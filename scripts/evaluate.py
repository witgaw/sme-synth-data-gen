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

    # Token recall - partial credit if all meaningful expected tokens appear in submitted
    # Handles any order, extra surrounding text, punctuation differences
    def _tokens(s: str) -> set[str]:
        return {t for t in re.sub(r"[^\w\s]", " ", s).split() if len(t) > 2}

    exp_tokens = _tokens(expected_norm)
    sub_tokens = _tokens(submitted_norm)
    if exp_tokens and exp_tokens.issubset(sub_tokens):
        return 0.5

    return 0.0


def check_negative_question(submitted: str) -> bool:
    """Check if answer correctly indicates information is not available."""
    # Empty or whitespace-only counts as "no information"
    if not submitted or not submitted.strip():
        return True

    submitted_lower = submitted.lower().strip()

    negative_indicators = [
        # Polish - explicit negatives
        "brak informacji",
        "brak danych",
        "brak takich",
        "nie znaleziono",
        "nie odnaleziono",
        "nie ma danych",
        "nie ma informacji",
        "nie wiem",
        "nie można ustalić",
        "nie można określić",
        "nie dotyczy",
        "nie występuje",
        "nie istnieje",
        "nie zawiera",
        "nie zawierają",
        "nie jest dostępna",
        "nie są dostępne",
        "nie jestem w stanie",
        "nie mogę",
        "nie udało się",
        "nie posiadam",
        "nie wynika",
        "nie obejmują",
        "nie odnoszą się",
        "niedostępn",
        "poza zakresem",
        "brak",
        # English - explicit negatives
        "not found",
        "no information",
        "no data",
        "not available",
        "not present",
        "not mentioned",
        "does not contain",
        "doesn't contain",
        "do not contain",
        "don't contain",
        "cannot find",
        "could not find",
        "couldn't find",
        "unable to",
        "no such",
        "no relevant",
        "not in the documents",
        "outside the scope",
        "n/a",
        "unknown",
    ]

    # Check for negative indicators
    for indicator in negative_indicators:
        if indicator in submitted_lower:
            return True

    return False


def check_partial_answer(submitted: str) -> bool:
    """Check if answer acknowledges that only partial/limited information is available."""
    if not submitted or not submitted.strip():
        return False

    submitted_lower = submitted.lower().strip()

    partial_indicators = [
        # Polish
        "częściow",
        "fragmentarycz",
        "ograniczon",
        "niepełn",
        "jedynie ogóln",
        "tylko ogóln",
        "brak szczegół",
        "brak szczegółow",
        "nie zawiera szczegół",
        "nie ma szczegół",
        "ogólnikow",
        "wysokopoziomow",
        # English
        "partial",
        "limited information",
        "incomplete",
        "only high-level",
        "only general",
        "no detail",
        "lacks detail",
        "not detailed",
        "fragmentary",
    ]

    for indicator in partial_indicators:
        if indicator in submitted_lower:
            return True

    return False


def check_temporal_filter(submitted: str, expected_doc_ids: list) -> dict:
    """Check temporal filter question - matches filenames mentioned in the answer."""
    # expected_doc_ids may be list of strings or list of {id, filename} dicts
    entries = [e if isinstance(e, dict) else {"id": e, "filename": e} for e in expected_doc_ids]
    filename_to_id = {e["filename"]: e["id"] for e in entries}
    expected_set = {e["id"] for e in entries}

    # Match filenames mentioned in the submitted answer
    found_ids = set()
    for filename, doc_id in filename_to_id.items():
        if filename.lower() in submitted.lower():
            found_ids.add(doc_id)

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


def levenshtein_distance(seq1: list, seq2: list) -> int:
    """Compute Levenshtein edit distance between two sequences (chars or words)."""
    m, n = len(seq1), len(seq2)
    prev = list(range(n + 1))
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j - 1], prev[j], curr[j - 1])
        prev, curr = curr, prev
    return prev[n]


def compute_cer(hypothesis: str, reference: str) -> float:
    """Character Error Rate: char-level edit distance / reference length. 0.0 = perfect."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    dist = levenshtein_distance(list(hypothesis), list(reference))
    return dist / len(reference)


def compute_wer(hypothesis: str, reference: str) -> float:
    """Word Error Rate: word-level edit distance / reference word count. 0.0 = perfect."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = levenshtein_distance(hyp_words, ref_words)
    return dist / len(ref_words)


