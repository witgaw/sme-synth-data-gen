#!/usr/bin/env python3
"""
Generate realistic files from documents.json

Reads the canonical JSON and creates actual .eml, .docx, .xlsx, .pptx, .md files
in the output/ directory.

Usage:
    uv run generate [--output-dir OUTPUT_DIR]

Or without uv:
    pip install python-docx openpyxl python-pptx
    python scripts/generate_files.py
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

# Optional dependencies - graceful fallback if not installed
try:
    from docx import Document

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

try:
    from pptx import Presentation

    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False


def generate_eml(doc: dict, output_dir: Path) -> Path:
    """Generate RFC 822 .eml file"""
    dt = datetime.fromisoformat(doc["timestamp"])
    date_str = dt.strftime("%a, %d %b %Y %H:%M:%S %z")

    to_list = ", ".join([f"{r['name']} <{r['email']}>" for r in doc["recipients"]])
    cc_list = ", ".join([f"{r['name']} <{r['email']}>" for r in doc.get("cc", [])])

    eml_content = f"""From: {doc["author"]} <{doc["author_email"]}>
To: {to_list}
{"Cc: " + cc_list if cc_list else ""}Date: {date_str}
Subject: {doc["subject"]}
Content-Type: text/plain; charset=utf-8
MIME-Version: 1.0

{doc["body"]}
"""

    filepath = output_dir / doc["filename"]
    filepath.write_text(eml_content, encoding="utf-8")
    return filepath


def generate_md(doc: dict, output_dir: Path) -> Path:
    """Generate markdown file"""
    content = f"# {doc['title']}\n\n"
    content += f"**Author:** {doc['author']}\n"
    content += f"**Date:** {doc['timestamp']}\n\n"

    if "attendees" in doc:
        content += f"**Attendees:** {', '.join(doc['attendees'])}\n"
    if "location" in doc:
        content += f"**Location:** {doc['location']}\n"

    content += "\n---\n\n"
    content += doc.get("content", "")

    if "action_items" in doc:
        content += "\n\n## Action Items\n\n"
        for item in doc["action_items"]:
            content += f"- [ ] {item['task']} ({item['owner']}, due: {item['due']})\n"

    filepath = output_dir / doc["filename"]
    filepath.write_text(content, encoding="utf-8")
    return filepath


def generate_docx(doc: dict, output_dir: Path) -> Path:
    """Generate .docx file"""
    if not HAS_DOCX:
        print(f"  Skipping {doc['filename']} - python-docx not installed")
        return None

    document = Document()
    document.add_heading(doc["title"], 0)

    meta = document.add_paragraph()
    meta.add_run(f"Autor: {doc['author']}\n").italic = True
    dt = datetime.fromisoformat(doc["timestamp"])
    meta.add_run(f"Data: {dt.strftime('%d %B %Y')}").italic = True

    for section in doc.get("sections", []):
        document.add_heading(section["heading"], level=1)
        document.add_paragraph(section["content"])

    filepath = output_dir / doc["filename"]
    document.save(str(filepath))
    return filepath


def generate_xlsx(doc: dict, output_dir: Path) -> Path:
    """Generate .xlsx file"""
    if not HAS_XLSX:
        print(f"  Skipping {doc['filename']} - openpyxl not installed")
        return None

    wb = Workbook()
    wb.remove(wb.active)

    for sheet_data in doc.get("sheets", []):
        ws = wb.create_sheet(title=sheet_data["name"][:31])

        # Header row
        for col, header in enumerate(sheet_data["columns"], 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

        # Data rows
        for row_idx, row_data in enumerate(sheet_data["rows"], 2):
            for col_idx, value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=value)

    filepath = output_dir / doc["filename"]
    wb.save(str(filepath))
    return filepath


def generate_pptx(doc: dict, output_dir: Path) -> Path:
    """Generate .pptx file"""
    if not HAS_PPTX:
        print(f"  Skipping {doc['filename']} - python-pptx not installed")
        return None

    prs = Presentation()

    for slide_data in doc.get("slides", []):
        if slide_data.get("type") == "title":
            slide_layout = prs.slide_layouts[0]
            slide = prs.slides.add_slide(slide_layout)
            slide.shapes.title.text = slide_data["title"]
            if "subtitle" in slide_data:
                slide.placeholders[1].text = slide_data["subtitle"]
        else:
            slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(slide_layout)
            slide.shapes.title.text = slide_data["title"]

            if "bullets" in slide_data:
                body = slide.placeholders[1]
                tf = body.text_frame
                tf.text = slide_data["bullets"][0]
                for bullet in slide_data["bullets"][1:]:
                    p = tf.add_paragraph()
                    p.text = bullet
                    p.level = 0
            elif "content" in slide_data:
                body = slide.placeholders[1]
                body.text = slide_data["content"]

    filepath = output_dir / doc["filename"]
    prs.save(str(filepath))
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Generate files from documents.json")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory")
    parser.add_argument("--input", "-i", default="dataset/documents.json", help="Input JSON file")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Generating {len(data['documents'])} files to {output_dir}/")

    generated = 0
    skipped = 0

    for doc in data["documents"]:
        doc_type = doc["type"]
        fmt = doc.get("format", "")

        try:
            if fmt == "eml" or "email" in doc_type:
                generate_eml(doc, output_dir)
            elif fmt == "md" or doc_type in ["meeting_notes", "project_kickoff"]:
                generate_md(doc, output_dir)
            elif fmt == "docx" or doc_type in [
                "report_quarterly",
                "report_monthly",
                "report_project",
                "proposal",
            ]:
                result = generate_docx(doc, output_dir)
                if result is None:
                    skipped += 1
                    continue
            elif fmt == "xlsx" or "spreadsheet" in doc_type:
                result = generate_xlsx(doc, output_dir)
                if result is None:
                    skipped += 1
                    continue
            elif fmt == "pptx" or "presentation" in doc_type:
                result = generate_pptx(doc, output_dir)
                if result is None:
                    skipped += 1
                    continue
            else:
                print(f"  Unknown format for {doc['id']}: {doc_type}/{fmt}")
                skipped += 1
                continue

            generated += 1
            print(f"  {doc['id']}: {doc['filename']}")

        except Exception as e:
            print(f"  Error generating {doc['id']}: {e}")
            skipped += 1

    print(f"\nDone: {generated} generated, {skipped} skipped")


if __name__ == "__main__":
    main()
