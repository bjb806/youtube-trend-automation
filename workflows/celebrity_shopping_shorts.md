# Celebrity Shopping Shorts Report (매일 08:00 KST)

## Goal
유튜브 한국(KR)의 "연예인 쇼핑 추천템" 인기 쇼츠(실제 재생시간 60초 이하) Top 10을 키워드 검색으로 수집·분석해서 PDF 리포트를 만들고, 본인(`REPORT_RECIPIENT_EMAIL` 환경변수의 주소)에게 이메일로 발송하고, 모든 데이터를 별도 Notion 데이터베이스에 누적 저장한다.

`workflows/daily_trend_report.md`(일반 트렌드 리포트)와 같은 시간에 별도로 실행되는 독립적인 리포트다. `tools/`의 PDF/이메일/노션/반복제외 로직은 공유하되, 수집 방식과 데이터가 다르다.

## Inputs
환경변수(클라우드 환경설정에 등록됨): `YOUTUBE_API_KEY`, `NOTION_API_KEY`, `NOTION_SHOPPING_DATABASE_ID`, `REPORT_RECIPIENT_EMAIL`, `GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON`

사용자로부터 받는 입력은 없음. 실행일 기준 날짜를 `{date}` (YYYY-MM-DD)로 사용.

### 0. 실행 환경 준비 (매 실행 시)
`daily_trend_report.md`와 동일하게:
```
pip install -r requirements.txt
```
`{date}`는 반드시 `TZ=Asia/Seoul date +%Y-%m-%d`로 계산한다 (클라우드 sandbox 시계는 UTC라 그냥 `date`를 쓰면 하루 밀린다 - 이유는 `daily_trend_report.md` step 0 참고).

---

## Steps

### 1. 키워드 검색으로 쇼츠 후보 수집
```
python tools/shopping_shorts_fetch.py --region KR --days 14 --top 30 --output .tmp/shopping_candidates_{date}.json
```
- 이 카테고리는 유튜브 공식 차트가 없어서 키워드 검색으로 찾는다: "연예인 추천템", "연예인 애용템", "연예인 인생템", "연예인 PICK", "연예인 내돈내산", "스타일리스트 추천" (`tools/shopping_shorts_fetch.py`의 `KEYWORDS` 참고).
- 검색 결과 중 실제 재생시간 60초 이하(진짜 쇼츠)만 후보로 남긴다.
- 광고/PPL 표시 영상도 현재는 그대로 포함한다 (사용자가 나중에 제외 요청 가능 - 그때 필터 추가).
- API 오류 시 1회 재시도. 계속 실패하면 발송 없이 중단하고 로그만 남긴다. 2일 연속 실패 시 사용자에게 보고.

### 2. 최근 7일 반복 제외 후 Top 10 선정
```
python tools/rank_by_growth.py --input .tmp/shopping_candidates_{date}.json --date {date} --database-id $NOTION_SHOPPING_DATABASE_ID --top 10 --exclude-days 7 --output .tmp/shopping_trending_{date}.json
```
- `daily_trend_report.md`와 동일한 툴/로직을 재사용한다 (최근 7일 내 이미 실린 영상 제외 → 남은 후보 조회수 순 정렬).
- **주의**: `--database-id`는 반드시 `$NOTION_SHOPPING_DATABASE_ID`를 넘겨야 한다 (일반 트렌드 DB와 섞이면 안 됨).

### 3. 자막 추출
```
python tools/youtube_transcript.py --input .tmp/shopping_trending_{date}.json --output .tmp/shopping_trending_{date}.json --transcripts-dir .tmp/shopping_transcripts
```
- `youtube-transcript-api`는 비공식 스크래핑 방식이라 IP 차단으로 실패할 수 있다 (흔함). 실패해도 전체는 계속 진행하고, 제목/설명 기반으로 분석한다.

### 4. 분석 (Claude가 직접 수행, 툴 없음)
`.tmp/shopping_trending_{date}.json`의 각 영상(제목, 통계, 자막/설명, `matched_keywords`)을 읽고 직접 판단한다:
- 영상별: 2-3문장 요약(`analysis_summary`), 훅 스타일(`hook_style`), 주제 태그(`topic_tags`, 2-4개 — 제품 카테고리 위주: 뷰티/패션/주방/간식/인테리어 등)
- 전체: 3-5개 크로스 비디오 테마, 포맷/스타일 인사이트(`format_insights` — 예: 큐레이션 채널 비중, 커머스 연동 해시태그 비중 등)
- 이번 주 추천 콘텐츠 주제 3-5개, 각각 한 줄 근거(`recommended_topics`) — 가능하면 `video_ids` 포함

