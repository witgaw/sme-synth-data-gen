# Manual Verification Guide

This document explains how to manually verify ground truth answers in the dataset.

## Overview

Each question type has different verification methods:

| Question Type | Verification Source |
|---------------|---------------------|
| Document questions | `source_documents` → check in `documents.json` |
| OCR questions | `source_documents` → check PDF content in `documents.json` |
| Database questions | `sql_hint` + `db_tables` → run against SQLite |
| Multi-hop questions | `reasoning_steps` → follow step-by-step |

## Setup

```bash
# Generate all files including database
uv run generate --include-db --include-pdf

# Files will be in output/
ls output/
```

## Verification by Question Type

### 1. Exact Match Questions (`exact_match_questions`)

These have a single correct answer found in one document.

**Fields:**
- `source_documents`: List of document IDs containing the answer
- `planted_fact_id`: ID linking to the planted fact
- `expected_answer`: The correct answer

**Example verification:**

```bash
# Question q001: "When did Maciej Boryna sign contract with Smakosz?"
# source_documents: ["doc_007"]
# expected_answer: "2023-07-26"

# Verify by searching documents.json:
jq '.documents[] | select(.id == "doc_007") | {id, type, timestamp, subject}' dataset/documents.json
```

Or in Python:
```python
import json

with open('dataset/documents.json') as f:
    docs = json.load(f)

doc = next(d for d in docs['documents'] if d['id'] == 'doc_007')
print(doc['timestamp'])  # Should contain 2023-07-26
```

### 2. Multi-Document Synthesis Questions

Require combining information from multiple documents.

**Example:**
```bash
# Question q020: "Total value of Browar contract in 2023"
# source_documents: ["doc_001", "doc_002", "doc_016"]

# Check each document:
jq '.documents[] | select(.id == "doc_001" or .id == "doc_002" or .id == "doc_016") | {id, type}' dataset/documents.json
```

### 3. OCR Questions (`ocr_questions`)

Facts embedded in PDF documents. The `content` field in `documents.json` contains the text that would be extracted via OCR.

**Example:**
```bash
# Question q_ocr_009: "MaszBud annual marketing budget from handwritten notes"
# source_documents: ["doc_109"]
# expected_answer: "50000"

# Check the PDF content:
jq '.documents[] | select(.id == "doc_109") | .content' dataset/documents.json | head -20
# Look for "BUDŻET: 50k/rok" in the content
```

### 4. Database Questions (`database_questions`)

Answerable via SQL queries against the SQLite database.

**Fields:**
- `sql_hint`: Example SQL query
- `db_tables`: Tables involved
- `expected_answer`: The correct answer

**Verification:**
```bash
# Question q_db_001: "Anna Kowalska's phone number"
# sql_hint: SELECT phone FROM contacts WHERE name = 'Anna Kowalska'
# expected_answer: "+48 607 777 888"

sqlite3 output/kreatywna_fala_crm.db "SELECT phone FROM contacts WHERE name = 'Anna Kowalska'"
# Output: +48 607 777 888
```

**All database questions:**
```bash
# q_db_002: Maciej Boryna hire date
sqlite3 output/kreatywna_fala_crm.db "SELECT hire_date FROM employees WHERE name = 'Maciej Boryna'"
# Expected: 2023-02-01

# q_db_003: Art Director hourly rate
sqlite3 output/kreatywna_fala_crm.db "SELECT hourly_rate FROM employees WHERE role = 'Art Director'"
# Expected: 170

# q_db_004: Browar 2023 total invoices (gross)
sqlite3 output/kreatywna_fala_crm.db "SELECT SUM(amount_gross) FROM invoices WHERE client_id = 1 AND strftime('%Y', paid_date) = '2023'"
# Expected: 31365.0

# q_db_005: Invoice FV/2023/10/003 delay
sqlite3 output/kreatywna_fala_crm.db "SELECT julianday(paid_date) - julianday(due_date) FROM invoices WHERE invoice_number = 'FV/2023/10/003'"
# Expected: 61.0

# q_db_006: Browar spring 2024 subcontractor costs
sqlite3 output/kreatywna_fala_crm.db "SELECT SUM(amount_net) FROM expenses WHERE project_id = 4"
# Expected: 13000.0

# q_db_007: MaszBud NIP
sqlite3 output/kreatywna_fala_crm.db "SELECT nip FROM clients WHERE code = 'MASZBUD'"
# Expected: 8973456789

# q_db_008: Smakosz rebranding total hours
sqlite3 output/kreatywna_fala_crm.db "SELECT SUM(hours) FROM time_entries WHERE project_id = 7"
# Expected: 87.0

# q_db_009: Highest revenue client
sqlite3 output/kreatywna_fala_crm.db "SELECT c.name, SUM(i.amount_net) as revenue FROM clients c JOIN invoices i ON c.id = i.client_id GROUP BY c.id ORDER BY revenue DESC LIMIT 1"
# Expected: Browar Regionalny "Wroclavia"

# q_db_010: Creative department headcount
sqlite3 output/kreatywna_fala_crm.db "SELECT COUNT(*) FROM employees WHERE department = 'Creative'"
# Expected: 3
```

