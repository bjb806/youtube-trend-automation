"""Re-rank candidate videos by view-count growth since yesterday, instead of
raw cumulative view count - so a perennially popular video can't camp in the
Top 10 forever just by having a high total; today's actual surge wins.

Looks up yesterday's view counts from the Notion database (populated by the
previous day's run). A video not seen yesterday (brand new to the chart)
counts its full view_count as growth, so genuinely new videos still surface.
On the very first run (no prior Notion data at all), everything falls back
to ranking by raw view_count, same as before.

CLI:
    python tools/rank_by_growth.py --input .tmp/candidates_20260709.json \\
        --date 2026-07-09 --database-id $NOTION_DATABASE_ID --top 10 \\
        --output .tmp/trending_20260709.json
"""
import argparse
import json
from datetime import datetime, timedelta

from notion_sync import get_video_views_by_date


def compute_growth(videos, previous_views):
    for video in videos:
        prior = previous_views.get(video["video_id"])
        video["previous_view_count"] = prior
        video["view_growth"] = video["view_count"] - prior if prior is not None else video["view_count"]
    return videos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--date", required=True, help="today's date, YYYY-MM-DD")
    parser.add_argument("--database-id", required=True)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    yesterday = (datetime.strptime(args.date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    previous_views = get_video_views_by_date(args.database_id, yesterday)

    videos = compute_growth(data["videos"], previous_views)
    videos.sort(key=lambda v: v["view_growth"], reverse=True)
    top = videos[: args.top]
    for rank, video in enumerate(top, start=1):
        video["rank"] = rank

    data["videos"] = top
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    new_count = sum(1 for v in top if v["previous_view_count"] is None)
    print(f"[ok] ranked {len(videos)} candidates by growth vs {yesterday}, "
          f"kept top {len(top)} ({new_count} new-to-chart) -> {args.output}")


if __name__ == "__main__":
    main()
