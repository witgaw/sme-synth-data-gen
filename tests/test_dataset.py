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


@pytest.fixture
def database():
    with open(DATASET_DIR / "database.json", encoding="utf-8") as f:
        return json.load(f)


class TestDocumentsJson:
    def test_valid_json(self, documents):
        """documents.json is valid JSON with expected structure."""
        assert "meta" in documents
        assert "documents" in documents
        assert isinstance(documents["documents"], list)

    def test_document_count(self, documents):
        """Should have exactly 116 documents (100 standard + 16 PDF)."""
        assert len(documents["documents"]) == 116

    def test_unique_ids(self, documents):
        """All document IDs should be unique."""
        ids = [doc["id"] for doc in documents["documents"]]
        assert len(ids) == len(set(ids)), "Duplicate document IDs found"

    def test_sequential_ids(self, documents):
        """Document IDs should be sequential doc_001 to doc_116."""
        ids = sorted([doc["id"] for doc in documents["documents"]])
        expected = [f"doc_{i:03d}" for i in range(1, 117)]
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


class TestPdfDocuments:
    """Tests specific to PDF documents."""

    def test_pdf_document_count(self, documents):
        """Should have 16 PDF documents."""
        pdf_docs = [d for d in documents["documents"] if d.get("format") == "pdf"]
        assert len(pdf_docs) == 16

    def test_pdf_difficulty_distribution(self, documents):
        """Should have 8 easy and 8 hard PDFs."""
        pdf_docs = [d for d in documents["documents"] if d.get("format") == "pdf"]
        easy = [d for d in pdf_docs if d.get("pdf_difficulty") == "easy"]
        hard = [d for d in pdf_docs if d.get("pdf_difficulty") == "hard"]
        assert len(easy) == 8, f"Expected 8 easy PDFs, got {len(easy)}"
        assert len(hard) == 8, f"Expected 8 hard PDFs, got {len(hard)}"

    def test_pdf_documents_have_content(self, documents):
        """All PDF documents should have content field."""
        pdf_docs = [d for d in documents["documents"] if d.get("format") == "pdf"]
        for doc in pdf_docs:
            assert "content" in doc, f"PDF {doc['id']} missing content"
            assert len(doc["content"]) > 100, f"PDF {doc['id']} content too short"

    def test_pdf_documents_have_titles(self, documents):
        """All PDF documents should have title field."""
        pdf_docs = [d for d in documents["documents"] if d.get("format") == "pdf"]
        for doc in pdf_docs:
            assert "title" in doc, f"PDF {doc['id']} missing title"


class TestGroundTruth:
    def test_valid_json(self, ground_truth):
        """ground_truth.json is valid JSON."""
        assert "meta" in ground_truth
        assert "exact_match_questions" in ground_truth

    def test_standard_question_count(self, ground_truth):
        """Should have 35 standard questions (excluding OCR)."""
        total = (
            len(ground_truth.get("exact_match_questions", []))
            + len(ground_truth.get("multi_document_synthesis_questions", []))
            + len(ground_truth.get("qualitative_questions", []))
            + len(ground_truth.get("temporal_filter_questions", []))
            + len(ground_truth.get("negative_questions", []))
        )
        assert total == 35

    def test_ocr_question_count(self, ground_truth):
        """Should have 16 OCR questions."""
        ocr_questions = ground_truth.get("ocr_questions", [])
        assert len(ocr_questions) == 16

    def test_total_question_count(self, ground_truth):
        """Should have 70 total questions."""
        total = (
            len(ground_truth.get("exact_match_questions", []))
            + len(ground_truth.get("multi_document_synthesis_questions", []))
            + len(ground_truth.get("qualitative_questions", []))
            + len(ground_truth.get("temporal_filter_questions", []))
            + len(ground_truth.get("negative_questions", []))
            + len(ground_truth.get("ocr_questions", []))
            + len(ground_truth.get("multi_hop_ocr_questions", []))
            + len(ground_truth.get("database_questions", []))
            + len(ground_truth.get("multi_hop_db_doc_questions", []))
        )
        assert total == 70

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


