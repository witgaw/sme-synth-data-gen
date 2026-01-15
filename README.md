# Polish SME Dataset for RAG Evaluation

A synthetic **Polish-language** dataset of business documents from a fictional marketing agency. Designed for testing and evaluating RAG (Retrieval-Augmented Generation) systems.

> **Language:** All documents are in Polish (polski).

## Overview

The dataset mimics internal documents of Kreatywna Fala Sp. z o.o., a small marketing agency in Wrocław, Poland. Documents span June 2023 - July 2024 and include realistic business scenarios: client negotiations, project crises, team communications, financial reports.

### Key Features

- **116 documents** across multiple types (emails, reports, spreadsheets, presentations, meeting notes, PDFs)
- **Polish business language** with authentic terminology and conventions
- **38 planted facts** with ground truth for quantitative evaluation
- **59 evaluation questions** (35 standard + 8 meta + 16 OCR)
- **Interconnected narratives** testing multi-document reasoning
- **Optional OCR testing** with scanned-style PDFs (easy and hard difficulty)

## Installation

Requires [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Clone the repository
git clone https://github.com/your-username/sme-synth-data-gen.git
cd sme-synth-data-gen

# Install dependencies
uv sync
```

## Usage

### Reading the Dataset

The core dataset is in `dataset/documents.json` - no dependencies required:

```python
import json

with open('dataset/documents.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for doc in data['documents']:
    print(f"{doc['id']}: {doc['type']} - {doc.get('title') or doc.get('subject')}")
```

### Generating Actual Files

To create .eml, .docx, .xlsx, .pptx files from the JSON:

```bash
# Generate files to output/ directory (excludes PDFs by default)
uv run generate

# Or specify custom output directory
uv run generate --output-dir my_output/
```

### Running Tests

```bash
uv sync --extra dev  # includes pytest, ruff
uv run pytest
```

## OCR Testing (Optional)

The dataset includes 16 scanned PDF documents for testing OCR capabilities:

| Difficulty | Count | Description |
|------------|-------|-------------|
| Easy | 8 | Clean scans - contracts, invoices, bank confirmations |
| Hard | 8 | Degraded quality - handwritten notes, faxes, crumpled receipts, multi-column layouts |

### Generating PDFs

```bash
# Install PDF generation dependencies
uv sync --extra pdf

# Generate all files including PDFs
uv run generate --include-pdf
```

### Hard PDF Challenges

The "hard" PDFs include realistic degradation effects:
- Slight rotation (0.5-2.5 degrees)
- Gaussian noise
- Reduced contrast
- Lower DPI (150-200)
- JPEG compression artifacts

OCR questions in `ground_truth.json` are marked with `"requires_ocr": true` and `"ocr_difficulty": "easy"|"hard"`. Skip these if not testing OCR pipelines.

## Repository Structure

```
├── README.md
├── LICENSE
├── pyproject.toml
│
├── dataset/
│   ├── documents.json           # 116 documents (100 standard + 16 PDF)
│   ├── ground_truth.json        # 51 evaluation questions (35 + 16 OCR)
│   ├── qualitative_rubric.json  # Scoring rubrics for narrative questions
│   └── company_meta.json        # Synthesizable facts + 8 meta-questions
│
├── context/
│   └── company_bible.md         # Company background, team, clients, timeline
│
├── scripts/
│   └── generate_files.py        # File generator (entry point: `generate`)
│
└── tests/
    └── test_dataset.py          # Dataset validation tests
```

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total Documents | 116 |
| Standard Documents | 100 |
| OCR Documents (PDF) | 16 (8 easy, 8 hard) |
| Language | Polish |
| Document Types | 8+ (emails, reports, proposals, meeting notes, spreadsheets, presentations, PDFs) |
| Time Range | June 2023 - July 2024 |
| Clients | 5 |
| Team Members | 10 |
| Planted Facts | 38 (22 standard + 16 OCR) |
| Evaluation Questions | 59 total |

## Evaluation Questions

| Category | Count | Description |
|----------|-------|-------------|
| Exact Match | 19 | Single fact retrieval (dates, amounts, names) |
| Multi-Document Synthesis | 4 | Combine information across documents |
| Qualitative/Narrative | 4 | Complex relationships, scored with rubrics |
| Temporal Filter | 3 | Date-based retrieval |
| Negative | 5 | Absent or out-of-scope information |
| Meta (synthesizable) | 8 | Implicit facts derivable from multiple documents |
| **OCR (optional)** | **16** | Facts in scanned PDFs (8 easy, 8 hard) |

### Meta-Questions

The `company_meta.json` file contains questions testing a system's ability to aggregate implicit knowledge:

- Company headcount and organizational structure
- Typical contract sizes and financial patterns
- Common operational issues and resolution approaches
- Implicit company values and communication culture

## Key Narratives

1. **ModaNet Drama:** Scope creep → budget overrun → client complaints → account handover → recovery
2. **Smakosz Crisis:** Delivery delays → payment withheld → resolution meeting → relationship rebuilt
3. **MaszBud Sales:** 10-month B2B cycle → management change → deal closed
4. **Boryna's Growth:** Junior account manager's learning journey

## License

MIT License. See [LICENSE](LICENSE) file.

## Technical Details

- **Generated by:** Claude (Sonnet 4.5 + Opus 4.5)
- **Encoding:** UTF-8
- **Date format:** ISO 8601 with timezone
- **Currency:** PLN (Polish Złoty)

---

*All names, companies, and events are entirely fictional. Any resemblance to real entities is coincidental.*
