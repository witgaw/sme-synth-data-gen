#!/usr/bin/env python3
"""
Generate a leaderboard by scoring all submissions in the submissions/ folder.

Usage:
    uv run leaderboard
    uv run leaderboard --submissions-dir submissions/
    uv run leaderboard --output leaderboard.md
    uv run leaderboard --display markdown
"""

import argparse
import json
import sys
from pathlib import Path

from scripts.evaluate import evaluate


def score_submission(
    path: Path, ground_truth_path: Path, rubrics_path: Path, documents_path: Path
) -> dict:
    """Score a single submission file and return summary + metadata."""
    try:
        results = evaluate(
            submissions=path,
            ground_truth=ground_truth_path,
            rubrics=rubrics_path,
            documents=documents_path,
        )
    except Exception as exc:
        return {"error": str(exc), "file": path.name}

    summary = results["summary"]

    # Per-category breakdown from auto_scored results
    by_cat: dict[str, dict] = {}
    for r in results["auto_scored"]:
        cat = r["category"]
        if cat not in by_cat:
            by_cat[cat] = {"score": 0.0, "max": 0}
        by_cat[cat]["score"] += r["score"]
        by_cat[cat]["max"] += 1
    # Temporal counts separately
    if results["temporal"]:
        by_cat["temporal_filter_questions"] = {
            "score": float(summary["temporal_pass"]),
            "max": summary["temporal_total"],
        }

    # Extract metadata from submission file
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    meta = raw.get("_meta", {})

    return {
        "file": path.name,
        "name": meta.get("name") or meta.get("config") or path.stem,
        "description": meta.get("description", ""),
        "model": meta.get("llm_model", ""),
        "llm_provider": meta.get("llm_provider", ""),
        "ocr_enabled": meta.get("ocr_enabled", False),
        "ocr_model": meta.get("ocr_model", ""),
        "use_reranker": meta.get("use_reranker", False),
        "auto_score": summary["auto_scored_total_score"],
        "auto_max": summary["auto_scored_max_score"],
        "auto_pct": summary["auto_scored_percentage"],
        "full_credit": summary["full_credit_count"],
        "partial_credit": summary["partial_credit_count"],
        "wrong": summary["wrong_count"],
        "temporal_pass": summary["temporal_pass"],
        "temporal_total": summary["temporal_total"],
        "not_answered": summary["not_answered_count"],
        "human_review": summary["human_review_count"],
        "by_category": by_cat,
    }


def build_leaderboard(
    submissions_dir: Path,
    ground_truth_path: Path,
    rubrics_path: Path,
    documents_path: Path,
) -> list[dict]:
    """Score all submissions and return sorted leaderboard entries."""
    sub_files = sorted(submissions_dir.glob("sub_*.json"))
    if not sub_files:
        print(f"No submission files found in {submissions_dir}", file=sys.stderr)
        return []

    entries = []
    for path in sub_files:
        print(f"  Scoring {path.name}...", file=sys.stderr)
        entry = score_submission(path, ground_truth_path, rubrics_path, documents_path)
        entries.append(entry)

    # Sort by auto_pct descending, then full_credit descending
    entries.sort(
        key=lambda e: (
            e.get("auto_pct", -1),
            e.get("full_credit", 0),
            -e.get("not_answered", 0),
        ),
        reverse=True,
    )
    return entries


