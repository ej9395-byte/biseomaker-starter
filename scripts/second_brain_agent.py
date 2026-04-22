#!/usr/bin/env python3
"""SecondBrain 오케스트레이터 — 현황 요약, 주간 소화 리포트, 갭 탐지, 승격

실행:
    uv run scripts/second_brain_agent.py --status
    uv run scripts/second_brain_agent.py --digest
    uv run scripts/second_brain_agent.py --promote
    uv run scripts/second_brain_agent.py --recheck
"""

import argparse
import json
import os
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# 환경 변수 기반 설정
# ---------------------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv()

WORKSPACE        = Path(os.getenv("WORKSPACE_DIR", Path.home() / "biseomaker-workspace"))
TACIT_DIR        = WORKSPACE / "knowledge" / "tacit"
GRAD_LOG_PATH    = WORKSPACE / "data" / "graduation_log.json"
TACIT_SEEN_PATH  = WORKSPACE / "data" / "tacit_seen.json"
RECHECK_PATH     = WORKSPACE / "data" / "tacit_recheck_queue.json"
LOG_PATH         = WORKSPACE / "logs" / "second_brain.log"
CLAUDE_BIN       = Path(os.getenv("CLAUDE_BIN", Path.home() / ".local" / "bin" / "claude"))
OBSIDIAN_INBOX   = Path(os.getenv("OBSIDIAN_INBOX_DIR", ""))

MODEL_COLLECT    = os.getenv("MODEL_COLLECT",    "claude-haiku-4-5-20251001")
MODEL_LEARN      = os.getenv("MODEL_LEARN",      "claude-sonnet-4-6")
MODEL_SYNTHESIZE = os.getenv("MODEL_SYNTHESIZE", "claude-opus-4-7")

BOT_NAME    = os.getenv("BOT_NAME",    "비서")
OWNER_NAME  = os.getenv("OWNER_NAME",  "대표님")
CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "")
BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")

# DOMAINS: 쉼표 구분 문자열 → dict
_raw_domains = os.getenv("DOMAINS", "sales,operations,marketing").split(",")
DOMAIN_FILES: dict[str, Path] = {
    d.strip(): TACIT_DIR / f"{d.strip()}.md" for d in _raw_domains if d.strip()
}

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        _log(f"JSON 로드 실패 {path}: {e}")
        return {}


def _send_telegram(msg: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        _log("텔레그램 미설정 — 콘솔 출력만")
        print(msg)
        return
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg}).encode()
    try:
        urllib.request.urlopen(url, data, timeout=10)
    except Exception as e:
        _log(f"텔레그램 발송 실패: {e}")


def _claude(prompt: str, model: str = MODEL_LEARN) -> str:
    result = subprocess.run(
        [str(CLAUDE_BIN), "-p", prompt, "--model", model],
        capture_output=True, text=True, timeout=120
    )
    return result.stdout.strip()


def _write_obsidian(filename: str, content: str) -> None:
    if not OBSIDIAN_INBOX or not OBSIDIAN_INBOX.exists():
        return
    out = OBSIDIAN_INBOX / filename
    out.write_text(content, encoding="utf-8")
    _log(f"옵시디언 Inbox 저장: {out.name}")

# ---------------------------------------------------------------------------
# 기능
# ---------------------------------------------------------------------------

def cmd_status() -> None:
    grad = _load_json(GRAD_LOG_PATH)
    seen = _load_json(TACIT_SEEN_PATH)
    lines = [f"=== {BOT_NAME} 세컨드브레인 현황 ({date.today()}) ==="]
    for domain, path in DOMAIN_FILES.items():
        if path.exists():
            text = path.read_text(encoding="utf-8")
            count = text.count("\n##")
            lines.append(f"  {domain}: {count}개 항목")
        else:
            lines.append(f"  {domain}: 파일 없음")
    lines.append(f"졸업 항목: {len(grad)} | 처리된 대화: {len(seen)}")
    msg = "\n".join(lines)
    _log(msg)
    _send_telegram(msg)


def cmd_digest() -> None:
    all_tacit = []
    for domain, path in DOMAIN_FILES.items():
        if path.exists():
            all_tacit.append(f"[{domain}]\n{path.read_text(encoding='utf-8')[:2000]}")

    if not all_tacit:
        _log("암묵지 없음 — digest 스킵")
        return

    prompt = f"""다음은 {OWNER_NAME}의 지난 한 주 암묵지 목록입니다.
주간 소화 리포트를 작성해 주세요:
- 가장 중요한 인사이트 3가지
- 반복 패턴 발견된 것
- 다음 주 적용 권고사항

암묵지:
{'---'.join(all_tacit)}
"""
    report = _claude(prompt, MODEL_SYNTHESIZE)
    today = date.today().strftime("%Y-%m-%d")
    _write_obsidian(f"{today}_주간리뷰.md", f"# 주간 소화 리포트 {today}\n\n{report}")
    _send_telegram(f"주간 리포트 생성 완료. 옵시디언 Inbox 확인하세요.")
    _log("digest 완료")


def cmd_promote() -> None:
    recheck = _load_json(RECHECK_PATH)
    if not recheck:
        _log("재심 큐 비어있음")
        return
    grad = _load_json(GRAD_LOG_PATH)
    promoted = 0
    for item_id, item in list(recheck.items()):
        if item.get("confidence", 0) >= 0.8:
            grad[item_id] = item
            del recheck[item_id]
            promoted += 1
    GRAD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAD_LOG_PATH.write_text(json.dumps(grad, ensure_ascii=False, indent=2), encoding="utf-8")
    RECHECK_PATH.write_text(json.dumps(recheck, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"승격 완료: {promoted}개")
    if promoted:
        _send_telegram(f"암묵지 {promoted}개가 지식베이스로 승격되었습니다.")


def cmd_recheck() -> None:
    recheck = _load_json(RECHECK_PATH)
    if not recheck:
        _log("재심 큐 비어있음")
        return
    for item_id, item in recheck.items():
        prompt = f"""다음 암묵지의 신뢰도를 0.0~1.0으로 평가해 주세요. 숫자만 답변:
{item.get('content', '')}"""
        score_str = _claude(prompt, MODEL_COLLECT)
        try:
            score = float(score_str.strip())
            recheck[item_id]["confidence"] = score
        except ValueError:
            pass
    RECHECK_PATH.write_text(json.dumps(recheck, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"재심 완료: {len(recheck)}개")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status",  action="store_true")
    parser.add_argument("--digest",  action="store_true")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--recheck", action="store_true")
    args = parser.parse_args()

    if args.status:  cmd_status()
    elif args.digest:  cmd_digest()
    elif args.promote: cmd_promote()
    elif args.recheck: cmd_recheck()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
