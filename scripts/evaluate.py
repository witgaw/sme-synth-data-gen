#!/usr/bin/env python3
"""
Evaluate RAG system answers against ground truth.

Usage:
    uv run evaluate submissions.json
    uv run evaluate submissions.json --output results.json
    uv run evaluate submissions.json --format markdown

Input format (submissions.json):
    {
        "q001": "2023-07-26",
        "q002": "Maciej Boryna",
        ...
    }

Output:
    - Auto-scored results for exact match questions
    - Human review section for qualitative questions
    - Summary statistics
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, normalize unicode."""
    if not isinstance(text, str):
        text = str(text)
    # Normalize unicode (e.g., ł -> l for comparison)
    text = unicodedata.normalize("NFKC", text)
    # Lowercase and strip
    text = text.lower().strip()
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_number(text: str) -> float | None:
    """Extract numeric value from text, handling Polish formats."""
    if not isinstance(text, str):
        if isinstance(text, (int, float)):
            return float(text)
        text = str(text)

    # Remove currency and common suffixes
    text = re.sub(r"\s*(PLN|zł|złotych|pln|ZŁ)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*(dni|days|godzin|hours|h|%)\s*", "", text, flags=re.IGNORECASE)

    # Handle "k" suffix (e.g., "50k" -> 50000)
    if match := re.search(r"(\d+(?:[.,]\d+)?)\s*k\b", text, re.IGNORECASE):
        return float(match.group(1).replace(",", ".")) * 1000

    # Remove thousand separators and normalize decimal
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)  # "50 000" -> "50000"
    text = text.replace(" ", "")

    # Try to extract number
    if match := re.search(r"-?\d+(?:[.,]\d+)?", text):
        num_str = match.group().replace(",", ".")
        try:
            return float(num_str)
        except ValueError:
            pass
    return None


def normalize_date(text: str) -> str | None:
    """Normalize date to YYYY-MM-DD format."""
    if not isinstance(text, str):
        text = str(text)

    # Already in ISO format
    if match := re.search(r"(\d{4})-(\d{2})-(\d{2})", text):
        return match.group()

    # Polish format: DD.MM.YYYY or DD/MM/YYYY
    if match := re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", text):
        day, month, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # Just year-month
    if match := re.search(r"(\d{4})-(\d{2})", text):
        return match.group()

    return None


def check_exact_match(submitted: str, expected: str, variants: list[str] | None) -> float:
    """
    Check if submitted answer matches expected or any variant.

    Returns:
        1.0 = exact match (followed format instructions)
        0.5 = correct after normalization (right fact, wrong format)
        0.0 = wrong
    """
    submitted_norm = normalize_text(submitted)
    expected_norm = normalize_text(expected)

    # Direct text match - full credit
    if submitted_norm == expected_norm:
        return 1.0

    # Check variants - full credit (variants are acceptable formats)
    if variants:
        for variant in variants:
            if normalize_text(variant) == submitted_norm:
                return 1.0

    # Try numeric comparison - partial credit (right fact, extra formatting)
    submitted_num = normalize_number(submitted)
    expected_num = normalize_number(expected)
    if submitted_num is not None and expected_num is not None:
        # Allow 1% tolerance for floating point
        if abs(submitted_num - expected_num) < max(0.01, abs(expected_num) * 0.01):
            return 0.5

    # Try date comparison - partial credit
    submitted_date = normalize_date(submitted)
    expected_date = normalize_date(expected)
    if submitted_date and expected_date:
        if submitted_date == expected_date:
            return 0.5

    # Check if expected is contained in submitted - partial credit
    if expected_norm in submitted_norm and len(expected_norm) > 5:
        return 0.5

    return 0.0


def check_negative_question(submitted: str) -> bool:
    """Check if answer correctly indicates information is not available."""
    # Empty or whitespace-only counts as "no information"
    if not submitted or not submitted.strip():
        return True

    submitted_lower = submitted.lower().strip()

    negative_indicators = [
        "nie znaleziono",
        "brak informacji",
        "nie ma danych",
        "nie wiem",
        "nie można ustalić",
        "brak danych",
        "nie dotyczy",
        "n/a",
        "not found",
        "no information",
        "unknown",
        "nie występuje",
        "brak",
        "nie istnieje",
    ]

    # Check for negative indicators
    for indicator in negative_indicators:
        if indicator in submitted_lower:
            return True

    # Check for question marks or uncertainty
    if "?" in submitted and len(submitted) < 50:
        return True

    return False


