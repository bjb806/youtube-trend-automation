"""Render a clean, no-frills PDF trend report from a report_data JSON.

Report data schema (assembled by Claude during the workflow, see
workflows/daily_trend_report.md step 4):
{
  "date": "2026-07-09", "region": "KR",
  "executive_summary": ["...", "..."],
  "videos": [{"rank":1, "title":.., "channel_name":.., "view_count":.., "like_count":..,
              "comment_count":.., "duration_sec":.., "format":.., "category":..,
              "video_url":.., "topic_tags":[..], "hook_style":.., "analysis_summary":..}, ...],
  "format_insights": ["...", "..."],
  "recommended_topics": [{"topic":.., "rationale":..}, ...]
}

Requires a Korean-capable Unicode TTF font (video titles/analysis are in Korean).
Set PDF_FONT_PATH in .env, or place a font at tools/assets/fonts/NotoSansKR-Regular.ttf
(e.g. https://fonts.google.com/noto/specimen/Noto+Sans+KR, SIL Open Font License).

CLI:
    python tools/pdf_report.py --input .tmp/report_data_20260709.json --output .tmp/report_20260709.pdf
"""
import argparse
import json
import os

from dotenv import load_dotenv
from fpdf import FPDF

load_dotenv()

ACCENT_COLOR = (60, 65, 75)      # muted slate
MUTED_COLOR = (120, 125, 135)
FONT_NAME = "NotoKR"


def resolve_font_path():
    candidates = [
        os.environ.get("PDF_FONT_PATH"),
        os.path.join(os.path.dirname(__file__), "assets", "fonts", "NotoSansKR-Regular.ttf"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "Korean-capable TTF font not found. Download a free font such as Noto Sans KR "
        "(https://fonts.google.com/noto/specimen/Noto+Sans+KR) and save it as "
        "tools/assets/fonts/NotoSansKR-Regular.ttf, or set PDF_FONT_PATH in .env."
    )


def build_pdf(data):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    font_path = resolve_font_path()
    pdf.add_font(FONT_NAME, "", font_path)
    pdf.add_font(FONT_NAME, "B", font_path)

    _add_cover(pdf, data)
    _add_summary(pdf, data)
    _add_video_table(pdf, data)
    _add_video_detail(pdf, data)
    _add_format_insights(pdf, data)
    _add_recommendations(pdf, data)
    _add_footer_note(pdf, data)
    return pdf


def _heading(pdf, text, size=16):
    pdf.set_font(FONT_NAME, "B", size)
    pdf.set_text_color(*ACCENT_COLOR)
    pdf.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _body(pdf, text, size=10):
    pdf.set_font(FONT_NAME, "", size)
    pdf.set_text_color(20, 20, 20)
    pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")


def _add_cover(pdf, data):
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font(FONT_NAME, "B", 26)
    pdf.set_text_color(*ACCENT_COLOR)
    title = data.get("report_title", "YouTube Korea Trend Report")
    pdf.cell(0, 14, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font(FONT_NAME, "", 12)
    pdf.set_text_color(*MUTED_COLOR)
    subtitle = data.get("report_subtitle", "Daily content intelligence brief")
    pdf.cell(0, 10, f"{subtitle} · {data['date']}", new_x="LMARGIN", new_y="NEXT", align="C")


def _add_summary(pdf, data):
    pdf.add_page()
    _heading(pdf, "Executive Summary")
    for bullet in data.get("executive_summary", []):
        _body(pdf, f"- {bullet}")
    pdf.ln(4)


def _fit_text(pdf, text, max_width, padding=4):
    available = max_width - padding
    if pdf.get_string_width(text) <= available:
        return text
    truncated = text
    while truncated and pdf.get_string_width(truncated + "...") > available:
        truncated = truncated[:-1]
    return truncated + "..."


def _add_video_table(pdf, data):
    _heading(pdf, "Top 10 Trending Videos", size=14)
    pdf.set_font(FONT_NAME, "B", 9)
    pdf.set_fill_color(235, 235, 238)
    headers = [("#", 8), ("Title", 78), ("Channel", 42), ("Views", 25), ("Format", 25)]
    for label, width in headers:
        pdf.cell(width, 8, label, border=1, fill=True)
    pdf.ln()
    pdf.set_font(FONT_NAME, "", 9)
    for video in data.get("videos", []):
        pdf.cell(8, 8, str(video["rank"]), border=1)
        pdf.cell(78, 8, _fit_text(pdf, video["title"], 78), border=1)
        pdf.cell(42, 8, _fit_text(pdf, video["channel_name"], 42), border=1)
        pdf.cell(25, 8, f"{video['view_count']:,}", border=1)
        pdf.cell(25, 8, video["format"], border=1)
        pdf.ln()
    pdf.ln(4)


def _add_video_detail(pdf, data):
    pdf.add_page()
    _heading(pdf, "Per-Video Breakdown", size=14)
    for video in data.get("videos", []):
        pdf.set_font(FONT_NAME, "B", 11)
        pdf.set_text_color(20, 20, 20)
        pdf.multi_cell(0, 7, f"{video['rank']}. {video['title']} — {video['channel_name']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(FONT_NAME, "", 9)
        pdf.set_text_color(*MUTED_COLOR)
        stats = f"{video['view_count']:,} views · {video['duration_sec']}s · {video['category']} · {video['format']}"
        pdf.multi_cell(0, 6, stats, new_x="LMARGIN", new_y="NEXT")
        _body(pdf, video.get("analysis_summary", ""))
        tags = ", ".join(video.get("topic_tags", []))
        if tags:
            _body(pdf, f"Tags: {tags}", size=9)
        pdf.ln(3)


def _add_format_insights(pdf, data):
    pdf.add_page()
    _heading(pdf, "Format & Style Insights", size=14)
    for insight in data.get("format_insights", []):
        _body(pdf, f"- {insight}")
    pdf.ln(4)


def _add_recommendations(pdf, data):
    _heading(pdf, "This Week's Recommended Content Topics", size=14)
    for rec in data.get("recommended_topics", []):
        pdf.set_font(FONT_NAME, "B", 11)
        pdf.set_text_color(20, 20, 20)
        pdf.multi_cell(0, 7, rec["topic"], new_x="LMARGIN", new_y="NEXT")
        _body(pdf, rec["rationale"])
        pdf.ln(2)


def _add_footer_note(pdf, data):
    pdf.set_font(FONT_NAME, "", 8)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.multi_cell(0, 5, f"Source: YouTube Data API v3, region={data.get('region', 'KR')} · "
                          f"Generated {data.get('generated_at', data['date'])}",
                   new_x="LMARGIN", new_y="NEXT")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    pdf = build_pdf(data)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    pdf.output(args.output)
    print(f"[ok] wrote PDF to {args.output}")


if __name__ == "__main__":
    main()
