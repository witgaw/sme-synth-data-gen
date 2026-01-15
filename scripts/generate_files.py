#!/usr/bin/env python3
"""
Generate realistic files from documents.json

Reads the canonical JSON and creates actual .eml, .docx, .xlsx, .pptx, .md files
in the output/ directory. Optionally generates scanned-style PDFs for OCR testing.

Usage:
    uv run generate [--output-dir OUTPUT_DIR] [--include-pdf]

Or without uv:
    pip install python-docx openpyxl python-pptx
    python scripts/generate_files.py

For PDF generation:
    uv sync --extra pdf
    uv run generate --include-pdf
"""

import argparse
import json
import random
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

# PDF dependencies
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

try:
    from PIL import Image, ImageFilter

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import fitz  # pymupdf

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

HAS_PDF = HAS_REPORTLAB and HAS_PIL and HAS_PYMUPDF


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


def generate_pdf_easy(doc: dict, output_dir: Path) -> Path:
    """Generate clean, OCR-friendly PDF"""
    if not HAS_REPORTLAB:
        print(f"  Skipping {doc['filename']} - reportlab not installed")
        return None

    filepath = output_dir / doc["filename"]

    # Create PDF with reportlab
    pdf_doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles for Polish text
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=20,
        fontName="Helvetica-Bold",
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        fontName="Helvetica",
    )

    story = []

    # Add title
    title = doc.get("title", doc.get("filename", "Dokument"))
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 12))

    # Add content - handle Polish characters by escaping XML entities
    content = doc.get("content", "")
    # Replace problematic characters for XML
    content = content.replace("&", "&amp;")
    content = content.replace("<", "&lt;")
    content = content.replace(">", "&gt;")
    # Convert newlines to HTML breaks for proper rendering
    content = content.replace("\n", "<br/>")

    story.append(Paragraph(content, body_style))

    pdf_doc.build(story)
    return filepath


def apply_scan_effects(img: Image.Image, difficulty: str = "hard") -> Image.Image:
    """Apply scan/degradation effects to an image"""
    # Convert to RGB if necessary
    if img.mode != "RGB":
        img = img.convert("RGB")

    width, height = img.size

    # Rotation (slight for all hard PDFs)
    if difficulty == "hard":
        angle = random.uniform(-2.5, 2.5)
        img = img.rotate(angle, expand=True, fillcolor=(255, 255, 255))

    # Add noise
    if difficulty == "hard":
        import numpy as np

        img_array = np.array(img)
        noise = np.random.normal(0, random.uniform(5, 15), img_array.shape).astype(np.int16)
        img_array = np.clip(img_array.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(img_array)

    # Slight blur
    if difficulty == "hard":
        blur_radius = random.uniform(0.3, 0.8)
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Contrast/brightness adjustment
    if difficulty == "hard":
        from PIL import ImageEnhance

        # Reduce contrast slightly
        contrast = ImageEnhance.Contrast(img)
        img = contrast.enhance(random.uniform(0.85, 1.0))

        # Adjust brightness
        brightness = ImageEnhance.Brightness(img)
        img = brightness.enhance(random.uniform(0.9, 1.05))

    return img


def generate_pdf_hard(doc: dict, output_dir: Path) -> Path:
    """Generate scanned-style PDF with degradation effects"""
    if not HAS_PDF:
        missing = []
        if not HAS_REPORTLAB:
            missing.append("reportlab")
        if not HAS_PIL:
            missing.append("Pillow")
        if not HAS_PYMUPDF:
            missing.append("pymupdf")
        print(f"  Skipping {doc['filename']} - missing: {', '.join(missing)}")
        return None

    # First generate a clean PDF
    temp_pdf_path = output_dir / f"_temp_{doc['filename']}"

    pdf_doc = SimpleDocTemplate(
        str(temp_pdf_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=16,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        fontName="Helvetica",
    )

    story = []
    title = doc.get("title", doc.get("filename", "Dokument"))
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 10))

    content = doc.get("content", "")
    content = content.replace("&", "&amp;")
    content = content.replace("<", "&lt;")
    content = content.replace(">", "&gt;")
    content = content.replace("\n", "<br/>")

    story.append(Paragraph(content, body_style))
    pdf_doc.build(story)

    # Convert PDF to images and apply effects
    pdf_document = fitz.open(str(temp_pdf_path))
    images = []

    # DPI for rendering (lower = more degraded)
    dpi = random.randint(150, 200)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)

    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        pix = page.get_pixmap(matrix=matrix)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Apply scan effects
        img = apply_scan_effects(img, "hard")
        images.append(img)

    pdf_document.close()

    # Save as new PDF from images
    filepath = output_dir / doc["filename"]

    if images:
        # Convert images back to PDF
        first_img = images[0]
        if len(images) > 1:
            first_img.save(
                str(filepath),
                "PDF",
                save_all=True,
                append_images=images[1:],
                resolution=dpi,
                quality=random.randint(70, 85),
            )
        else:
            first_img.save(str(filepath), "PDF", resolution=dpi, quality=random.randint(70, 85))

    # Clean up temp file
    temp_pdf_path.unlink()

    return filepath