### 5. 리포트 데이터 조립
아래 스키마로 `.tmp/shopping_report_data_{date}.json`을 작성한다 (`daily_trend_report.md`의 report_data 스키마와 동일 + 리포트 제목 커스터마이징):
```json
{
  "date": "YYYY-MM-DD",
  "region": "KR",
  "report_title": "Celebrity Shopping Shorts Report",
  "report_subtitle": "Daily celebrity-recommended product Shorts brief",
  "generated_at": "ISO8601 timestamp",
  "executive_summary": ["...", "..."],
  "videos": [ /* daily_trend_report.md와 동일한 필드 구조 */ ],
  "format_insights": ["...", "..."],
  "recommended_topics": [{"topic": "...", "rationale": "...", "video_ids": ["..."]}]
}
```

### 6. PDF 생성
```
python tools/pdf_report.py --input .tmp/shopping_report_data_{date}.json --output .tmp/shopping_report_{date}.pdf
```
- `report_title`/`report_subtitle`을 표지에 자동 반영한다 (`pdf_report.py`가 이 필드를 읽음). 실패 시 fix forward, 절대 스킵 금지.

### 7. 이메일 발송
```
python tools/gmail_send.py --to $REPORT_RECIPIENT_EMAIL --subject "Celebrity Shopping Shorts Report - {date}" --body-file .tmp/shopping_email_body_{date}.txt --attachment .tmp/shopping_report_{date}.pdf
```
- 본문에 핵심 요약 3줄 + Top 10 제목·링크 목록 포함 (daily_trend_report.md 7단계와 동일한 형식).
- 헤드리스 재인증 시도 안 함. 실패해도 8단계는 계속 진행, 실패 사실 명확히 보고.

### 8. Notion 동기화
```
python tools/notion_sync.py --input .tmp/shopping_report_data_{date}.json --database-id $NOTION_SHOPPING_DATABASE_ID
```
- **중요**: 앞으로 7일간 반복 제외 판정의 기준 데이터가 되므로 반드시 성공해야 한다. 실패 시 1회 재시도, 계속 실패하면 데이터 보존 후 수동 백필.

### 9. 정리
`.tmp/`의 `shopping_*` 파일들도 7일 지나면 정리, 직전 실행분은 보관.

### 10. 보고
성공/실패 요약(수집 영상 수, 이메일 발송 여부, Notion 동기화 행 수)을 한 줄로 정리해 남긴다.

---

## Expected Output
- PDF 리포트 1부가 `REPORT_RECIPIENT_EMAIL`로 발송됨
- Notion "Shopping Shorts Trends" 데이터베이스에 10개 행 추가됨
- 실행 로그 한 줄 요약

## Error Handling Summary
| 단계 | 실패 시 |
|---|---|
| 후보 수집(키워드 검색) | 1회 재시도 → 계속 실패 시 발송 없이 중단, 2일 연속 실패면 사용자 보고 |
| 반복 제외 랭킹 | 제외 후 10개 미만이면 조회수 높은 반복 영상으로 자동 백필 (에러 아님) |
| 자막 | 영상 단위로만 "unavailable" 처리 (IP 차단으로 흔함), 전체는 계속 진행 |
| PDF | Fix forward, 절대 스킵 금지 |
| 이메일 | 헤드리스 재인증 시도 안 함, 실패해도 Notion 동기화는 계속, 실패 사실 명확히 보고 |
| Notion | 1회 재시도 → 실패 시 데이터 보존 후 수동 백필 대기 |

## One-time Setup (이미 완료됨, 참고용)
1. `.env`/클라우드 환경변수에 `NOTION_SHOPPING_DATABASE_ID` 추가 (기존 `NOTION_PARENT_PAGE_ID` 페이지 아래 새 데이터베이스로 생성, 기존 통합 재사용이라 별도 공유 작업 불필요)
2. `python tools/notion_sync.py --setup --parent-page-id $NOTION_PARENT_PAGE_ID --title "Shopping Shorts Trends"` 로 생성
3. 나머지 자격증명(YouTube/Gmail)은 `daily_trend_report.md`와 동일하게 재사용
4. `schedule` 스킬로 별도 클라우드 라우틴을 매일 08:00 KST에 등록 (등록 프롬프트: "workflows/celebrity_shopping_shorts.md를 처음부터 끝까지 따라 실행")