def check_temporal_filter(submitted: str, expected_doc_ids: list[str]) -> dict:
    """Check temporal filter question - expects list of document IDs."""
    # Try to extract document IDs from the answer
    found_ids = set(re.findall(r"doc_\d+", submitted.lower()))

    expected_set = set(expected_doc_ids)

    correct = found_ids & expected_set
    missing = expected_set - found_ids
    extra = found_ids - expected_set

    precision = len(correct) / len(found_ids) if found_ids else 0
    recall = len(correct) / len(expected_set) if expected_set else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "correct": list(correct),
        "missing": list(missing),
        "extra": list(extra),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "pass": recall >= 0.8,  # Pass if at least 80% of expected docs found
    }


def evaluate_submissions(ground_truth: dict, submissions: dict) -> dict:
    """Evaluate all submissions against ground truth."""
    results = {
        "auto_scored": [],
        "human_review": [],
        "temporal": [],
        "not_answered": [],
        "summary": {},
    }

    # Collect all questions with expected answers (auto-scorable)
    # Only truly auto-scorable are short factual answers
    auto_score_categories = [
        "exact_match_questions",
        "multi_document_synthesis_questions",
        "ocr_questions",
        "multi_hop_ocr_questions",
        "database_questions",
        "multi_hop_db_doc_questions",
    ]

    # Max length for auto-scoring - longer answers need human review
    AUTO_SCORE_MAX_LENGTH = 80

    for category in auto_score_categories:
        questions = ground_truth.get(category, [])
        for q in questions:
            qid = q["id"]
            expected = q.get("expected_answer", "")

            # Long/complex answers go to human review, not auto-scoring
            if len(expected) > AUTO_SCORE_MAX_LENGTH:
                submitted = submissions.get(qid, "[NOT ANSWERED]")
                results["human_review"].append(
                    {
                        "id": qid,
                        "category": category,
                        "question": q.get("question_pl", q.get("question_en", "")),
                        "reference_answer": expected,
                        "submitted": submitted,
                    }
                )
                continue

            if qid not in submissions:
                results["not_answered"].append(
                    {
                        "id": qid,
                        "category": category,
                        "question": q.get("question_pl", q.get("question_en", "")),
                    }
                )
                continue

            submitted = submissions[qid]
            expected = q.get("expected_answer", "")
            variants = q.get("answer_variants", [])

            score = check_exact_match(submitted, expected, variants)

            results["auto_scored"].append(
                {
                    "id": qid,
                    "category": category,
                    "question": q.get("question_pl", "")[:80] + "...",
                    "expected": expected,
                    "submitted": submitted,
                    "variants": variants,
                    "score": score,
                }
            )

    # Qualitative questions - need human review
    for q in ground_truth.get("qualitative_questions", []):
        qid = q["id"]
        submitted = submissions.get(qid, "[NOT ANSWERED]")

        results["human_review"].append(
            {
                "id": qid,
                "category": "qualitative",
                "question": q.get("question_pl", q.get("question_en", "")),
                "rubric_id": q.get("rubric_id"),
                "submitted": submitted,
            }
        )

    # Negative questions - check for appropriate "not found" response
    for q in ground_truth.get("negative_questions", []):
        qid = q["id"]
        if qid not in submissions:
            results["not_answered"].append(
                {
                    "id": qid,
                    "category": "negative_questions",
                    "question": q.get("question_pl", q.get("question_en", "")),
                }
            )
            continue

        submitted = submissions[qid]
        expected_behavior = q.get("expected_behavior", "")

        is_correct = check_negative_question(submitted)

        results["auto_scored"].append(
            {
                "id": qid,
                "category": "negative_questions",
                "question": q.get("question_pl", "")[:80] + "...",
                "expected": f"[Should indicate: {expected_behavior}]",
                "submitted": submitted,
                "score": 1.0 if is_correct else 0.0,
            }
        )

    # Temporal filter questions - check document ID recall
    for q in ground_truth.get("temporal_filter_questions", []):
        qid = q["id"]
        if qid not in submissions:
            results["not_answered"].append(
                {
                    "id": qid,
                    "category": "temporal_filter_questions",
                    "question": q.get("question_pl", q.get("question_en", "")),
                }
            )
            continue

        submitted = submissions[qid]
        expected_ids = q.get("expected_document_ids", [])

        temporal_result = check_temporal_filter(submitted, expected_ids)
        temporal_result["id"] = qid
        temporal_result["question"] = q.get("question_pl", "")[:80] + "..."
        temporal_result["submitted"] = submitted

        results["temporal"].append(temporal_result)

    # Calculate summary statistics
    auto_scored = results["auto_scored"]
    total_score = sum(r["score"] for r in auto_scored)
    max_score = len(auto_scored)
    full_credit = sum(1 for r in auto_scored if r["score"] == 1.0)
    partial_credit = sum(1 for r in auto_scored if r["score"] == 0.5)
    wrong = sum(1 for r in auto_scored if r["score"] == 0.0)

    temporal = results["temporal"]
    temporal_pass = sum(1 for r in temporal if r["pass"])
    total_temporal = len(temporal)

    results["summary"] = {
        "auto_scored_total_score": total_score,
        "auto_scored_max_score": max_score,
        "auto_scored_percentage": round(100 * total_score / max_score, 1) if max_score else 0,
        "full_credit_count": full_credit,
        "partial_credit_count": partial_credit,
        "wrong_count": wrong,
        "temporal_pass": temporal_pass,
        "temporal_total": total_temporal,
        "human_review_count": len(results["human_review"]),
        "not_answered_count": len(results["not_answered"]),
    }

    return results


