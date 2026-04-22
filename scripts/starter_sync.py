#!/usr/bin/env python3
"""스타터 레포 주간 자동 업데이트
매주 일요일 자정, 메인 워크스페이스의 스크립트 최신본을 일반화해서 스타터 레포에 동기화.

사용법:
    uv run scripts/starter_sync.py
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
WORKSPACE       = Path(os.getenv("WORKSPACE_DIR", Path.home() / "biseomaker-workspace"))
STARTER_REPO    = Path(os.getenv("STARTER_REPO_DIR", ""))   # 스타터 레포 로컬 경로
SOURCE_SCRIPTS  = WORKSPACE / "scripts"                       # 메인 워크스페이스 스크립트
LOG_PATH        = WORKSPACE / "logs" / "starter_sync.log"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# 동기화 대상 스크립트 (메인 → 스타터)
SYNC_MAP = {
    "second_brain_agent.py":        "scripts/second_brain_agent.py",
    "tacit_knowledge_extractor.py": "scripts/tacit_knowledge_extractor.py",
    "knowledge_graph_builder.py":   "scripts/knowledge_graph_builder.py",
    "knowledge_answer_listener.py": "scripts/knowledge_answer_listener.py",
}

# 제거할 하드코딩 패턴 → env 변수 참조로 교체
REPLACE_PATTERNS = [
    # 특정 경로 → 환경변수
    (r'Path\.home\(\) / "\.openclaw" / "workspace"',
     'Path(os.getenv("WORKSPACE_DIR", Path.home() / "biseomaker-workspace"))'),
    (r'Path\.home\(\) / "Documents" / "비서메이커"',
     'Path(os.getenv("LOG_DIR", Path.home() / "Documents" / "업무일지"))'),
    # 특정 Chat ID
    (r'"2\d{9}"',  'os.getenv("TELEGRAM_CHAT_ID", "")'),
    # 특정 도메인 딕셔너리 → env 기반으로
    (r'"doorlock":\s*TACIT_DIR\s*/\s*"doorlock\.md"[^}]*"marketing":\s*TACIT_DIR\s*/\s*"marketing\.md"',
     '# DOMAIN_FILES: .env의 DOMAINS 변수로 동적 생성\n'
     '_raw_domains = os.getenv("DOMAINS", "sales,operations,marketing").split(",")\n'
     'DOMAIN_FILES = {d.strip(): TACIT_DIR / f"{d.strip()}.md" for d in _raw_domains if d.strip()}'),
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


def _send_telegram(msg: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        return
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg}).encode()
    try:
        urllib.request.urlopen(url, data, timeout=10)
    except Exception:
        pass


def _generalize(content: str) -> str:
    for pattern, replacement in REPLACE_PATTERNS:
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    return content


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True
    )
    return result.stdout.strip()

# ---------------------------------------------------------------------------
# 동기화
# ---------------------------------------------------------------------------

def main():
    if not STARTER_REPO or not STARTER_REPO.exists():
        _log(f"STARTER_REPO_DIR 미설정 또는 경로 없음: {STARTER_REPO}")
        return

    changed_files = []

    for src_name, dst_rel in SYNC_MAP.items():
        src = SOURCE_SCRIPTS / src_name
        dst = STARTER_REPO / dst_rel

        if not src.exists():
            _log(f"소스 없음: {src}")
            continue

        original = src.read_text(encoding="utf-8")
        generalized = _generalize(original)

        if dst.exists() and dst.read_text(encoding="utf-8") == generalized:
            _log(f"변경 없음: {src_name}")
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(generalized, encoding="utf-8")
        changed_files.append(src_name)
        _log(f"동기화 완료: {src_name}")

    if not changed_files:
        _log("이번 주 변경 없음 — 커밋 스킵")
        return

    # git commit & push
    today = datetime.now().strftime("%Y-%m-%d")
    _git(["add", "-A"], STARTER_REPO)
    _git(["commit", "-m", f"chore: weekly sync {today} ({len(changed_files)}개 파일)"], STARTER_REPO)
    _git(["push"], STARTER_REPO)

    msg = f"스타터 레포 업데이트 완료 ({today})\n변경: {', '.join(changed_files)}"
    _log(msg)
    _send_telegram(msg)


if __name__ == "__main__":
    main()
