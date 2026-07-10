# Daily Trend Report (매일 08:00 KST)

## Goal
유튜브 한국(KR) Top 10 트렌딩 영상을 수집·분석해서 PDF 리포트를 만들고, 본인(`REPORT_RECIPIENT_EMAIL` 환경변수의 주소)에게 이메일로 발송하고, 모든 데이터를 Notion에 누적 저장한다.

## Inputs
환경변수(클라우드 환경설정에 등록됨): `YOUTUBE_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`, `REPORT_RECIPIENT_EMAIL`, `GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON`

사용자로부터 받는 입력은 없음. 실행일 기준 날짜를 `{date}` (YYYY-MM-DD)로 사용.

### 0. 실행 환경 준비 (매 실행 시)
클라우드 실행 환경은 매번 새로 시작되므로, 본격적인 단계 전에 의존성을 설치한다:
```
pip install -r requirements.txt
```
`credentials.json`/`token.json`은 `tools/gmail_send.py`가 `GMAIL_CREDENTIALS_JSON`/`GMAIL_TOKEN_JSON` 환경변수로부터 자동으로 파일을 생성하므로 별도 조치가 필요 없다.

---

## Steps

### 1. 트렌드 후보 수집
```
python tools/youtube_fetch.py --region KR --top 30 --output .tmp/candidates_{date}.json
```
- `--top 30`으로 넉넉하게 후보군을 모은다 (최종 10개는 다음 단계에서 "어제 대비 증가분" 기준으로 뽑는다). 단순 조회수 누적 1위 영상만 매일 우려먹지 않기 위함.
- API 오류 시 1회 재시도. 그래도 실패하면 **발송 없이 중단**하고 로그만 남긴다. 내일 다시 시도되므로 과잉대응 금지. 단, **2일 연속 실패**하면 사용자에게 보고(쿼터 초과 또는 키 문제 가능성).

### 2. 급상승 기준 Top 10 선정
```
python tools/rank_by_growth.py --input .tmp/candidates_{date}.json --date {date} --database-id $NOTION_DATABASE_ID --top 10 --output .tmp/trending_{date}.json
```
- 어제 날짜로 Notion에 저장된 조회수와 비교해서, "어제보다 오늘 조회수가 얼마나 늘었는지"(`view_growth`)가 큰 순서로 최종 10개를 뽑는다. 어제 데이터에 없던 영상(신규 차트 진입)은 조회수 전체를 증가분으로 간주한다.
- Notion에 어제자 데이터가 아예 없으면(운영 첫날 등) 자동으로 조회수 누적 기준으로 대체된다 - 별도 처리 불필요.

### 3. 자막 추출
```
python tools/youtube_transcript.py --input .tmp/trending_{date}.json --output .tmp/trending_{date}.json --transcripts-dir .tmp/transcripts
```
- 특정 영상만 자막이 없으면 그 영상만 제목/설명 기반으로 분석하고 전체 흐름은 계속 진행한다.

### 4. 분석 (Claude가 직접 수행, 툴 없음)
`.tmp/trending_{date}.json`의 각 영상(제목, 통계, 자막/설명)을 읽고 직접 판단한다:
- 영상별: 2-3문장 요약(`analysis_summary`), 훅 스타일(`hook_style`), 주제 태그(`topic_tags`, 2-4개)
- 전체: 3-5개 크로스 비디오 테마, 포맷 인사이트(숏폼/롱폼 비율 등, `format_insights`)
- 이번 주 추천 콘텐츠 주제 3-5개, 각각 한 줄 근거(`recommended_topics`) — 가능하면 어떤 영상이 이 추천의 근거가 됐는지 `video_ids`에 포함

### 5. 리포트 데이터 조립
아래 스키마로 `.tmp/report_data_{date}.json`을 작성한다 (pdf_report.py, notion_sync.py가 이 형식을 그대로 사용):
```json
{
  "date": "YYYY-MM-DD",
  "region": "KR",
  "generated_at": "ISO8601 timestamp",
  "executive_summary": ["...", "..."],
  "videos": [
    {
      "rank": 1, "video_id": "...", "title": "...", "channel_name": "...", "channel_id": "...",
      "published_at": "ISO8601", "view_count": 0, "like_count": 0, "comment_count": 0,
      "duration_sec": 0, "format": "Shorts|Long-form", "category": "...", "source": "MostPopular|ViewCountSurge|Both",
      "thumbnail_url": "...", "video_url": "...", "transcript_available": true,
      "topic_tags": ["..."], "hook_style": "...", "analysis_summary": "..."
    }
  ],
  "format_insights": ["...", "..."],
  "recommended_topics": [{"topic": "...", "rationale": "...", "video_ids": ["..."]}]
}
```
(`video_id`~`transcript_available` 필드는 1~3단계 결과를 그대로 복사하고, `topic_tags`/`hook_style`/`analysis_summary`만 4단계에서 새로 채운다.)