def evaluate(
    submissions: dict | str | Path,
    ground_truth: dict | str | Path | None = None,
    rubrics: dict | str | Path | None = None,
) -> dict:
    """
    Evaluate RAG submissions against ground truth.

    Can be called from Python code with dicts or file paths.

    Args:
        submissions: Dict of {question_id: answer} or path to JSON file
        ground_truth: Dict or path to ground truth JSON (default: dataset/ground_truth.json)
        rubrics: Dict or path to rubrics JSON (default: dataset/qualitative_rubric.json)

    Returns:
        Dict with keys:
            - auto_scored: List of auto-scored results with scores (1.0/0.5/0.0)
            - human_review: List of questions requiring semantic analysis
            - temporal: List of temporal filter results
            - not_answered: List of unanswered questions
            - summary: Dict with aggregate statistics

    Example:
        >>> from scripts.evaluate import evaluate
        >>> results = evaluate({"q001": "15 czerwca 2023", "q002": "45"})
        >>> print(results["summary"]["auto_scored_percentage"])
    """
    # Load submissions if path
    if isinstance(submissions, (str, Path)):
        with open(submissions, encoding="utf-8") as f:
            submissions = json.load(f)

    # Load ground truth
    if ground_truth is None:
        ground_truth = Path("dataset/ground_truth.json")
    if isinstance(ground_truth, (str, Path)):
        with open(ground_truth, encoding="utf-8") as f:
            ground_truth = json.load(f)

    # Load rubrics
    if rubrics is None:
        rubrics_path = Path("dataset/qualitative_rubric.json")
        if rubrics_path.exists():
            with open(rubrics_path, encoding="utf-8") as f:
                rubrics = json.load(f)
    elif isinstance(rubrics, (str, Path)):
        with open(rubrics, encoding="utf-8") as f:
            rubrics = json.load(f)

    # Run evaluation
    results = evaluate_submissions(ground_truth, submissions)

    # Attach rubrics to results for convenience
    if rubrics:
        results["rubrics"] = rubrics

    return results


