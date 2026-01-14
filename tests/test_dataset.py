"""
Dataset validation tests.

Run with: uv run pytest
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

DATASET_DIR = Path(__file__).parent.parent / "dataset"


@pytest.fixture
def documents():
    with open(DATASET_DIR / "documents.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def ground_truth():
    with open(DATASET_DIR / "ground_truth.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def company_meta():
    with open(DATASET_DIR / "company_meta.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def rubrics():
    with open(DATASET_DIR / "qualitative_rubric.json", encoding="utf-8") as f:
        return json.load(f)


class TestDocumentsJson:
    def test_valid_json(self, documents):
        """documents.json is valid JSON with expected structure."""
        assert "meta" in documents
        assert "documents" in documents
        assert isinstance(documents["documents"], list)

    def test_document_count(self, documents):
        """Should have exactly 100 documents."""
        assert len(documents["documents"]) == 100

    def test_unique_ids(self, documents):
        """All document IDs should be unique."""
        ids = [doc["id"] for doc in documents["documents"]]
        assert len(ids) == len(set(ids)), "Duplicate document IDs found"

    def test_sequential_ids(self, documents):
        """Document IDs should be sequential doc_001 to doc_100."""
        ids = sorted([doc["id"] for doc in documents["documents"]])
        expected = [f"doc_{i:03d}" for i in range(1, 101)]
        assert ids == expected

    def test_required_fields(self, documents):
        """All documents should have required fields."""
        required = ["id", "type", "timestamp", "author"]
        for doc in documents["documents"]:
            for field in required:
                assert field in doc, f"Document {doc.get('id', 'unknown')} missing {field}"

    def test_valid_timestamps(self, documents):
        """All timestamps should be valid ISO format."""
        for doc in documents["documents"]:
            try:
                datetime.fromisoformat(doc["timestamp"])
            except ValueError:
                pytest.fail(f"Invalid timestamp in {doc['id']}: {doc['timestamp']}")

    def test_timestamps_in_range(self, documents):
        """All timestamps should be within June 2023 - July 2024."""
        start = datetime(2023, 6, 1)
        end = datetime(2024, 7, 31, 23, 59, 59)

        for doc in documents["documents"]:
            dt = datetime.fromisoformat(doc["timestamp"]).replace(tzinfo=None)
            assert start <= dt <= end, f"Document {doc['id']} timestamp {dt} out of range"

    def test_clients_mentioned_format(self, documents):
        """clients_mentioned should be a list."""
        for doc in documents["documents"]:
            assert "clients_mentioned" in doc
            assert isinstance(doc["clients_mentioned"], list)

    def test_planted_facts_format(self, documents):
        """planted_facts should be a list."""
        for doc in documents["documents"]:
            assert "planted_facts" in doc
            assert isinstance(doc["planted_facts"], list)


class TestGroundTruth:
    def test_valid_json(self, ground_truth):
        """ground_truth.json is valid JSON."""
        assert "meta" in ground_truth
        assert "exact_match_questions" in ground_truth

    def test_question_count(self, ground_truth):
        """Should have 35 questions total."""
        total = (
            len(ground_truth.get("exact_match_questions", []))
            + len(ground_truth.get("multi_document_synthesis_questions", []))
            + len(ground_truth.get("qualitative_questions", []))
            + len(ground_truth.get("temporal_filter_questions", []))
            + len(ground_truth.get("negative_questions", []))
        )
        assert total == 35

    def test_unique_question_ids(self, ground_truth):
        """All question IDs should be unique."""
        ids = []
        for key in ground_truth:
            if isinstance(ground_truth[key], list):
                ids.extend([q.get("id") for q in ground_truth[key] if isinstance(q, dict)])
        ids = [i for i in ids if i]  # Filter None
        assert len(ids) == len(set(ids)), "Duplicate question IDs found"

    def test_exact_match_have_answers(self, ground_truth):
        """Exact match questions should have expected_answer."""
        for q in ground_truth.get("exact_match_questions", []):
            assert "expected_answer" in q, f"Question {q['id']} missing expected_answer"

    def test_qualitative_have_rubric_ids(self, ground_truth):
        """Qualitative questions should reference rubrics."""
        for q in ground_truth.get("qualitative_questions", []):
            assert "rubric_id" in q, f"Question {q['id']} missing rubric_id"


class TestCompanyMeta:
    def test_valid_json(self, company_meta):
        """company_meta.json is valid JSON."""
        assert "meta" in company_meta
        assert "evaluation_questions" in company_meta

    def test_has_synthesizable_facts(self, company_meta):
        """Should have company fundamentals and patterns."""
        assert "company_fundamentals" in company_meta
        assert "financial_patterns" in company_meta
        assert "client_patterns" in company_meta

    def test_meta_questions_count(self, company_meta):
        """Should have 8 meta-questions."""
        assert len(company_meta["evaluation_questions"]) == 8


class TestRubrics:
    def test_valid_json(self, rubrics):
        """qualitative_rubric.json is valid JSON."""
        assert "rubrics" in rubrics

    def test_rubrics_have_required_fields(self, rubrics):
        """Each rubric should have must_mention and scoring."""
        for name, rubric in rubrics["rubrics"].items():
            assert "must_mention" in rubric, f"Rubric {name} missing must_mention"
            assert "scoring" in rubric, f"Rubric {name} missing scoring"

    def test_rubric_references_valid(self, ground_truth, rubrics):
        """All rubric_ids in ground_truth should exist in rubrics."""
        rubric_names = set(rubrics["rubrics"].keys())
        for q in ground_truth.get("qualitative_questions", []):
            rubric_id = q.get("rubric_id")
            if rubric_id:
                assert rubric_id in rubric_names, f"Rubric {rubric_id} not found"


class TestCrossValidation:
    def test_planted_facts_have_questions(self, documents, ground_truth):
        """Documents with planted_facts should have corresponding questions."""
        # Collect all planted fact IDs from documents
        planted_in_docs = set()
        for doc in documents["documents"]:
            planted_in_docs.update(doc.get("planted_facts", []))

        # Collect all planted_fact_ids from questions
        planted_in_questions = set()
        for key in ground_truth:
            if isinstance(ground_truth[key], list):
                for q in ground_truth[key]:
                    if isinstance(q, dict) and "planted_fact_id" in q:
                        planted_in_questions.add(q["planted_fact_id"])

        # Every planted fact in docs should have a question
        missing = planted_in_docs - planted_in_questions - {"multi_fact_synthesis"}
        assert not missing, f"Planted facts without questions: {missing}"
