# YouTube KR Trend Report 자동화

매일 오전 8시(KST), 유튜브 한국 트렌드를 수집·분석해서 PDF 리포트로 만들어 이메일로 보내고, 모든 데이터를 Notion에 누적 저장하는 자동화.

## 매일 일어나는 일 (자동)

1. **트렌드 후보 30개 수집** — 유튜브 공식 인기차트(mostPopular, 카테고리별) + 최근 48시간 내 조회수 급상승 검색을 합쳐서 후보군을 모음
2. **어제 대비 증가분 기준으로 Top 10 선정** — 단순 누적 조회수가 아니라, Notion에 저장된 어제 데이터와 비교해서 "오늘 얼마나 늘었는지" 기준으로 순위를 매김 (그래야 예전부터 꾸준히 조회수 높은 영상이 매일 우려먹듯 상위권을 차지하지 않음)
3. **자막 추출** — 가능한 영상만, 안 되면 제목/설명 기반으로 분석
4. **분석** — Claude가 직접 영상별 요약/훅스타일/주제, 전체 트렌드 테마, 포맷 인사이트, 이번 주 추천 콘텐츠 주제 작성
5. **PDF 리포트 생성** — 한글 지원, 깔끔한 기본 톤
6. **이메일 발송** — PDF 첨부 + 영상 링크 목록 포함
7. **Notion에 누적 저장** — 다음날 급상승 계산의 기준 데이터가 됨

## 어디서 돌아가는가

**클라우드**(Anthropic 서버)에서 매일 자동 실행됩니다. 로컬 컴퓨터가 꺼져 있어도 상관없습니다.

- GitHub 저장소(코드): https://github.com/bjb806/youtube-trend-automation (public — 코드에는 실제 API 키가 절대 없음, 전부 환경변수로만 읽음)
- 클라우드 스케줄 관리: https://claude.ai/code/routines/trig_01E9eKVJQCnsDcVky1tL8dV1
- Notion 데이터: "YouTube Trend Reports" 페이지 안 "YouTube KR Trends" 데이터베이스

## 파일 구성

```
workflows/daily_trend_report.md   ← 전체 프로세스 매뉴얼 (Claude가 매일 이걸 보고 실행)
tools/
  youtube_fetch.py       ← 트렌드 후보 수집 (YouTube Data API v3)
  rank_by_growth.py      ← 어제 대비 증가분으로 Top 10 재정렬 (Notion 조회)
  youtube_transcript.py  ← 자막 추출
  pdf_report.py          ← PDF 리포트 생성 (한글 폰트 포함)
  gmail_send.py          ← Gmail 발송 (OAuth)
  notion_sync.py         ← Notion 데이터베이스 생성/동기화
requirements.txt          ← 파이썬 의존성 목록
```

## 자격증명이 어디 있는가

- **로컬(`/Users/jeongbin/claude-study/`)**: `.env`(API 키), `credentials.json`/`token.json`(Gmail OAuth) — 전부 git에는 안 올라감(`.gitignore`)
- **클라우드(claude.ai 환경설정)**: `YOUTUBE_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`, `REPORT_RECIPIENT_EMAIL`, `GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON` — claude.ai/code의 "Default" 환경에 등록되어 있으며, 매일 실행 시 이 값들을 사용함

## 문제가 생기면

`workflows/daily_trend_report.md`의 "Error Handling Summary" 표에 단계별 대응 방법이 정리되어 있음. Gmail 토큰은 OAuth 동의화면이 "In production" 상태여야 만료 없이 계속 작동함(이미 설정 완료).
