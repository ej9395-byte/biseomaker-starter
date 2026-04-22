#!/bin/bash
# 비서메이커 스타터 크론 자동 등록
# 실행: bash setup/cron_template.sh

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UV="/opt/homebrew/bin/uv"

echo "크론 등록 시작: $SCRIPT_DIR"

# 기존 비서메이커 크론 제거
crontab -l 2>/dev/null | grep -v "biseomaker-starter" | crontab -

# 새 크론 추가
(crontab -l 2>/dev/null; cat <<EOF

# === 비서메이커 스타터 크론 ===

# 암묵지 수집 (매일 01:00)
0 1 * * * $UV run $SCRIPT_DIR/scripts/tacit_knowledge_extractor.py --daily >> $SCRIPT_DIR/logs/cron.log 2>&1

# 지식 그래프 스캔 (매일 02:55)
55 2 * * * $UV run $SCRIPT_DIR/scripts/knowledge_graph_builder.py >> $SCRIPT_DIR/logs/cron.log 2>&1

# 학습 질문 발송 (매일 07:00, 12:00, 20:00)
0 7,12,20 * * * $UV run $SCRIPT_DIR/scripts/knowledge_graph_builder.py --send >> $SCRIPT_DIR/logs/cron.log 2>&1

# 답변 수신 (매 5분)
*/5 * * * * $UV run $SCRIPT_DIR/scripts/knowledge_answer_listener.py >> $SCRIPT_DIR/logs/cron.log 2>&1

# 주간 중복 제거 (매주 일요일 02:00)
0 2 * * 0 $UV run $SCRIPT_DIR/scripts/tacit_knowledge_extractor.py --weekly >> $SCRIPT_DIR/logs/cron.log 2>&1

# 주간 소화 리포트 (매주 일요일 03:00)
0 3 * * 0 $UV run $SCRIPT_DIR/scripts/second_brain_agent.py --digest >> $SCRIPT_DIR/logs/cron.log 2>&1

# 암묵지 승격 (매주 일요일 03:30)
30 3 * * 0 $UV run $SCRIPT_DIR/scripts/second_brain_agent.py --promote >> $SCRIPT_DIR/logs/cron.log 2>&1

# 스타터 레포 주간 업데이트 (매주 일요일 자정)
0 0 * * 0 $UV run $SCRIPT_DIR/scripts/starter_sync.py >> $SCRIPT_DIR/logs/cron.log 2>&1

EOF
) | crontab -

echo "크론 등록 완료!"
crontab -l | grep -A1 "비서메이커 스타터"
