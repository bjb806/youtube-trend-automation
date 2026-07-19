"""Pick today's Top N from the candidate pool, excluding anything that already
appeared in the Top 10 within the last EXCLUDE_DAYS days.

Repeats aren't useful for content-idea research - if a video was already
surfaced recently, seeing it again tomorrow doesn't tell the user anything
new, no matter how much it's still growing. So instead of a soft "growth"
score, this does a hard exclusion: look up every video id that appeared in
Notion in the last N days, drop those from the candidate pool, then rank
whatever's left by raw view count (already-excluded candidates can't have
"yesterday" data anyway, since yesterday falls inside the exclusion window).

If exclusion leaves fewer than --top candidates, the default is to backfill
with the highest-view excluded ones so the report still has a full Top N.
Pass --no-backfill to skip this and just return fewer than --top instead -
appropriate for narrow candidate pools (e.g. keyword-search-based fetches)
where backfilling ends up reintroducing the same repeats constantly instead
of being a rare edge case.

CLI:
    python tools/rank_by_growth.py --input .tmp/candidates_20260709.json \\
        --date 2026-07-09 --database-id $NOTION_DATABASE_ID --top 10 \\
        --exclude-days 7 --output .tmp/trending_20260709.json
"""
import argparse
import json
from datetime import datetime, timedelta

from notion_sync import get_recent_video_ids


def select_top(videos, recent_ids, top_n, allow_backfill=True):
    fresh = [v for v in videos if v["video_id"] not in recent_ids]
    repeats = [v for v in videos if v["video_id"] in recent_ids]
    fresh.sort(key=lambda v: v["view_count"], reverse=True)
    repeats.sort(key=lambda v: v["view_count"], reverse=True)

    top = fresh[:top_n]
    for video in top:
        video["repeat"] = False
    if allow_backfill and len(top) < top_n:
        backfill = repeats[: top_n - len(top)]
        for video in backfill:
            video["repeat"] = True
        top += backfill
    return top


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--date", required=True, help="today's date, YYYY-MM-DD (unused directly, kept for workflow consistency)")
    parser.add_argument("--database-id", required=True)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--exclude-days", type=int, default=7)
    parser.add_argument("--no-backfill", action="store_true", help="don't top up with repeats if fresh candidates run short")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    since_date = (datetime.strptime(args.date, "%Y-%m-%d") - timedelta(days=args.exclude_days)).strftime("%Y-%m-%d")
    recent_ids = get_recent_video_ids(args.database_id, since_date)

    top = select_top(data["videos"], recent_ids, args.top, allow_backfill=not args.no_backfill)
    for rank, video in enumerate(top, start=1):
        video["rank"] = rank

    data["videos"] = top
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    backfilled = sum(1 for v in top if v.get("repeat"))
    print(f"[ok] excluded videos seen since {since_date}, kept top {len(top)} "
          f"({backfilled} backfilled repeats, {'disabled' if args.no_backfill else 'enabled'}) -> {args.output}")


if __name__ == "__main__":
    main()