class TestOcrQuestions:
    """Tests specific to OCR questions."""

    def test_ocr_questions_have_required_fields(self, ground_truth):
        """OCR questions should have requires_ocr and ocr_difficulty."""
        for q in ground_truth.get("ocr_questions", []):
            assert q.get("requires_ocr") is True, f"Question {q['id']} missing requires_ocr"
            assert q.get("ocr_difficulty") in [
                "easy",
                "hard",
            ], f"Question {q['id']} has invalid ocr_difficulty"

    def test_ocr_difficulty_distribution(self, ground_truth):
        """Should have 8 easy and 8 hard OCR questions."""
        ocr_questions = ground_truth.get("ocr_questions", [])
        easy = [q for q in ocr_questions if q.get("ocr_difficulty") == "easy"]
        hard = [q for q in ocr_questions if q.get("ocr_difficulty") == "hard"]
        assert len(easy) == 8, f"Expected 8 easy OCR questions, got {len(easy)}"
        assert len(hard) == 8, f"Expected 8 hard OCR questions, got {len(hard)}"

    def test_ocr_questions_reference_pdf_documents(self, ground_truth, documents):
        """OCR questions should reference PDF documents."""
        pdf_doc_ids = {d["id"] for d in documents["documents"] if d.get("format") == "pdf"}
        for q in ground_truth.get("ocr_questions", []):
            source_docs = q.get("source_documents", [])
            for doc_id in source_docs:
                assert doc_id in pdf_doc_ids, f"Question {q['id']} references non-PDF {doc_id}"


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

        # Collect all planted_fact_ids from questions (including OCR)
        planted_in_questions = set()
        for key in ground_truth:
            if isinstance(ground_truth[key], list):
                for q in ground_truth[key]:
                    if isinstance(q, dict) and "planted_fact_id" in q:
                        planted_in_questions.add(q["planted_fact_id"])

        # Every planted fact in docs should have a question
        missing = planted_in_docs - planted_in_questions - {"multi_fact_synthesis"}
        assert not missing, f"Planted facts without questions: {missing}"

    def test_ocr_questions_match_pdf_facts(self, documents, ground_truth):
        """OCR planted facts should match between documents and questions."""
        # Get planted facts from PDF documents
        pdf_planted_facts = set()
        for doc in documents["documents"]:
            if doc.get("format") == "pdf":
                pdf_planted_facts.update(doc.get("planted_facts", []))

        # Get planted fact IDs from OCR questions
        ocr_question_facts = set()
        for q in ground_truth.get("ocr_questions", []):
            if "planted_fact_id" in q:
                ocr_question_facts.add(q["planted_fact_id"])

        # Every OCR question should reference a fact in PDFs
        for fact_id in ocr_question_facts:
            assert fact_id in pdf_planted_facts, f"OCR question fact {fact_id} not in any PDF"


class TestDatabaseJson:
    """Tests for database.json structure."""

    def test_valid_json(self, database):
        """database.json is valid JSON with expected structure."""
        assert "meta" in database
        assert "schema" in database
        assert "data" in database

    def test_schema_has_required_tables(self, database):
        """Schema should define all required tables."""
        required_tables = [
            "employees",
            "clients",
            "contacts",
            "projects",
            "time_entries",
            "invoices",
            "expenses",
        ]
        for table in required_tables:
            assert table in database["schema"], f"Missing table: {table}"

    def test_data_has_required_tables(self, database):
        """Data should have entries for required tables."""
        required_tables = ["employees", "clients", "contacts", "projects", "invoices"]
        for table in required_tables:
            assert table in database["data"], f"Missing data for table: {table}"
            assert len(database["data"][table]) > 0, f"No data in table: {table}"

    def test_employee_count(self, database):
        """Should have 9 employees."""
        assert len(database["data"]["employees"]) == 9

    def test_client_count(self, database):
        """Should have 8 clients."""
        assert len(database["data"]["clients"]) == 8

    def test_employees_have_required_fields(self, database):
        """Employees should have required fields."""
        required = ["id", "name", "email", "role", "hourly_rate"]
        for emp in database["data"]["employees"]:
            for field in required:
                assert field in emp, f"Employee {emp.get('id')} missing {field}"

    def test_clients_have_required_fields(self, database):
        """Clients should have required fields."""
        required = ["id", "code", "name", "status"]
        for client in database["data"]["clients"]:
            for field in required:
                assert field in client, f"Client {client.get('id')} missing {field}"

    def test_invoices_have_valid_amounts(self, database):
        """Invoice amounts should be positive."""
        for inv in database["data"]["invoices"]:
            assert inv["amount_net"] > 0, f"Invoice {inv['invoice_number']} has invalid amount"

    def test_foreign_key_references_valid(self, database):
        """Foreign keys should reference existing records."""
        client_ids = {c["id"] for c in database["data"]["clients"]}
        employee_ids = {e["id"] for e in database["data"]["employees"]}
        project_ids = {p["id"] for p in database["data"]["projects"]}

        # Check projects reference valid clients
        for proj in database["data"]["projects"]:
            assert proj["client_id"] in client_ids, f"Project {proj['id']} invalid client_id"

        # Check invoices reference valid clients
        for inv in database["data"]["invoices"]:
            assert inv["client_id"] in client_ids, f"Invoice {inv['id']} invalid client_id"

        # Check time_entries reference valid projects and employees
        for te in database["data"]["time_entries"]:
            assert te["project_id"] in project_ids, f"Time entry {te['id']} invalid project_id"
            assert te["employee_id"] in employee_ids, f"Time entry {te['id']} invalid employee_id"