def format_markdown_report(results: dict, rubrics: dict | None = None) -> str:
    """Format results as a human-readable markdown report."""
    lines = []
    summary = results["summary"]

    lines.append("# RAG Evaluation Report\n")

    # Summary
    lines.append("## Summary\n")
    total_score = summary["auto_scored_total_score"]
    max_score = summary["auto_scored_max_score"]
    pct = summary["auto_scored_percentage"]
    lines.append(f"- **Auto-scored:** {total_score}/{max_score} ({pct}%)")
    lines.append(f"  - Full credit (1.0): {summary['full_credit_count']}")
    lines.append(f"  - Partial credit (0.5): {summary['partial_credit_count']}")
    lines.append(f"  - Wrong (0.0): {summary['wrong_count']}")
    if summary["temporal_total"] > 0:
        t_pass = summary["temporal_pass"]
        t_total = summary["temporal_total"]
        lines.append(f"- **Temporal filter:** {t_pass}/{t_total} passed")
    lines.append(f"- **Semantic analysis:** {summary['human_review_count']} questions")
    if summary["not_answered_count"] > 0:
        lines.append(f"- **Not answered:** {summary['not_answered_count']} questions")
    lines.append("")

    # Auto-scored results
    lines.append("## Auto-Scored Questions\n")

    # Group by category
    by_category = {}
    for r in results["auto_scored"]:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r)

    for category, items in by_category.items():
        cat_score = sum(i["score"] for i in items)
        lines.append(f"### {category} ({cat_score}/{len(items)})\n")

        for r in items:
            score = r["score"]
            if score == 1.0:
                status = "✓"
            elif score == 0.5:
                status = "½"
            else:
                status = "✗"
            lines.append(f"**{r['id']}** {status} ({score})")
            lines.append(f"- Q: {r['question']}")
            lines.append(f"- Expected: `{r['expected']}`")
            lines.append(f"- Submitted: `{r['submitted']}`")
            if score < 1.0 and r.get("variants"):
                lines.append(f"- Variants: {r['variants'][:3]}")
            lines.append("")

    # Temporal filter results
    if results["temporal"]:
        lines.append("## Temporal Filter Questions\n")
        for r in results["temporal"]:
            status = "✓" if r["pass"] else "✗"
            lines.append(f"**{r['id']}** {status} (F1: {r['f1']:.2f})")
            lines.append(f"- Q: {r['question']}")
            lines.append(f"- Recall: {r['recall']:.1%}, Precision: {r['precision']:.1%}")
            if r["missing"]:
                lines.append(f"- Missing: {r['missing']}")
            if r["extra"]:
                lines.append(f"- Extra: {r['extra']}")
            lines.append("")

    # Human review section
    if results["human_review"]:
        lines.append("## Requires Semantic Analysis\n")
        lines.append("Not auto-scored. Use human review or LLM-based evaluation.\n")

        for r in results["human_review"]:
            lines.append(f"### {r['id']} ({r.get('category', 'qualitative')})\n")
            lines.append(f"**Question:** {r['question']}\n")

            # Include rubric if available (for qualitative questions)
            if rubrics and r.get("rubric_id"):
                rubric = rubrics.get("rubrics", {}).get(r["rubric_id"], {})
                if rubric:
                    lines.append("**Rubric criteria:**")
                    for item in rubric.get("must_mention", []):
                        lines.append(f"- [MUST] {item}")
                    for item in rubric.get("should_mention", []):
                        lines.append(f"- [SHOULD] {item}")
                    lines.append("")
                    n_must = len(rubric.get("must_mention", []))
                    n_should = len(rubric.get("should_mention", []))
                    s_high = max(1, round(n_should * 0.75))

                    def fmt_range(lo: int, hi: int) -> str:
                        return str(lo) if lo == hi else f"{lo}-{hi}"

                    lines.append(f"**Scoring (0-5, {n_must} MUST, {n_should} SHOULD):**")
                    lines.append(f"- 5: {n_must} MUST + ≥{s_high} SHOULD")
                    lines.append(f"- 4: {n_must} MUST + <{s_high} SHOULD")
                    lines.append(f"- 3: {fmt_range(n_must - 1, n_must - 1)} MUST")
                    lines.append(f"- 2: {fmt_range(n_must // 2 + 1, n_must - 2)} MUST")
                    lines.append(f"- 1: {fmt_range(1, n_must // 2)} MUST")
                    lines.append("- 0: 0 MUST or factual errors")
                    lines.append("")

            # Include reference answer if available (for complex factual questions)
            if r.get("reference_answer"):
                lines.append(f"**Reference answer:**\n> {r['reference_answer']}\n")
                lines.append("**Scoring:** 0=wrong, 1=partial match, 2=correct\n")

            lines.append(f"**Submitted answer:**\n> {r['submitted']}\n")
            lines.append("---\n")

    # Not answered
    if results["not_answered"]:
        lines.append("## Not Answered\n")
        for r in results["not_answered"]:
            lines.append(f"- **{r['id']}** ({r['category']}): {r['question'][:60]}...")
        lines.append("")

    return "\n".join(lines)


