#!/usr/bin/env python3
"""텔레그램 답변 수신 → 지식베이스 반영

사용법:
    uv run scripts/knowledge_answer_listener.py   # 5분마다 크론으로 실행
"""

import json
import os
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
WORKSPACE    = Path(os.getenv("WORKSPACE_DIR", Path.home() / "biseomaker-workspace"))
QUEUE_PATH   = WORKSPACE / "data" / "question_queue.json"
TACIT_DIR    = WORKSPACE / "knowledge" / "tacit"
LOG_PATH     = WORKSPACE / "logs" / "answer_listener.log"
CLAUDE_BIN   = Path(os.getenv("CLAUDE_BIN", Path.home() / ".local" / "bin" / "claude"))
OBSIDIAN_INBOX = Path(os.getenv("OBSIDIAN_INBOX_DIR", ""))

MODEL_LEARN  = os.getenv("MODEL_LEARN", "claude-sonnet-4-6")
BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID      = os.getenv("TELEGRAM_CHAT_ID", "")

_raw_domains = os.getenv("DOMAINS", "sales,operations,marketing").split(",")
DOMAIN_FILES: dict[str, Path] = {
    d.strip(): TACIT_DIR / f"{d.strip()}.md" for d in _raw_domains if d.strip()
}

OFFSET_PATH  = WORKSPACE / "data" / "tg_offset.json"

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


def _get_updates(offset: int = 0) -> list:
    if not BOT_TOKEN:
        return []
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=5"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("result", [])
    except Exception as e:
        _log(f"업데이트 수신 실패: {e}")
        return []


def _classify_and_save(answer: str) -> None:
    domains = list(DOMAIN_FILES.keys())
    prompt = f"""다음 답변을 읽고 가장 적합한 도메인을 선택하고, 암묵지로 요약해 주세요.
형식: DOMAIN: <도메인명>\nSUMMARY: <한 줄 요약>

도메인 선택지: {', '.join(domains)}
답변: {answer[:500]}"""

    result = subprocess.run(
        [str(CLAUDE_BIN), "-p", prompt, "--model", MODEL_LEARN],
        capture_output=True, text=True, timeout=60
    ).stdout.strip()

    domain = domains[0]
    summary = answer[:200]

    for line in result.splitlines():
        if line.startswith("DOMAIN:"):
            d = line.split(":", 1)[1].strip().lower()
            if d in DOMAIN_FILES:
                domain = d
        elif line.startswith("SUMMARY:"):
            summary = line.split(":", 1)[1].strip()

    path = DOMAIN_FILES[domain]
    path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n## [answer] {today}\n{summary}\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)
    _log(f"반영 완료 → {domain}: {summary[:50]}")

    if OBSIDIAN_INBOX and Path(OBSIDIAN_INBOX).exists():
        fname = f"{today}_답변반영_{domain}.md"
        (Path(OBSIDIAN_INBOX) / fname).write_text(
            f"# 답변 반영 {today}\n도메인: {domain}\n\n{summary}\n",
            encoding="utf-8"
        )


def main():
    offset_data = _load_json(OFFSET_PATH)
    offset = offset_data.get("offset", 0)

    updates = _get_updates(offset)
    if not updates:
        return

    queue = _load_json(QUEUE_PATH)
    sent_questions = {
        qid: item for qid, item in queue.items()
        if item.get("sent") and not item.get("answered")
    }

    for update in updates:
        uid = update.get("update_id", 0)
        offset = max(offset, uid + 1)

        msg = update.get("message", {})
        text = msg.get("text", "").strip()
        from_id = str(msg.get("from", {}).get("id", ""))

        if not text or from_id != CHAT_ID:
            continue

        if sent_questions:
            # 가장 최근 발송 질문에 대한 답변으로 처리
            latest_qid = sorted(
                sent_questions.keys(),
                key=lambda q: sent_questions[q].get("sent_at", ""),
                reverse=True
            )[0]
            _classify_and_save(text)
            queue[latest_qid]["answered"] = True
            queue[latest_qid]["answer"] = text
            _save_json(QUEUE_PATH, queue)

    _save_json(OFFSET_PATH, {"offset": offset})


if __name__ == "__main__":
    main()