class TestDatabaseQuestions:
    """Tests for database questions in ground_truth."""

    def test_database_question_count(self, ground_truth):
        """Should have 10 database-only questions."""
        db_questions = ground_truth.get("database_questions", [])
        assert len(db_questions) == 10

    def test_multi_hop_db_question_count(self, ground_truth):
        """Should have 4 multi-hop DB+doc questions."""
        multi_hop = ground_truth.get("multi_hop_db_doc_questions", [])
        assert len(multi_hop) == 4

    def test_database_questions_have_sql_hints(self, ground_truth):
        """Database questions should have SQL hints."""
        for q in ground_truth.get("database_questions", []):
            assert "sql_hint" in q, f"Question {q['id']} missing sql_hint"

    def test_multi_hop_questions_have_reasoning(self, ground_truth):
        """Multi-hop DB questions should have reasoning steps."""
        for q in ground_truth.get("multi_hop_db_doc_questions", []):
            assert "reasoning_steps" in q, f"Question {q['id']} missing reasoning_steps"
            assert "db_tables" in q, f"Question {q['id']} missing db_tables"


class TestGeneratedDatabase:
    """Tests for the generated SQLite database."""

    @pytest.fixture
    def generated_db(self, tmp_path, database):
        """Generate a temporary database for testing."""
        import sqlite3

        from scripts.generate_database import (
            create_indexes,
            create_schema,
            create_views,
            insert_data,
        )

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        create_schema(conn, database["schema"])
        insert_data(conn, database["data"])
        create_indexes(conn)
        create_views(conn)
        conn.commit()

        yield conn
        conn.close()

    def test_can_query_employees(self, generated_db):
        """Can query employees table."""
        cursor = generated_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees")
        count = cursor.fetchone()[0]
        assert count == 9

    def test_can_query_anna_kowalska_phone(self, generated_db):
        """Can retrieve planted fact: Anna Kowalska's phone."""
        cursor = generated_db.cursor()
        cursor.execute("SELECT phone FROM contacts WHERE name = 'Anna Kowalska'")
        phone = cursor.fetchone()[0]
        assert phone == "+48 607 777 888"

    def test_can_query_maciej_hire_date(self, generated_db):
        """Can retrieve planted fact: Maciej Boryna's hire date."""
        cursor = generated_db.cursor()
        cursor.execute("SELECT hire_date FROM employees WHERE name = 'Maciej Boryna'")
        hire_date = cursor.fetchone()[0]
        assert hire_date == "2023-02-01"

    def test_can_query_smakosz_hours(self, generated_db):
        """Can retrieve planted fact: hours on Smakosz rebranding."""
        cursor = generated_db.cursor()
        cursor.execute("SELECT SUM(hours) FROM time_entries WHERE project_id = 7")
        total_hours = cursor.fetchone()[0]
        assert total_hours == 87.0

    def test_can_query_invoice_delay(self, generated_db):
        """Can retrieve planted fact: invoice FV/2023/10/003 delay."""
        cursor = generated_db.cursor()
        cursor.execute(
            "SELECT julianday(paid_date) - julianday(due_date) "
            "FROM invoices WHERE invoice_number = 'FV/2023/10/003'"
        )
        days_late = cursor.fetchone()[0]
        assert days_late == 61.0

    def test_views_work(self, generated_db):
        """Views should return data."""
        cursor = generated_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM v_client_revenue")
        count = cursor.fetchone()[0]
        assert count > 0

    def test_foreign_keys_valid(self, generated_db):
        """All foreign key references should be valid."""
        cursor = generated_db.cursor()

        # Check no orphan invoices
        cursor.execute(
            "SELECT COUNT(*) FROM invoices i "
            "LEFT JOIN clients c ON i.client_id = c.id WHERE c.id IS NULL"
        )
        orphans = cursor.fetchone()[0]
        assert orphans == 0, "Found invoices with invalid client_id"

        # Check no orphan time entries
        cursor.execute(
            "SELECT COUNT(*) FROM time_entries t "
            "LEFT JOIN projects p ON t.project_id = p.id WHERE p.id IS NULL"
        )
        orphans = cursor.fetchone()[0]
        assert orphans == 0, "Found time_entries with invalid project_id"
