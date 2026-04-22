#!/usr/bin/env python3
"""지식 그래프 빌더 — 빈 곳 탐지 + 질문 생성 + 텔레그램 발송

사용법:
    uv run scripts/knowledge_graph_builder.py          # 스캔 + 큐 저장
    uv run scripts/knowledge_graph_builder.py --send   # 텔레그램 발송
    uv run scripts/knowledge_graph_builder.py --status
"""

import argparse
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
WORKSPACE      = Path(os.getenv("WORKSPACE_DIR", Path.home() / "biseomaker-workspace"))
WIKI_DIR       = WORKSPACE / "knowledge" / "wiki"
TACIT_DIR      = WORKSPACE / "knowledge" / "tacit"
QUEUE_PATH     = WORKSPACE / "data" / "question_queue.json"
CACHE_PATH     = WORKSPACE / "data" / "graph_cache.json"
LOG_PATH       = WORKSPACE / "logs" / "graph_builder.log"
CLAUDE_BIN     = Path(os.getenv("CLAUDE_BIN", Path.home() / ".local" / "bin" / "claude"))

MODEL_SYNTHESIZE = os.getenv("MODEL_SYNTHESIZE", "claude-opus-4-7")

BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")
OWNER_NAME = os.getenv("OWNER_NAME", "대표님")
BOT_NAME   = os.getenv("BOT_NAME", "비서")

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


def _send_telegram(msg: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print(msg)
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg}).encode()
    try:
        urllib.request.urlopen(url, data, timeout=10)
    except Exception as e:
        _log(f"텔레그램 실패: {e}")


def _claude(prompt: str) -> str:
    result = subprocess.run(
        [str(CLAUDE_BIN), "-p", prompt, "--model", MODEL_SYNTHESIZE],
        capture_output=True, text=True, timeout=120
    )
    return result.stdout.strip()


def _extract_concepts(text: str) -> set[str]:
    words = re.findall(r"[\w가-힣]{2,}", text)
    stopwords = {"있다", "없다", "하다", "이다", "되다", "않다", "이런", "그런", "저런", "것이", "수가"}
    return {w for w in words if w not in stopwords and len(w) >= 2}


# ---------------------------------------------------------------------------
# 기능
# ---------------------------------------------------------------------------

def cmd_scan() -> None:
    all_files = list(WIKI_DIR.rglob("*.md")) + list(TACIT_DIR.rglob("*.md"))
    if not all_files:
        _log("지식 파일 없음 — 스캔 스킵")
        return

    concept_map: dict[str, list[str]] = {}
    for f in all_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        concepts = _extract_concepts(text)
        for c in concepts:
            concept_map.setdefault(c, []).append(f.stem)

    _save_json(CACHE_PATH, concept_map)
    _log(f"그래프 스캔 완료: {len(concept_map)}개 개념")

    # 빈 곳 탐지 — 한 파일에만 등장하는 개념 = 연결 안 된 지식
    isolated = [c for c, files in concept_map.items() if len(files) == 1]
    if not isolated:
        _log("고립된 개념 없음")
        return

    sample = isolated[:20]
    prompt = f"""{OWNER_NAME}의 지식 그래프에서 아직 깊이 탐구되지 않은 개념들이 있습니다.
아래 개념 중에서 {OWNER_NAME}에게 물어볼 만한 핵심 질문 3개를 만들어 주세요.
질문은 짧고 구체적으로, 한 줄씩 작성하세요.

개념 목록: {', '.join(sample)}"""

    questions = _claude(prompt)
    queue = _load_json(QUEUE_PATH)
    ts = datetime.now().isoformat()
    for q in questions.splitlines():
        q = q.strip()
        if q:
            qid = f"q_{ts[:19].replace(':', '-')}_{len(queue)}"
            queue[qid] = {"question": q, "created": ts, "sent": False}

    _save_json(QUEUE_PATH, queue)
    _log(f"질문 {len([q for q in questions.splitlines() if q.strip()])}개 생성")


def cmd_send() -> None:
    queue = _load_json(QUEUE_PATH)
    unsent = [(qid, item) for qid, item in queue.items() if not item.get("sent")]
    if not unsent:
        _log("발송할 질문 없음")
        return

    qid, item = unsent[0]
    msg = f"[{BOT_NAME} 학습 질문]\n\n{item['question']}\n\n짧게 답변해 주시면 지식베이스에 반영됩니다."
    _send_telegram(msg)
    queue[qid]["sent"] = True
    queue[qid]["sent_at"] = datetime.now().isoformat()
    _save_json(QUEUE_PATH, queue)
    _log(f"질문 발송: {item['question'][:50]}")


def cmd_status() -> None:
    queue = _load_json(QUEUE_PATH)
    cache = _load_json(CACHE_PATH)
    unsent = sum(1 for item in queue.values() if not item.get("sent"))
    lines = [
        "=== 지식 그래프 현황 ===",
        f"  개념 수: {len(cache)}",
        f"  대기 질문: {unsent}개",
        f"  전체 질문: {len(queue)}개",
    ]
    _log("\n".join(lines))


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send",   action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.send:
        cmd_send()
    elif args.status:
        cmd_status()
    else:
        cmd_scan()


if __name__ == "__main__":
    main()
