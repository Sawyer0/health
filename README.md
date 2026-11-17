# Head & Neck Clinical PRO Triage Dashboard & Pipeline

Clinical Patient-Reported Outcomes (PRO) ingestion, conflict detection, and triage dashboard for Head & Neck cancer oncology care teams.

## Architecture

```text
health/
├── main.py                 # CLI pipeline entrypoint
├── app.py                  # FastAPI HTTP entrypoint
├── constants.py            # Shared config & domain constants
├── domain/                 # Pure domain models & business rules (no I/O)
│   ├── schema.py           # SymptomReport, StoredSymptomReport, ConflictEvent
│   ├── parser.py           # Free-text & questionnaire extraction
│   └── conflicts.py        # Divergence, contradiction, and med-delta detection
├── storage/                # SQLite persistence subsystem
│   ├── store.py            # ReportStore connection & query API
│   ├── queries.py          # SQL DDL & analytical queries
│   └── serializer.py       # Row <-> model mapping
├── charts/                 # Longitudinal plotting subsystem
│   ├── data.py             # ChartSeries time-series preparation
│   └── plot.py             # Matplotlib dual-track rendering
├── components/             # UI & CLI presentation layer
│   ├── badge.py            # Badge primitive
│   ├── card.py             # Base card container
│   ├── report_card.py      # Paginated patient report card
│   ├── dashboard.py        # Full dashboard HTML/CSS/JS shell
│   └── cli.py              # Terminal review queue table
└── tests/
    └── test_reports.py     # Unit, functional, API, and chart test suite
```

## Setup & Quickstart

### Prerequisites
- Python 3.11+
- Virtual environment with dependencies installed:

```bash
pip install -r requirements.txt
```

### Running the Pipeline (CLI Demo)
To ingest reports, detect conflicts, log medication changes, print the terminal triage table, and generate the trend chart:

```bash
python main.py data/patient_reports.json data/reports.db
```

Optional flags:
- `--reset-db`: Wipes and cleanly re-initializes SQLite before ingestion.
- `--serve`: Starts the FastAPI web server on `http://127.0.0.1:8000`.

### Running the Web Server Directly
```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```
- **Interactive Dashboard**: `http://127.0.0.1:8000/dashboard`
- **Ingest Report (`POST`)**: `http://127.0.0.1:8000/reports`
- **Batch Ingest (`POST`)**: `http://127.0.0.1:8000/reports/batch`
- **Review Queue Endpoint**: `http://127.0.0.1:8000/review-queue`
- **Conflicts Endpoint**: `http://127.0.0.1:8000/conflicts`
- **Dynamic Patient Chart**: `http://127.0.0.1:8000/patient/{patient_id}/chart`
- **OpenAPI / Swagger**: `http://127.0.0.1:8000/docs`

## Verification & Testing
Run all unit and functional tests:
```bash
pytest -v tests/
```

Run strict type checking:
```bash
mypy --strict main.py app.py constants.py domain storage charts components tests
```