### 6. PDF 생성
```
python tools/pdf_report.py --input .tmp/report_data_{date}.json --output .tmp/report_{date}.pdf
```
- 실패 시 "fix forward": 데이터 JSON 또는 툴 코드를 점검해 수정하고 재시도한다. 이 단계는 절대 건너뛰지 않는다.

### 7. 이메일 발송
```
python tools/gmail_send.py --to $REPORT_RECIPIENT_EMAIL --subject "YouTube KR Trend Report - {date}" --body-file .tmp/email_body_{date}.txt --attachment .tmp/report_{date}.pdf
```
- `email_body_{date}.txt`에는 핵심 요약 3줄 정도 + **Top 10 영상 제목과 링크(`video_url`) 목록**을 포함한다 (한 줄에 하나씩, `순위. 제목 - URL` 형식). 본문에서 바로 영상으로 이동할 수 있게 하는 것이 목적이며, 상세 분석은 PDF가 핵심.
- Gmail 인증 실패(토큰 만료 등)는 헤드리스 환경에서 대화형 재인증을 시도하지 않는다. 다음 단계는 계속 진행해 데이터 유실은 막되, 발송 실패를 명확히 보고한다 (로컬에서 수동 재인증 필요).

### 8. Notion 동기화
```
python tools/notion_sync.py --input .tmp/report_data_{date}.json --database-id $NOTION_DATABASE_ID
```
- 실패 시 1회 재시도. 계속 실패하면 `.tmp/report_data_{date}.json`을 보존해 나중에 수동 백필할 수 있게 한다.
- **중요**: 다음 날 급상승 랭킹(2단계) 계산의 기준값이 되므로, 이 단계가 반드시 성공해야 한다. 실패한 채로 넘어가면 다음날 성장률 계산에 어제 데이터가 비어서 그날은 조회수 누적 기준으로 대체된다 (자동 완화되지만, 며칠 연속 실패하면 사용자에게 보고).

### 9. 정리
`.tmp/`는 폐기 가능한 공간이다. 7일 지난 `candidates_*`/`trending_*`/`report_*`/`transcripts/*` 파일은 정리하되, 직전 실행분은 다음 실행 전까지 보관한다.

### 10. 보고
성공/실패 요약(수집 영상 수, 이메일 발송 여부, Notion 동기화 행 수)을 한 줄로 정리해 남긴다.

---

## Expected Output
- PDF 리포트 1부가 `REPORT_RECIPIENT_EMAIL`로 발송됨
- Notion `YouTube KR Trends` 데이터베이스에 10개 행 추가됨
- 실행 로그 한 줄 요약

## Error Handling Summary
| 단계 | 실패 시 |
|---|---|
| 후보 수집 | 1회 재시도 → 계속 실패 시 발송 없이 중단, 2일 연속 실패면 사용자 보고 |
| 급상승 랭킹 | Notion에 어제 데이터 없으면 자동으로 조회수 누적 기준 대체 (에러 아님) |
| 자막 | 영상 단위로만 "unavailable" 처리, 전체는 계속 진행 |
| PDF | Fix forward, 절대 스킵 금지 |
| 이메일 | 헤드리스 재인증 시도 안 함, 실패해도 Notion 동기화는 계속, 실패 사실 명확히 보고 |
| Notion | 1회 재시도 → 실패 시 데이터 보존 후 수동 백필 대기, 다음날 랭킹 계산에 영향 |

## One-time Setup (반복 워크플로우 아님, 별도 진행)
1. `.env`에 `YOUTUBE_API_KEY`, `NOTION_API_KEY`, `NOTION_PARENT_PAGE_ID`, `REPORT_RECIPIENT_EMAIL` 채우기
2. `python tools/notion_sync.py --setup --parent-page-id $NOTION_PARENT_PAGE_ID` 실행 → 출력된 database_id를 `.env`의 `NOTION_DATABASE_ID`에 채우기
3. Google Cloud OAuth 클라이언트(Desktop app) 다운로드 → `credentials.json`으로 저장
4. 로컬에서 `python tools/gmail_send.py --to ... --subject test --body-file ...` 1회 실행 → 브라우저 인증 → `token.json` 생성
5. 전체 워크플로우를 수동으로 1회 실행해 이메일/Notion 결과 확인 후에만 `schedule` 스킬로 매일 08:00 KST 등록 (등록 프롬프트: "workflows/daily_trend_report.md를 처음부터 끝까지 따라 실행")
