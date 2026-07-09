"""Fetch transcripts for videos listed in a youtube_fetch.py output JSON.

Never raises on a missing/disabled transcript for a single video - marks it
"unavailable" and continues, so one video's captions never blocks the run.

CLI:
    python tools/youtube_transcript.py --input .tmp/trending_20260709.json \\
        --output .tmp/trending_20260709.json --transcripts-dir .tmp/transcripts
"""
import argparse
import json
import os
import sys

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound, TranscriptsDisabled, VideoUnavailable,
)

EXPECTED_ERRORS = (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable)


def fetch_transcript(video_id, languages=("ko", "en")):
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=list(languages))
        text = " ".join(snippet.text for snippet in fetched)
        return {"available": True, "text": text}
    except EXPECTED_ERRORS as e:
        return {"available": False, "reason": type(e).__name__}
    except Exception as e:
        print(f"[warn] unexpected transcript error for {video_id}: {e}", file=sys.stderr)
        return {"available": False, "reason": "unexpected_error"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--transcripts-dir", default=".tmp/transcripts")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(args.transcripts_dir, exist_ok=True)
    for video in data["videos"]:
        result = fetch_transcript(video["video_id"])
        video["transcript_available"] = result["available"]
        if result["available"]:
            transcript_path = os.path.join(args.transcripts_dir, f"{video['video_id']}.txt")
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(result["text"])
            video["transcript_path"] = transcript_path
            video.pop("transcript_unavailable_reason", None)
        else:
            video["transcript_unavailable_reason"] = result["reason"]
            video.pop("transcript_path", None)
        print(f"[ok] {video['video_id']}: transcript {'available' if result['available'] else 'unavailable (' + result['reason'] + ')'}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[ok] wrote enriched data to {args.output}")


if __name__ == "__main__":
    main()
