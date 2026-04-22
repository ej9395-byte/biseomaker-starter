# 비서메이커 스타터

비서메이커 고객 전용 AI 파트너 세팅 레포입니다. Claude Code에 URL 한 줄을 붙여넣으면 자동으로 세팅이 완료됩니다.

---

## 시작하기 (원라인 세팅)

Claude Code를 열고 아래 문장을 그대로 붙여넣으세요.

```
https://raw.githubusercontent.com/ej9395-byte/biseomaker-starter/main/SETUP.md 읽고 내 비서 세팅해줘
```

Claude가 질문 12개를 물어보고, 답변을 바탕으로 세팅을 자동으로 완료합니다.

---

## 사전 준비

세팅 전에 아래가 준비되어 있어야 합니다.

| 항목 | 확인 방법 |
|------|----------|
| Claude Code 설치 | `claude --version` |
| Python + uv 설치 | `uv --version` |
| 텔레그램 봇 토큰 | @BotFather에서 발급 |
| 텔레그램 Chat ID | @userinfobot에서 확인 |
| Anthropic API 키 | console.anthropic.com |
| 옵시디언 설치 (선택) | obsidian.md |

---

## 세팅되는 항목

- **AI 파트너 헌법** — 내 사업에 맞게 개인화된 Claude 설정
- **암묵지 수집 파이프라인** — 매일 업무 대화에서 노하우를 자동 추출
- **지식 그래프** — 빠진 지식을 텔레그램으로 질문, 답변을 자동 저장
- **옵시디언 연동** — AI가 학습한 내용을 Inbox에 자동 기록
- **크론 자동화** — 매일 새벽 수집·학습·반영 파이프라인 자동 실행

---

## 디렉토리 구조

```
biseomaker-starter/
├── SETUP.md                    ← Claude가 읽고 실행하는 세팅 가이드
├── CLAUDE.md                   ← AI 파트너 기본 헌법
├── .env.example                ← 환경변수 목록 (값 없음)
├── setup/
│   ├── rules_template/         ← Claude 규칙 템플릿
│   ├── SOUL_template.md        ← AI 파트너 정체성 템플릿
│   └── cron_template.sh        ← 크론 자동 등록 스크립트
├── scripts/
│   ├── second_brain_agent.py   ← 학습 파이프라인 오케스트레이터
│   ├── tacit_knowledge_extractor.py  ← 암묵지 수집·분류
│   ├── knowledge_graph_builder.py    ← 지식 그래프 + 빈 곳 질문
│   └── knowledge_answer_listener.py  ← 텔레그램 답변 수신·반영
├── knowledge/                  ← 암묵지·위키 저장소 (세팅 시 채워짐)
└── obsidian/                   ← 옵시디언 볼트 스타터
    ├── Templates/              ← AI가 노트 생성 시 사용하는 템플릿
    └── .obsidian/              ← 추천 플러그인 설정
```

---

## 학습 파이프라인 흐름

```
매일 업무 대화
    ↓
암묵지 자동 추출 (tacit_knowledge_extractor)
    ↓
지식 그래프 빈 곳 탐지 → 텔레그램 질문 (knowledge_graph_builder)
    ↓
답변 수신 → 지식 반영 (knowledge_answer_listener)
    ↓
주간 정리 + 옵시디언 Inbox 업데이트 (second_brain_agent)
```

---

## 업데이트

이 레포는 매주 일요일 자정 자동으로 최신 버전으로 업데이트됩니다. 별도로 할 일은 없습니다.

---

**비서메이커** | [biseomaker.shop](https://biseomaker.shop)