def format_markdown_leaderboard(entries: list[dict]) -> str:
    lines = []
    lines.append("# RAG Evaluation Leaderboard\n")

    if not entries:
        lines.append("No submissions found.\n")
        return "\n".join(lines)

    # Summary table
    hdr = "| # | Name | Model | Score | % | Full | Partial | Wrong | Temporal | Not answered |"
    sep = "|---|------|-------|------:|--:|-----:|--------:|------:|:--------:|-------------:|"
    lines.append(hdr)
    lines.append(sep)
    for i, e in enumerate(entries, 1):
        if e.get("error"):
            lines.append(f"| {i} | {e['file']} | — | ERROR | — | — | — | — | — | — |")
            continue
        t = f"{e['temporal_pass']}/{e['temporal_total']}" if e["temporal_total"] else "—"
        model = f"{e['model']}" if e["model"] else e["llm_provider"]
        lines.append(
            f"| {i} | {e['name']} "
            f"| {model} "
            f"| {e['auto_score']}/{e['auto_max']} "
            f"| {e['auto_pct']:.1f}% "
            f"| {e['full_credit']} "
            f"| {e['partial_credit']} "
            f"| {e['wrong']} "
            f"| {t} "
            f"| {e['not_answered']} |"
        )
    lines.append("")

    # Detail section
    lines.append("## Submission Details\n")
    for i, e in enumerate(entries, 1):
        if e.get("error"):
            lines.append(f"### {i}. {e['file']} — ERROR\n")
            lines.append(f"> {e['error']}\n")
            continue
        lines.append(f"### {i}. {e['name']}\n")
        if e["description"]:
            lines.append(f"> {e['description']}\n")
        lines.append(f"- **File:** `{e['file']}`")
        lines.append(f"- **Model:** {e['model']} ({e['llm_provider']})")
        if e["ocr_enabled"]:
            lines.append(f"- **OCR model:** {e['ocr_model']}")
        lines.append(f"- **Reranker:** {'yes' if e['use_reranker'] else 'no'}")
        lines.append(
            f"- **Score:** {e['auto_score']}/{e['auto_max']} ({e['auto_pct']:.1f}%) "
            f"— {e['full_credit']} full, {e['partial_credit']} partial, {e['wrong']} wrong"
        )
        if e["temporal_total"]:
            t = f"{e['temporal_pass']}/{e['temporal_total']}"
            lines.append(f"- **Temporal filter:** {t} passed")
        lines.append(f"- **Not answered:** {e['not_answered']}")
        lines.append(f"- **Requires human review:** {e['human_review']} questions")
        if e.get("by_category"):
            lines.append("\n**By category:**\n")
            lines.append("| Category | Score | % |")
            lines.append("|----------|------:|--:|")
            for cat, stats in sorted(e["by_category"].items()):
                pct = 100 * stats["score"] / stats["max"] if stats["max"] else 0
                lines.append(f"| {cat} | {stats['score']}/{stats['max']} | {pct:.0f}% |")
        lines.append("")

    return "\n".join(lines)