def print_rich_report(results: dict, rubrics: dict | None = None) -> None:
    """Print results using Rich for nice terminal formatting."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    summary = results["summary"]

    # Summary panel
    total = summary["auto_scored_total_score"]
    max_s = summary["auto_scored_max_score"]
    pct = summary["auto_scored_percentage"]
    color = "green" if pct >= 80 else "yellow" if pct >= 60 else "red"

    summary_text = (
        f"[bold {color}]{total}/{max_s} ({pct}%)[/]\n\n"
        f"[green]Full credit (1.0):[/] {summary['full_credit_count']}\n"
        f"[yellow]Partial (0.5):[/] {summary['partial_credit_count']}\n"
        f"[red]Wrong (0.0):[/] {summary['wrong_count']}\n"
        f"[blue]Semantic analysis:[/] {summary['human_review_count']}"
    )

    # Group auto-scored by score
    full = [r for r in results["auto_scored"] if r["score"] == 1.0]
    partial = [r for r in results["auto_scored"] if r["score"] == 0.5]
    wrong = [r for r in results["auto_scored"] if r["score"] == 0.0]

    def make_table(items: list, title: str, style: str) -> Table:
        table = Table(title=title, show_lines=True, border_style=style, expand=True)
        table.add_column("ID", style="bold", width=12, no_wrap=True)
        table.add_column("Expected")
        table.add_column("Submitted")
        for r in items:
            table.add_row(r["id"], r["expected"], r["submitted"])
        return table

    def make_review_panel(r: dict, rubrics_data: dict | None) -> Panel:
        cat = r.get("category", "qualitative")
        q_text = f"[bold]{r['id']}[/] [dim]({cat})[/]\n\n"
        q_text += f"{r['question']}\n\n"
        if r.get("reference_answer"):
            q_text += f"[green]Reference:[/]\n{r['reference_answer']}\n\n"
            q_text += "[cyan]Suggested scoring:[/] 0=wrong, 1=partial match, 2=correct\n\n"
        elif r.get("rubric_id") and rubrics_data:
            rubric = rubrics_data.get("rubrics", {}).get(r["rubric_id"], {})
            if rubric:
                q_text += "[green]Rubric criteria:[/]\n"
                for item in rubric.get("must_mention", []):
                    q_text += f"  [bold]MUST:[/] {item}\n"
                for item in rubric.get("should_mention", []):
                    q_text += f"  [dim]SHOULD:[/] {item}\n"
                q_text += "\n"
                # Add scoring guidelines with exact counts
                n_must = len(rubric.get("must_mention", []))
                n_should = len(rubric.get("should_mention", []))
                s_high = max(1, round(n_should * 0.75))

                def fmt_range(lo: int, hi: int) -> str:
                    return str(lo) if lo == hi else f"{lo}-{hi}"

                q_text += f"[cyan]Scoring (0-5, {n_must} MUST, {n_should} SHOULD):[/]\n"
                q_text += f"  5: {n_must} MUST + ≥{s_high} SHOULD\n"
                q_text += f"  4: {n_must} MUST + <{s_high} SHOULD\n"
                q_text += f"  3: {fmt_range(n_must - 1, n_must - 1)} MUST\n"
                q_text += f"  2: {fmt_range(n_must // 2 + 1, n_must - 2)} MUST\n"
                q_text += f"  1: {fmt_range(1, n_must // 2)} MUST\n"
                q_text += "  0: 0 MUST or factual errors\n\n"
        q_text += f"[yellow]Submitted:[/]\n{r['submitted']}"
        return Panel(q_text, border_style="blue")

    # Build all content
    panels = [Panel(summary_text, title="Score Summary", border_style=color)]

    if wrong:
        panels.append(make_table(wrong, f"Wrong ({len(wrong)})", "red"))
    if partial:
        panels.append(make_table(partial, f"Partial Credit ({len(partial)})", "yellow"))
    if full:
        panels.append(make_table(full, f"Full Credit ({len(full)})", "green"))

    if results["human_review"]:
        header = (
            "[bold]Requires Semantic Analysis[/] "
            "[dim](not auto-scored - use human review or LLM-based evaluation)[/]"
        )
        panels.append(Panel(header, border_style="blue"))
        for r in results["human_review"]:
            panels.append(make_review_panel(r, rubrics))

    for panel in panels:
        console.print(panel)


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG submissions against ground truth")
    parser.add_argument("submissions", help="Path to submissions JSON file")
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
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--display",
        "-d",
        choices=["rich", "markdown", "json"],
        default="rich",
        help="Output display format (default: rich)",
    )
    args = parser.parse_args()

    # Load ground truth
    with open(args.ground_truth, encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Load submissions
    with open(args.submissions, encoding="utf-8") as f:
        submissions = json.load(f)

    # Load rubrics (optional)
    rubrics = None
    rubrics_path = Path(args.rubrics)
    if rubrics_path.exists():
        with open(rubrics_path, encoding="utf-8") as f:
            rubrics = json.load(f)

    # Evaluate
    results = evaluate_submissions(ground_truth, submissions)

    # Format and output
    if args.display == "rich":
        print_rich_report(results, rubrics)
    elif args.display == "json":
        output = json.dumps(results, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Results written to {args.output}", file=sys.stderr)
        else:
            print(output)
        # Print score to stderr so JSON stays valid
        s = results["summary"]
        score = f"{s['auto_scored_total_score']}/{s['auto_scored_max_score']}"
        print(f"\nSCORE: {score} ({s['auto_scored_percentage']}%)", file=sys.stderr)
    else:  # markdown
        output = format_markdown_report(results, rubrics)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Results written to {args.output}", file=sys.stderr)
        else:
            print(output)


if __name__ == "__main__":
    main()
