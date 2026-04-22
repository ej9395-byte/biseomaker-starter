# 비서메이커 스타터 세팅 가이드

> Claude Code가 이 파일을 읽고 자동으로 세팅을 진행합니다.
> 고객은 아래 원라인을 Claude에 붙여넣기만 하면 됩니다.

---

## Claude 실행 지시사항

이 파일을 읽은 Claude는 아래 순서대로 세팅을 진행하세요.

### 1단계: 사업 정보 수집 (온톨로지 서베이)

다음 12가지 항목을 대표님께 순서대로 질문하세요. 한 번에 2~3개씩 나눠서 물어보세요.

```
1. 대표님 성함이 어떻게 되세요?
2. 사업체 이름(상호)은 무엇인가요?
3. 어떤 업종/업무를 하시나요? (예: 도어락 설치, 카페 운영, 세무 컨설팅)
4. 주요 서비스/상품을 한 줄로 설명해 주세요.
5. 주요 고객은 누구인가요? (예: 아파트 주민, 소상공인, 법인)
6. 텔레그램 Chat ID를 알려주세요. (없으면 @userinfobot 으로 확인)
7. 텔레그램 봇 토큰을 알려주세요. (없으면 @BotFather 에서 생성)
8. Claude API 키가 있으신가요? (있으면 알려주세요)
9. 옵시디언이 설치되어 있나요? 볼트(폴더) 경로가 어디인가요?
10. 대화 기록이나 업무 일지를 저장하는 폴더가 있나요? 경로를 알려주세요.
11. 이번 달 가장 중요한 목표 하나를 말씀해 주세요.
12. AI 파트너 이름을 정해주세요. (예: 지음, 해피, 제리)
```

### 2단계: 환경 설정

수집한 정보로 `.env` 파일을 생성하세요:

```bash
# 아래 내용으로 .env 파일 생성
TELEGRAM_BOT_TOKEN={7번 답변}
TELEGRAM_CHAT_ID={6번 답변}
ANTHROPIC_API_KEY={8번 답변}
OBSIDIAN_VAULT_DIR={9번 답변 경로}
OBSIDIAN_INBOX_DIR={9번 답변 경로}/Inbox
LOG_DIR={10번 답변 경로}
WORKSPACE_DIR={현재 디렉토리 절대경로}
BUSINESS_NAME={2번 답변}
BUSINESS_DOMAIN={3번 답변}
BOT_NAME={12번 답변}
OWNER_NAME={1번 답변}
MONTHLY_GOAL={11번 답변}
DOMAINS=domain1,domain2,domain3
```

`DOMAINS`는 업종 기반으로 Claude가 자동 추천: 예) `sales,operations,marketing,customer,product`

### 3단계: Claude 헌법 생성

`setup/rules_template/` 파일들을 `.claude/rules/` 로 복사하고 플레이스홀더를 교체하세요:

```bash
mkdir -p ~/.claude/rules
cp setup/rules_template/*.md ~/.claude/rules/
```

각 파일의 플레이스홀더를 수집한 정보로 교체:
- `{BOT_NAME}` → 12번 답변
- `{OWNER_NAME}` → 1번 답변
- `{BUSINESS_NAME}` → 2번 답변
- `{BUSINESS_DOMAIN}` → 3번 답변
- `{MONTHLY_GOAL}` → 11번 답변

`setup/SOUL_template.md` → `SOUL.md` 로 복사 후 동일하게 교체

### 4단계: 지식 디렉토리 구조 생성

`.env`의 `DOMAINS` 값을 기반으로 암묵지 파일 생성:

```bash
mkdir -p knowledge/tacit knowledge/wiki
# DOMAINS에 있는 각 도메인마다 빈 파일 생성
# 예: knowledge/tacit/sales.md, knowledge/tacit/operations.md ...
```

### 5단계: 옵시디언 볼트 연동

```bash
# 옵시디언 볼트 디렉토리에 Inbox 폴더 생성
mkdir -p "{OBSIDIAN_VAULT_DIR}/Inbox"
mkdir -p "{OBSIDIAN_VAULT_DIR}/Tacit"
mkdir -p "{OBSIDIAN_VAULT_DIR}/Wiki"

# 옵시디언 설정 파일 복사
cp -r obsidian/.obsidian "{OBSIDIAN_VAULT_DIR}/"
cp -r obsidian/Templates "{OBSIDIAN_VAULT_DIR}/"
```

### 6단계: 크론 등록

```bash
bash setup/cron_template.sh
```

### 7단계: 연결 테스트

```bash
# 텔레그램 봇 테스트
uv run scripts/second_brain_agent.py --status

# 암묵지 추출기 테스트
uv run scripts/tacit_knowledge_extractor.py --status
```

텔레그램으로 "세팅 완료 테스트 메시지"가 오면 성공입니다.

### 8단계: 세팅 완료 보고

아래 내용을 대표님 텔레그램으로 발송하세요:

```
✅ {BOT_NAME} 세팅 완료!

📌 세팅된 항목:
- AI 파트너: {BOT_NAME}
- 사업체: {BUSINESS_NAME}
- 업종: {BUSINESS_DOMAIN}
- 옵시디언 볼트 연동: {OBSIDIAN_VAULT_DIR}
- 암묵지 도메인: {DOMAINS}
- 주간 업데이트: 매주 일요일 자정 자동 실행

📚 다음 단계:
매일 대화를 나누면 {BOT_NAME}이 자동으로 배워갑니다.
옵시디언 Inbox 폴더에서 새 학습 노트를 확인하세요.
```