def evaluate_ocr_quality(ocr_texts: dict, documents: list) -> dict:
    """
    Compare submitted OCR text against ground truth document content.

    Args:
        ocr_texts: Dict of {doc_id: extracted_text} from submissions["ocr_texts"]
        documents: List of document dicts from documents.json

    Returns:
        Dict with per-document CER/WER and aggregated summary by difficulty.
    """
    ocr_docs = {d["id"]: d for d in documents if d.get("pdf_difficulty")}

    results = []
    for doc_id, submitted_text in ocr_texts.items():
        if doc_id not in ocr_docs:
            continue
        doc = ocr_docs[doc_id]
        reference = doc.get("content", "")
        difficulty = doc.get("pdf_difficulty", "unknown")

        ref_norm = re.sub(r"\s+", " ", reference.strip())
        hyp_norm = re.sub(r"\s+", " ", submitted_text.strip()) if submitted_text else ""

        cer = compute_cer(hyp_norm, ref_norm)
        wer = compute_wer(hyp_norm, ref_norm)

        results.append(
            {
                "doc_id": doc_id,
                "filename": doc.get("filename", ""),
                "difficulty": difficulty,
                "cer": round(cer, 4),
                "wer": round(wer, 4),
                "ref_chars": len(ref_norm),
                "hyp_chars": len(hyp_norm),
                "submitted": bool(submitted_text),
            }
        )

    def _agg(items: list) -> dict:
        if not items:
            return {"count": 0, "mean_cer": None, "mean_wer": None, "submitted_count": 0}
        return {
            "count": len(items),
            "mean_cer": round(sum(r["cer"] for r in items) / len(items), 4),
            "mean_wer": round(sum(r["wer"] for r in items) / len(items), 4),
            "submitted_count": sum(1 for r in items if r["submitted"]),
        }

    easy = [r for r in results if r["difficulty"] == "easy"]
    hard = [r for r in results if r["difficulty"] == "hard"]

    return {
        "documents": results,
        "summary": {
            "total": _agg(results),
            "easy": _agg(easy),
            "hard": _agg(hard),
        },
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

    for category in auto_score_categories:
        questions = ground_truth.get(category, [])
        for q in questions:
            qid = q["id"]
            expected = q.get("expected_answer", "")

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
        q_type = q.get("type", "")

        # negative_partial: partial info exists, so route to human review
        # since a good answer may provide partial data + acknowledge gaps
        if q_type == "negative_partial":
            is_negative = check_negative_question(submitted)
            is_partial = check_partial_answer(submitted)
            results["auto_scored"].append(
                {
                    "id": qid,
                    "category": "negative_questions",
                    "question": q.get("question_pl", "")[:80] + "...",
                    "expected": f"[Should indicate: {expected_behavior}]",
                    "submitted": submitted,
                    "score": 1.0 if (is_negative or is_partial) else 0.0,
                }
            )
        else:
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

        # temporal_synthesis questions also require summary scoring via rubric
        if q.get("rubric_id"):
            results["human_review"].append(
                {
                    "id": qid,
                    "category": "temporal_synthesis",
                    "question": q.get("question_pl", q.get("question_en", "")),
                    "rubric_id": q["rubric_id"],
                    "submitted": submitted,
                }
            )

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
    documents: dict | str | Path | None = None,
) -> dict:
    """
    Evaluate RAG submissions against ground truth.

    Can be called from Python code with dicts or file paths.

    Args:
        submissions: Dict of {question_id: answer} or path to JSON file.
            May include an optional "ocr_texts" key: {doc_id: extracted_text}
            for OCR quality assessment.
        ground_truth: Dict or path to ground truth JSON (default: dataset/ground_truth.json)
        rubrics: Dict or path to rubrics JSON (default: dataset/qualitative_rubric.json)
        documents: Dict or path to documents JSON (default: dataset/documents.json).
            Required only when "ocr_texts" is present in submissions.

    Returns:
        Dict with keys:
            - auto_scored: List of auto-scored results with scores (1.0/0.5/0.0)
            - human_review: List of questions requiring semantic analysis
            - temporal: List of temporal filter results
            - not_answered: List of unanswered questions
            - summary: Dict with aggregate statistics
            - ocr_quality: (optional) OCR CER/WER results per document

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

    # Run QA evaluation
    results = evaluate_submissions(ground_truth, submissions)

    # Attach rubrics to results for convenience
    if rubrics:
        results["rubrics"] = rubrics

    # OCR quality assessment if ocr_texts provided
    ocr_texts = submissions.get("ocr_texts")
    if ocr_texts:
        if documents is None:
            documents = Path("dataset/documents.json")
        if isinstance(documents, (str, Path)):
            with open(documents, encoding="utf-8") as f:
                documents = json.load(f)
        if isinstance(documents, dict):
            doc_list = documents.get("documents", documents)
        else:
            doc_list = documents
        results["ocr_quality"] = evaluate_ocr_quality(ocr_texts, doc_list)

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

    # OCR quality
    if results.get("ocr_quality"):
        oq = results["ocr_quality"]
        lines.append("## OCR Quality Assessment\n")
        s = oq["summary"]
        for label, key in [("All", "total"), ("Easy PDFs", "easy"), ("Hard PDFs", "hard")]:
            agg = s[key]
            if agg["count"] == 0:
                continue
            cer = f"{agg['mean_cer']:.1%}" if agg["mean_cer"] is not None else "n/a"
            wer = f"{agg['mean_wer']:.1%}" if agg["mean_wer"] is not None else "n/a"
            submitted = agg["submitted_count"]
            total_docs = agg["count"]
            lines.append(f"**{label}** ({submitted}/{total_docs} submitted): CER={cer}, WER={wer}")
        lines.append("")
        lines.append("| Document | Difficulty | CER | WER | Chars (ref) |")
        lines.append("|---|---|---|---|---|")
        for r in sorted(oq["documents"], key=lambda x: x["doc_id"]):
            cer = f"{r['cer']:.1%}"
            wer = f"{r['wer']:.1%}"
            lines.append(
                f"| {r['doc_id']} / {r['filename']} | {r['difficulty']} "
                f"| {cer} | {wer} | {r['ref_chars']} |"
            )
        lines.append("")

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

    if results.get("ocr_quality"):
        oq = results["ocr_quality"]
        s = oq["summary"]
        tbl = Table(
            title="OCR Quality Assessment", show_lines=True, border_style="cyan", expand=True
        )
        tbl.add_column("Document", style="dim", no_wrap=True)
        tbl.add_column("Difficulty", width=8)
        tbl.add_column("CER", width=8, justify="right")
        tbl.add_column("WER", width=8, justify="right")
        tbl.add_column("Chars (ref)", width=12, justify="right")
        for r in sorted(oq["documents"], key=lambda x: x["doc_id"]):
            cer_color = "green" if r["cer"] < 0.05 else "yellow" if r["cer"] < 0.20 else "red"
            wer_color = "green" if r["wer"] < 0.05 else "yellow" if r["wer"] < 0.20 else "red"
            diff_color = "cyan" if r["difficulty"] == "easy" else "magenta"
            tbl.add_row(
                f"{r['doc_id']} {r['filename']}",
                f"[{diff_color}]{r['difficulty']}[/]",
                f"[{cer_color}]{r['cer']:.1%}[/]",
                f"[{wer_color}]{r['wer']:.1%}[/]",
                str(r["ref_chars"]),
            )
        # Append aggregate summary rows
        for label, key in [("Easy avg", "easy"), ("Hard avg", "hard"), ("Total avg", "total")]:
            agg = s[key]
            if agg["count"] == 0:
                continue
            cer_str = f"{agg['mean_cer']:.1%}" if agg["mean_cer"] is not None else "n/a"
            wer_str = f"{agg['mean_wer']:.1%}" if agg["mean_wer"] is not None else "n/a"
            sub_str = f"{agg['submitted_count']}/{agg['count']}"
            tbl.add_row(
                f"[bold]{label}[/] ({sub_str} submitted)",
                "",
                f"[bold]{cer_str}[/]",
                f"[bold]{wer_str}[/]",
                "",
            )
        panels.append(tbl)

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
        "--documents",
        "-D",
        default="dataset/documents.json",
        help="Path to documents JSON (for OCR quality assessment)",
    )
    parser.add_argument(
        "--display",
        "-d",
        choices=["rich", "markdown", "json"],
        default="rich",
        help="Output display format (default: rich)",
    )
    args = parser.parse_args()

    # Evaluate (loads ground truth, submissions, rubrics, documents internally)
    results = evaluate(
        submissions=args.submissions,
        ground_truth=args.ground_truth,
        rubrics=args.rubrics,
        documents=args.documents,
    )
    rubrics = results.pop("rubrics", None)

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