def main():
    parser = argparse.ArgumentParser(description="Generate files from documents.json")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory")
    parser.add_argument("--input", "-i", default="dataset/documents.json", help="Input JSON file")
    parser.add_argument(
        "--include-pdf",
        action="store_true",
        help="Include PDF documents (requires: uv sync --extra pdf)",
    )
    parser.add_argument(
        "--include-db",
        action="store_true",
        help="Include SQLite database generation",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Filter documents based on --include-pdf flag
    docs_to_generate = []
    pdf_skipped = 0
    for doc in data["documents"]:
        if doc.get("format") == "pdf":
            if args.include_pdf:
                docs_to_generate.append(doc)
            else:
                pdf_skipped += 1
        else:
            docs_to_generate.append(doc)

    print(f"Generating {len(docs_to_generate)} files to {output_dir}/")
    if pdf_skipped > 0:
        print(f"  (Skipping {pdf_skipped} PDF documents - use --include-pdf to generate)")

    generated = 0
    skipped = 0

    for doc in docs_to_generate:
        doc_type = doc["type"]
        fmt = doc.get("format", "")

        try:
            if fmt == "pdf":
                # Handle PDF documents
                difficulty = doc.get("pdf_difficulty", "easy")
                if difficulty == "easy":
                    result = generate_pdf_easy(doc, output_dir)
                else:
                    result = generate_pdf_hard(doc, output_dir)
                if result is None:
                    skipped += 1
                    continue
            elif fmt == "eml" or "email" in doc_type:
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

    # Validation check: ensure we processed all documents
    expected = len(docs_to_generate)
    actual = generated + skipped
    if actual != expected:
        print(f"\nERROR: Expected to process {expected} documents, but processed {actual}")
        raise SystemExit(1)

    if skipped > 0:
        print(f"\nWARNING: {skipped} documents were skipped (missing dependencies?)")

    # Count actual files on disk
    actual_files = list(output_dir.glob("*"))
    actual_file_count = len([f for f in actual_files if f.is_file()])

    if actual_file_count != generated:
        print(f"\nERROR: Expected {generated} files on disk, but found {actual_file_count}")
        raise SystemExit(1)

    # Summary
    total_in_json = len(data["documents"])
    if args.include_pdf:
        if generated == total_in_json:
            print(f"\nValidation passed: all {generated} documents generated")
        else:
            print(f"\nValidation passed: {generated}/{total_in_json} generated ({skipped} skipped)")
    else:
        non_pdf_count = total_in_json - pdf_skipped
        if generated == non_pdf_count:
            print(f"\nValidation passed: all {generated} non-PDF documents generated")
        else:
            print(f"\nValidation passed: {generated}/{non_pdf_count} non-PDF ({skipped} skipped)")

    # Generate database if requested
    if args.include_db:
        from scripts.generate_database import (
            create_indexes,
            create_schema,
            create_views,
            insert_data,
            verify_database,
        )

        db_json_path = Path(args.input).parent / "database.json"
        with open(db_json_path, "r", encoding="utf-8") as f:
            db_def = json.load(f)

        db_name = db_def["meta"]["database_name"]
        db_path = output_dir / db_name

        if db_path.exists():
            db_path.unlink()

        print(f"\nGenerating database: {db_path}")

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            create_schema(conn, db_def["schema"])
            counts = insert_data(conn, db_def["data"])
            create_indexes(conn)
            create_views(conn)

            if verify_database(conn, counts):
                print(f"  Database created: {sum(counts.values())} rows in {len(counts)} tables")
            else:
                print("  ERROR: Database verification failed")
                raise SystemExit(1)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
