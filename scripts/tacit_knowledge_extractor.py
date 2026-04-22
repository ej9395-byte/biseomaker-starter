#!/usr/bin/env python3
"""암묵지 자동 수집·저장 엔진

사용법:
    uv run scripts/tacit_knowledge_extractor.py --daily
    uv run scripts/tacit_knowledge_extractor.py --weekly
    uv run scripts/tacit_knowledge_extractor.py --status
"""

import argparse
import json
import os
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
WORKSPACE       = Path(os.getenv("WORKSPACE_DIR", Path.home() / "biseomaker-workspace"))
LOG_DIR         = Path(os.getenv("LOG_DIR", Path.home() / "Documents" / "업무일지"))
TACIT_DIR       = WORKSPACE / "knowledge" / "tacit"
GRAD_LOG_PATH   = WORKSPACE / "data" / "graduation_log.json"
SEEN_LOG_PATH   = WORKSPACE / "data" / "tacit_seen.json"
LOG_PATH        = WORKSPACE / "logs" / "tacit_extractor.log"
CLAUDE_BIN      = Path(os.getenv("CLAUDE_BIN", Path.home() / ".local" / "bin" / "claude"))
OBSIDIAN_INBOX  = Path(os.getenv("OBSIDIAN_INBOX_DIR", ""))

MODEL_COLLECT   = os.getenv("MODEL_COLLECT", "claude-haiku-4-5-20251001")
MODEL_LEARN     = os.getenv("MODEL_LEARN",   "claude-sonnet-4-6")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

_raw_domains = os.getenv("DOMAINS", "sales,operations,marketing").split(",")
DOMAIN_FILES: dict[str, Path] = {
    d.strip(): TACIT_DIR / f"{d.strip()}.md" for d in _raw_domains if d.strip()
}

# 암묵지 탐지 패턴 (도메인 중립적)
TACIT_PATTERNS = [
    (r"보통\s*(이럴|이런|그런)\s*때", "rule"),
    (r"경험(상|에서)\s*(보면|항상|대개)", "rule"),
    (r"항상\s*(이렇게|이런\s*식으로)", "rule"),
    (r"느낌(으로|상)\s*(판단|결정|처리)", "decision"),
    (r"해봤더니\s*(이게|이런|역시)", "decision"),
    (r"이런\s*(유형|경우)(은|의)\s*(보통|항상)", "pattern"),
    (r"반복(되는|적으로)\s*(보면|나타나)", "pattern"),
    (r"(핵심|포인트|비결)(은|이)\s*(결국|사실)", "knowhow"),
    (r"이게\s*(진짜|핵심|포인트)(야|이야)", "knowhow"),
    (r"다음엔\s*(꼭|반드시|이렇게)", "reflection"),
    (r"그때\s*(알았으면|했으면)\s*(좋았을)", "reflection"),
]

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
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _claude(prompt: str, model: str = MODEL_COLLECT) -> str:
    result = subprocess.run(
        [str(CLAUDE_BIN), "-p", prompt, "--model", model],
        capture_output=True, text=True, timeout=60
    )
    return result.stdout.strip()


def _detect_tacit(text: str) -> list[tuple[str, str]]:
    found = []
    for pattern, ptype in TACIT_PATTERNS:
        for m in re.finditer(pattern, text):
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 200)
            snippet = text[start:end].strip()
            found.append((snippet, ptype))
    return found


def _classify_domain(snippet: str) -> str:
    domains = list(DOMAIN_FILES.keys())
    if not domains:
        return domains[0] if domains else "operations"
    prompt = f"""다음 문장이 아래 도메인 중 어디에 해당하는지 도메인명만 답변하세요.
도메인: {', '.join(domains)}

문장: {snippet[:300]}"""
    result = _claude(prompt, MODEL_COLLECT).strip().lower()
    for d in domains:
        if d in result:
            return d
    return domains[0]


def _append_tacit(domain: str, snippet: str, ptype: str) -> None:
    path = DOMAIN_FILES.get(domain)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    entry = f"\n## [{ptype}] {today}\n{snippet}\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)


def _write_obsidian(filename: str, content: str) -> None:
    if not OBSIDIAN_INBOX or not Path(OBSIDIAN_INBOX).exists():
        return
    out = Path(OBSIDIAN_INBOX) / filename
    out.write_text(content, encoding="utf-8")
    _log(f"옵시디언 저장: {out.name}")

# ---------------------------------------------------------------------------
# 명령
# ---------------------------------------------------------------------------

def cmd_daily() -> None:
    yesterday = date.today() - timedelta(days=1)
    pattern = yesterday.strftime("%Y-%m-%d")
    log_dir = Path(LOG_DIR)

    if not log_dir.exists():
        _log(f"로그 디렉토리 없음: {log_dir}")
        return

    files = list(log_dir.glob(f"*{pattern}*"))
    if not files:
        _log(f"{pattern} 날짜 파일 없음")
        return

    seen = _load_json(SEEN_LOG_PATH)
    new_count = 0

    for f in files:
        fid = f.stem
        if fid in seen:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        snippets = _detect_tacit(text)
        for snippet, ptype in snippets:
            domain = _classify_domain(snippet)
            _append_tacit(domain, snippet, ptype)
            new_count += 1
        seen[fid] = {"processed": datetime.now().isoformat()}

    _save_json(SEEN_LOG_PATH, seen)

    if new_count > 0:
        today_str = date.today().strftime("%Y-%m-%d")
        summary = f"# 암묵지 수집 {today_str}\n\n수집된 항목: {new_count}개\n"
        _write_obsidian(f"{today_str}_암묵지수집.md", summary)

    _log(f"daily 완료: {new_count}개 신규 암묵지")


def cmd_weekly() -> None:
    all_domains = {}
    for domain, path in DOMAIN_FILES.items():
        if path.exists():
            all_domains[domain] = path.read_text(encoding="utf-8")

    if not all_domains:
        _log("암묵지 없음 — weekly 스킵")
        return

    prompt = f"""아래 암묵지 목록에서 중복 항목을 제거하고 핵심만 남겨 재구성해 주세요.
각 도메인별로 유지하고 마크다운 형식으로 출력하세요.

{json.dumps({k: v[:1500] for k, v in all_domains.items()}, ensure_ascii=False)}"""

    result = _claude(prompt, MODEL_LEARN)
    _log(f"weekly 중복 제거 완료: {len(result)}자")


def cmd_status() -> None:
    lines = ["=== 암묵지 현황 ==="]
    for domain, path in DOMAIN_FILES.items():
        if path.exists():
            count = path.read_text(encoding="utf-8").count("\n##")
            lines.append(f"  {domain}: {count}개")
        else:
            lines.append(f"  {domain}: 없음")
    seen = _load_json(SEEN_LOG_PATH)
    lines.append(f"처리된 파일: {len(seen)}개")
    _log("\n".join(lines))


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily",  action="store_true")
    parser.add_argument("--weekly", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.daily:   cmd_daily()
    elif args.weekly: cmd_weekly()
    elif args.status: cmd_status()
    else: parser.print_help()


if __name__ == "__main__":
    main()