### 5. Multi-Hop Questions

Require combining multiple sources. Use `reasoning_steps` to verify step-by-step.

**Example: q_mh_001**
```
Question: "By how much PLN did initial MaszBud proposal exceed client's budget from handwritten notes?"
Expected: 2000 PLN

Reasoning steps:
1. OCR doc_109 (handwritten notes) → budget 50,000 PLN
2. Read doc_015 (proposal) → initial offer 52,000 PLN
3. Calculate: 52,000 - 50,000 = 2,000 PLN
```

Verify:
```bash
# Step 1: Check handwritten notes
jq '.documents[] | select(.id == "doc_109") | .key_figures.budget' dataset/documents.json
# Output: 50000

# Step 2: Check proposal (need to find the amount in content or metadata)
jq '.documents[] | select(.id == "doc_015") | {id, type, title}' dataset/documents.json

# Step 3: Calculate difference
echo $((52000 - 50000))
# Output: 2000
```

**Example: q_dbdoc_002**
```
Question: "Did Smakosz invoice delay occur before or after complaint meeting?"

Reasoning steps:
1. DB: Invoice FV/2023/10/003 due 2023-10-15, paid 2023-12-15 (61 days late)
2. Docs: doc_010 - email about overdue payment dated 2023-11-15
3. Docs: doc_013 - complaint meeting on 2023-12-01
4. Timeline: Due Oct 15 → Email Nov 15 → Meeting Dec 1 → Paid Dec 15
```

Verify:
```bash
# Step 1: Check invoice dates
sqlite3 output/kreatywna_fala_crm.db "SELECT due_date, paid_date FROM invoices WHERE invoice_number = 'FV/2023/10/003'"
# Output: 2023-10-15|2023-12-15

# Step 2: Check email date
jq '.documents[] | select(.id == "doc_010") | .timestamp' dataset/documents.json
# Should be around 2023-11-15

# Step 3: Check meeting date
jq '.documents[] | select(.id == "doc_013") | .timestamp' dataset/documents.json
# Should be around 2023-12-01
```

## Bulk Verification Script

Run all database verifications at once:

```bash
#!/bin/bash
DB="output/kreatywna_fala_crm.db"

echo "=== Database Question Verification ==="

echo -n "q_db_001 (Anna phone): "
sqlite3 $DB "SELECT phone FROM contacts WHERE name = 'Anna Kowalska'"

echo -n "q_db_002 (Maciej hire): "
sqlite3 $DB "SELECT hire_date FROM employees WHERE name = 'Maciej Boryna'"

echo -n "q_db_003 (Art Director rate): "
sqlite3 $DB "SELECT hourly_rate FROM employees WHERE role = 'Art Director'"

echo -n "q_db_004 (Browar 2023 gross): "
sqlite3 $DB "SELECT SUM(amount_gross) FROM invoices WHERE client_id = 1 AND strftime('%Y', paid_date) = '2023'"

echo -n "q_db_005 (Invoice delay): "
sqlite3 $DB "SELECT julianday(paid_date) - julianday(due_date) FROM invoices WHERE invoice_number = 'FV/2023/10/003'"

echo -n "q_db_006 (Browar expenses): "
sqlite3 $DB "SELECT SUM(amount_net) FROM expenses WHERE project_id = 4"

echo -n "q_db_007 (MaszBud NIP): "
sqlite3 $DB "SELECT nip FROM clients WHERE code = 'MASZBUD'"

echo -n "q_db_008 (Smakosz hours): "
sqlite3 $DB "SELECT SUM(hours) FROM time_entries WHERE project_id = 7"

echo -n "q_db_009 (Top client): "
sqlite3 $DB "SELECT c.name FROM clients c JOIN invoices i ON c.id = i.client_id GROUP BY c.id ORDER BY SUM(i.amount_net) DESC LIMIT 1"

echo -n "q_db_010 (Creative count): "
sqlite3 $DB "SELECT COUNT(*) FROM employees WHERE department = 'Creative'"
```

## Verification Checklist

For each question type, verify:

- [ ] **Exact match**: Answer appears verbatim in source document
- [ ] **Multi-doc synthesis**: All source documents contain relevant pieces
- [ ] **Qualitative**: Rubric criteria can be satisfied from sources
- [ ] **Temporal filter**: Expected documents fall within date range
- [ ] **Negative**: Information is genuinely absent from dataset
- [ ] **OCR**: Answer appears in PDF `content` field
- [ ] **Database**: SQL query returns expected answer
- [ ] **Multi-hop**: Each reasoning step is verifiable

## Common Issues

1. **Date formats**: Documents use ISO 8601 (`2023-07-26T14:00:00+02:00`), answers may be simplified (`2023-07-26`)

2. **Currency**: All amounts in PLN. Some answers include "PLN" suffix, some don't.

3. **Names**: May vary (e.g., "Browar Wroclavia" vs "Browar Regionalny Wroclavia Sp. z o.o.")

4. **Rounding**: Percentage calculations may have slight variations (e.g., 37.5% vs 38%)
