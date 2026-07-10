"""Bootstrap the Notion trend database (one-time) and append daily entries.

One-time setup:
    python tools/notion_sync.py --setup --parent-page-id <page_id>
    -> prints the new database_id; paste it into .env as NOTION_DATABASE_ID

Daily sync:
    python tools/notion_sync.py --input .tmp/report_data_20260709.json --database-id $NOTION_DATABASE_ID
"""
import argparse
import json
import os
import re
import sys

from dotenv import load_dotenv
from notion_client import Client

VIDEO_ID_RE = re.compile(r"v=([\w-]+)")

load_dotenv()

DATABASE_TITLE = "YouTube Trends"

SCHEMA = {
    "Name": {"title": {}},
    "Date": {"date": {}},
    "Channel Name": {"rich_text": {}},
    "View Count": {"number": {}},
    "Video URL": {"url": {}},
    "Published At": {"date": {}},
    "Format": {"select": {}},
    "Category": {"select": {}},
    "Rank": {"number": {}},
    "Hook Style": {"rich_text": {}},
    "Analysis Summary": {"rich_text": {}},
}


def get_client():
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        print("[error] NOTION_API_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)
    return Client(auth=api_key)


def create_database(parent_page_id):
    """Notion's API splits a database (container) from its data source (the
    actual property schema + rows). Properties must go on initial_data_source,
    not on the database itself - and writes target the data source id, not
    the database id."""
    notion = get_client()
    response = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": DATABASE_TITLE}}],
        initial_data_source={"properties": SCHEMA},
    )
    data_source_id = response["data_sources"][0]["id"]
    print(f"[ok] created database '{DATABASE_TITLE}' (database_id={response['id']})")
    print(f"[ok] data_source_id (use this as NOTION_DATABASE_ID): {data_source_id}")
    return data_source_id


def video_to_properties(date, video):
    return {
        "Name": {"title": [{"text": {"content": video["title"]}}]},
        "Date": {"date": {"start": date}},
        "Channel Name": {"rich_text": [{"text": {"content": video["channel_name"]}}]},
        "View Count": {"number": video["view_count"]},
        "Video URL": {"url": video.get("video_url") or None},
        "Published At": {"date": {"start": video["published_at"]}},
        "Format": {"select": {"name": video["format"]}},
        "Category": {"select": {"name": video["category"]}},
        "Rank": {"number": video["rank"]},
        "Hook Style": {"rich_text": [{"text": {"content": video.get("hook_style", "")}}]},
        "Analysis Summary": {"rich_text": [{"text": {"content": video.get("analysis_summary", "")}}]},
    }


def get_video_views_by_date(data_source_id, date):
    """Returns {video_id: view_count} for entries logged on the given date,
    matched by parsing the video id out of the stored Video URL (there's no
    dedicated Video ID column in this schema)."""
    notion = get_client()
    results = notion.data_sources.query(
        data_source_id=data_source_id,
        filter={"property": "Date", "date": {"equals": date}},
    )["results"]
    views = {}
    for page in results:
        url = page["properties"]["Video URL"]["url"]
        view_count = page["properties"]["View Count"]["number"]
        match = VIDEO_ID_RE.search(url or "")
        if match:
            views[match.group(1)] = view_count
    return views


def append_daily_entries(data_source_id, data):
    notion = get_client()
    date = data["date"]
    created = 0
    for video in data.get("videos", []):
        properties = video_to_properties(date, video)
        try:
            notion.pages.create(parent={"type": "data_source_id", "data_source_id": data_source_id}, properties=properties)
            created += 1
        except Exception as e:
            print(f"[warn] failed to sync video {video['video_id']}: {e}", file=sys.stderr)
    print(f"[ok] synced {created}/{len(data.get('videos', []))} videos to Notion")
    return created


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="one-time: create the database")
    parser.add_argument("--parent-page-id", help="required with --setup")
    parser.add_argument("--input", help="report_data JSON for daily sync")
    parser.add_argument("--database-id", help="target database id for daily sync")
    args = parser.parse_args()

    if args.setup:
        if not args.parent_page_id:
            print("[error] --parent-page-id is required with --setup", file=sys.stderr)
            sys.exit(1)
        create_database(args.parent_page_id)
        return

    if not args.input or not args.database_id:
        print("[error] --input and --database-id are required for daily sync", file=sys.stderr)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    created = append_daily_entries(args.database_id, data)
    if created == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
