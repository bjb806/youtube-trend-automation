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

## 기술 스택

**언어**: Python 3.9 (표준 CLI 스크립트, 프레임워크 없음)

**라이브러리** (`requirements.txt`):
| 용도 | 라이브러리 |
|---|---|
| YouTube Data API v3 클라이언트 | `google-api-python-client` |
| Gmail OAuth2 인증/토큰 갱신 | `google-auth`, `google-auth-oauthlib`, `google-auth-httplib2` |
| 유튜브 자막 추출 | `youtube-transcript-api` (v1.x, 인스턴스 기반 `YouTubeTranscriptApi().fetch()` API) |
| Notion 공식 SDK | `notion-client` (v3.x, database/data_source 분리된 신 API 대응) |
| PDF 생성 | `fpdf2` (WeasyPrint 대신 선택 — 시스템 라이브러리 의존성 없이 순수 파이썬이라 클라우드 샌드박스에 더 안정적) |
| .env 로딩 | `python-dotenv` |

**아키텍처**: 전통적인 백엔드 서비스/스케줄러가 아니라, **LLM 에이전트가 각 단계마다 결정론적 Python 스크립트를 순서대로 호출하는 파이프라인**입니다.
- `tools/*.py`: 각각 단일 책임의 순수 함수 + argparse 기반 CLI (API 호출, 파일 생성 등 예측 가능한 실행부)
- `workflows/daily_trend_report.md`: 마크다운으로 작성된 오케스트레이션 스펙 (입력/단계/에러 핸들링/출력 스키마) — 별도의 워크플로우 엔진이 있는 게 아니라, 이 문서 자체가 매일 실행되는 Claude 세션에게 주어지는 "지시서"
- "분석"(영상별 요약, 주제 태깅, 추천 콘텐츠 도출) 단계는 툴이 아니라 **Claude가 직접 그 세션 안에서 자연어 추론으로 수행** — 여기서 나온 결과를 JSON으로 조립해서 이후 PDF/Notion 툴에 그대로 넘김

**실행 환경**: Anthropic Claude Code의 "Routines"(cron 기반 클라우드 에이전트, 내부적으로 CCR/claude-code-remote) — 매일 새 sandbox에서 GitHub 저장소를 클론하고 `pip install -r requirements.txt` 후 파이프라인 실행. 로컬 `.venv`와 별개의 완전히 격리된 환경.

**인증 방식**:
- YouTube: API 키 (읽기 전용, OAuth 불필요)
- Notion: Internal Integration의 정적 시크릿 토큰
- Gmail: OAuth2 Installed-App 플로우, refresh token 방식. 로컬에서 1회 브라우저 인증 후 `token.json` 생성 → 클라우드에서는 `GMAIL_CREDENTIALS_JSON`/`GMAIL_TOKEN_JSON` 환경변수로 런타임에 파일을 복원(`materialize_credential_files()`)해서 동일 코드로 로컬/클라우드 양쪽에서 동작

**구현 중 겪은 주요 이슈**:
- YouTube "인기 급상승" 탭이 2025-07-25 폐지되어 `mostPopular`가 카테고리별 차트로 바뀜 → `search.list` 급상승 검색과 병행
- `fpdf2`의 `multi_cell()`이 기본적으로 커서를 다음 줄 왼쪽이 아니라 우측에 남기는 동작이 있어 텍스트 오버플로우 버그 발생 → `new_x="LMARGIN"` 명시로 해결
- Notion API가 2025년 하반기에 database/data_source를 분리하는 방향으로 개편되어(`notion-client` v3.x), `databases.create()`에 `properties`가 아니라 `initial_data_source.properties`로 넣어야 하고, 페이지 생성 시 parent도 `data_source_id` 기준으로 바뀜
- 클라우드 sandbox의 네트워크 정책이 기본적으로 `api.notion.com`/`youtube.com` 아웃바운드를 차단 → 환경설정에서 네트워크 액세스를 "전체"로 변경

## 문제가 생기면

`workflows/daily_trend_report.md`의 "Error Handling Summary" 표에 단계별 대응 방법이 정리되어 있음. Gmail 토큰은 OAuth 동의화면이 "In production" 상태여야 만료 없이 계속 작동함(이미 설정 완료).