def print_rich_leaderboard(entries: list[dict]) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    if not entries:
        console.print("[yellow]No submissions found.[/]")
        return

    table = Table(
        title="RAG Evaluation Leaderboard",
        show_lines=True,
        border_style="cyan",
        expand=True,
    )
    table.add_column("#", width=3, justify="right", style="dim", no_wrap=True)
    table.add_column("Name", min_width=20, ratio=3, no_wrap=False)
    table.add_column("Model", min_width=14, ratio=2, no_wrap=False)
    table.add_column("Score", justify="right", min_width=9, no_wrap=True)
    table.add_column("%", justify="right", min_width=6, no_wrap=True)
    table.add_column("Full", justify="right", min_width=5, no_wrap=True)
    table.add_column("Partial", justify="right", min_width=7, no_wrap=True)
    table.add_column("Wrong", justify="right", min_width=6, no_wrap=True)
    table.add_column("Temporal", justify="center", min_width=9, no_wrap=True)
    table.add_column("N/A", justify="right", min_width=4, no_wrap=True)

    for i, e in enumerate(entries, 1):
        if e.get("error"):
            table.add_row(str(i), e["file"], "", "ERROR", "—", "—", "—", "—", "—", "—")
            continue

        pct = e["auto_pct"]
        pct_color = "green" if pct >= 80 else "yellow" if pct >= 60 else "red"
        t_str = f"{e['temporal_pass']}/{e['temporal_total']}" if e["temporal_total"] else "—"
        model_str = e["model"] or ""
        if e["llm_provider"]:
            if model_str:
                model_str = f"[dim]{e['llm_provider']}[/]\n{model_str}"
            else:
                model_str = e["llm_provider"]

        table.add_row(
            str(i),
            e["name"],
            model_str,
            f"{e['auto_score']}/{e['auto_max']}",
            f"[{pct_color}]{pct:.1f}%[/]",
            f"[green]{e['full_credit']}[/]",
            f"[yellow]{e['partial_credit']}[/]",
            f"[red]{e['wrong']}[/]",
            t_str,
            str(e["not_answered"]) if e["not_answered"] else "[dim]0[/]",
        )

    console.print(table)

    # Per-category breakdown table
    all_cats = sorted(
        {cat for e in entries if not e.get("error") for cat in e.get("by_category", {})}
    )
    if all_cats:
        cat_table = Table(title="Score by Category", show_lines=True, border_style="blue")
        cat_table.add_column("Category", min_width=36)
        for e in entries:
            if not e.get("error"):
                cat_table.add_column(e["name"], justify="right", min_width=10)
        for cat in all_cats:
            row = [cat]
            for e in entries:
                if e.get("error"):
                    continue
                stats = e.get("by_category", {}).get(cat)
                if stats:
                    pct = 100 * stats["score"] / stats["max"] if stats["max"] else 0
                    col = "green" if pct >= 80 else "yellow" if pct >= 60 else "red"
                    row.append(f"[{col}]{stats['score']:.0f}/{stats['max']} ({pct:.0f}%)[/]")
                else:
                    row.append("[dim]—[/]")
            cat_table.add_row(*row)
        console.print(cat_table)

    # Top entry detail
    top = entries[0]
    if not top.get("error"):
        detail = f"[bold]#1 {top['name']}[/]\nModel: {top['model']} ({top['llm_provider']})"
        if top["description"]:
            detail = f"{top['description']}\n\n" + detail
        console.print(Panel(detail, title="Leader", border_style="gold1"))


def main():
    parser = argparse.ArgumentParser(description="Score all submissions and print a leaderboard")
    parser.add_argument(
        "--submissions-dir",
        "-s",
        default="submissions",
        help="Directory containing sub_*.json files (default: submissions/)",
    )
    parser.add_argument(
        "--ground-truth",
        "-g",
        default="dataset/ground_truth.json",
        help="Path to ground truth JSON",
    )
    parser.add_argument(
        "--rubrics",
        "-r",
        default="dataset/qualitative_rubric.json",
        help="Path to rubrics JSON",
    )
    parser.add_argument(
        "--documents",
        "-D",
        default="dataset/documents.json",
        help="Path to documents JSON",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Write markdown leaderboard to this file",
    )
    parser.add_argument(
        "--display",
        "-d",
        choices=["rich", "markdown"],
        default="rich",
        help="CLI display format (default: rich)",
    )
    args = parser.parse_args()

    submissions_dir = Path(args.submissions_dir)
    if not submissions_dir.is_dir():
        print(f"Submissions directory not found: {submissions_dir}", file=sys.stderr)
        sys.exit(1)

    print("Building leaderboard...", file=sys.stderr)
    entries = build_leaderboard(
        submissions_dir=submissions_dir,
        ground_truth_path=Path(args.ground_truth),
        rubrics_path=Path(args.rubrics),
        documents_path=Path(args.documents),
    )

    # CLI display
    if args.display == "rich":
        print_rich_leaderboard(entries)
    else:
        print(format_markdown_leaderboard(entries))

    # Markdown file output
    if args.output:
        md = format_markdown_leaderboard(entries)
        out_path = Path(args.output)
        out_path.write_text(md, encoding="utf-8")
        print(f"Leaderboard written to {out_path}", file=sys.stderr)
    elif args.display == "rich":
        # Always write leaderboard.md alongside submissions/ by default
        default_out = submissions_dir.parent / "leaderboard.md"
        md = format_markdown_leaderboard(entries)
        default_out.write_text(md, encoding="utf-8")
        print(f"Leaderboard markdown written to {default_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
