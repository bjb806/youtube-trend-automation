"""Fetch KR celebrity shopping-recommendation Shorts via keyword search.

There's no official YouTube chart for this niche, so this searches a set of
Korean keyword phrases, keeps only videos that are actually Shorts (<=60s),
and ranks the merged candidate pool by view count.

CLI:
    python tools/shopping_shorts_fetch.py --region KR --top 30 --output .tmp/shopping_candidates_20260709.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from youtube_fetch import CATEGORY_NAMES, parse_duration_seconds

load_dotenv()

KEYWORDS = [
    "연예인 추천템", "연예인 애용템", "연예인 인생템",
    "연예인 PICK", "연예인 내돈내산", "스타일리스트 추천",
    "연예인 협찬", "연예인 광고", "연예인 착용템",
]


def search_keyword(youtube, keyword, region, days, max_results=25):
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        response = youtube.search().list(
            part="id", q=keyword, type="video", order="viewCount", regionCode=region,
            publishedAfter=published_after, maxResults=max_results,
        ).execute()
    except HttpError as e:
        print(f"[warn] search failed for '{keyword}': {e}", file=sys.stderr)
        return []
    return [item["id"]["videoId"] for item in response.get("items", [])]


def get_video_details(youtube, video_ids):
    details = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        response = youtube.videos().list(part="snippet,statistics,contentDetails", id=",".join(batch)).execute()
        for item in response.get("items", []):
            details[item["id"]] = item
    return details


def build_candidates(details, matched_keywords, top_n):
    candidates = []
    for video_id, item in details.items():
        snippet, stats, content = item["snippet"], item.get("statistics", {}), item["contentDetails"]
        duration_sec = parse_duration_seconds(content.get("duration"))
        if duration_sec > 60:
            continue  # only real Shorts
        candidates.append({
            "video_id": video_id,
            "title": snippet["title"],
            "channel_name": snippet["channelTitle"],
            "channel_id": snippet["channelId"],
            "published_at": snippet["publishedAt"],
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration_sec": duration_sec,
            "format": "Shorts",
            "category": CATEGORY_NAMES.get(snippet.get("categoryId"), "Other"),
            "source": "KeywordSearch",
            "matched_keywords": sorted(matched_keywords.get(video_id, [])),
            "thumbnail_url": snippet["thumbnails"].get("high", snippet["thumbnails"]["default"])["url"],
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
        })
    candidates.sort(key=lambda v: v["view_count"], reverse=True)
    top = candidates[:top_n]
    for rank, video in enumerate(top, start=1):
        video["rank"] = rank
    return top


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="KR")
    parser.add_argument("--days", type=int, default=21, help="only consider videos published in the last N days")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("[error] YOUTUBE_API_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)

    youtube = build("youtube", "v3", developerKey=api_key)

    matched_keywords = {}
    for keyword in KEYWORDS:
        for video_id in search_keyword(youtube, keyword, args.region, args.days):
            matched_keywords.setdefault(video_id, set()).add(keyword)

    if not matched_keywords:
        print("[error] no candidates found for any keyword, aborting", file=sys.stderr)
        sys.exit(1)

    details = get_video_details(youtube, list(matched_keywords))
    top_videos = build_candidates(details, matched_keywords, args.top)

    if not top_videos:
        print("[error] no Shorts (<=60s) among search results, aborting", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"region": args.region, "collected_at": datetime.now(timezone.utc).isoformat(),
                   "keywords": KEYWORDS, "videos": top_videos}, f, ensure_ascii=False, indent=2)
    print(f"[ok] wrote {len(top_videos)} Shorts candidates to {args.output}")


if __name__ == "__main__":
    main()
