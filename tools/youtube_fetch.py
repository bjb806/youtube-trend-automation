"""Fetch KR trending YouTube videos: category mostPopular charts + view-count surge search.

CLI:
    python tools/youtube_fetch.py --region KR --top 10 --output .tmp/trending_20260709.json
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

CATEGORY_NAMES = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "19": "Travel & Events",
    "20": "Gaming", "22": "People & Blogs", "23": "Comedy",
    "24": "Entertainment", "25": "News & Politics", "26": "Howto & Style",
    "27": "Education", "28": "Science & Technology", "30": "Movies", "43": "Shows",
}
MOST_POPULAR_CATEGORY_IDS = [None, "10", "20", "24"]  # general + Music/Gaming/Entertainment
DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_duration_seconds(iso_duration):
    match = DURATION_RE.fullmatch(iso_duration or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def map_category(category_id, surge_only):
    name = CATEGORY_NAMES.get(category_id)
    if name:
        return name
    return "Cross-category Surge" if surge_only else "Other"


def fetch_most_popular(youtube, region):
    videos = {}
    for category_id in MOST_POPULAR_CATEGORY_IDS:
        params = {"part": "snippet,statistics,contentDetails", "chart": "mostPopular",
                   "regionCode": region, "maxResults": 25}
        if category_id:
            params["videoCategoryId"] = category_id
        try:
            response = youtube.videos().list(**params).execute()
        except HttpError as e:
            print(f"[warn] mostPopular fetch failed (category={category_id}): {e}", file=sys.stderr)
            continue
        for item in response.get("items", []):
            videos[item["id"]] = item
    return videos


def fetch_view_surge(youtube, region, hours=48, max_results=25):
    published_after = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        search_response = youtube.search().list(
            part="id", type="video", order="viewCount", regionCode=region,
            publishedAfter=published_after, maxResults=max_results,
        ).execute()
    except HttpError as e:
        print(f"[warn] view-count surge search failed: {e}", file=sys.stderr)
        return {}
    ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
    if not ids:
        return {}
    details = youtube.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids)).execute()
    return {item["id"]: item for item in details.get("items", [])}


def merge_and_rank(most_popular, surge, top_n):
    all_ids = set(most_popular) | set(surge)
    merged = []
    for video_id in all_ids:
        item = most_popular.get(video_id) or surge.get(video_id)
        in_most_popular = video_id in most_popular
        in_surge = video_id in surge
        source = "Both" if in_most_popular and in_surge else ("MostPopular" if in_most_popular else "ViewCountSurge")
        snippet, stats, content = item["snippet"], item.get("statistics", {}), item["contentDetails"]
        merged.append({
            "video_id": video_id,
            "title": snippet["title"],
            "channel_name": snippet["channelTitle"],
            "channel_id": snippet["channelId"],
            "published_at": snippet["publishedAt"],
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration_sec": parse_duration_seconds(content.get("duration")),
            "category": map_category(snippet.get("categoryId"), surge_only=not in_most_popular),
            "source": source,
            "thumbnail_url": snippet["thumbnails"].get("high", snippet["thumbnails"]["default"])["url"],
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
        })
    merged.sort(key=lambda v: v["view_count"], reverse=True)
    top = merged[:top_n]
    for rank, video in enumerate(top, start=1):
        video["rank"] = rank
        video["format"] = "Shorts" if video["duration_sec"] <= 60 else "Long-form"
    return top


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="KR")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("[error] YOUTUBE_API_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)

    youtube = build("youtube", "v3", developerKey=api_key)
    most_popular = fetch_most_popular(youtube, args.region)
    surge = fetch_view_surge(youtube, args.region)
    top_videos = merge_and_rank(most_popular, surge, args.top)

    if not top_videos:
        print("[error] no videos fetched, aborting", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"region": args.region, "collected_at": datetime.now(timezone.utc).isoformat(),
                    "videos": top_videos}, f, ensure_ascii=False, indent=2)
    print(f"[ok] wrote {len(top_videos)} videos to {args.output}")


if __name__ == "__main__":
    main()
