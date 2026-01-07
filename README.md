# X-Ray SDK & API

An observability system for debugging non-deterministic, multi-step algorithmic pipelines (LLMs, Search, Ranking).

## Overview
X-Ray helps you answer *"Why did my system make this decision?"* by capturing rich context (inputs, outputs, metadata) at every step of your pipeline.

## Project Structure
- `api/`: FastAPI service backed by SQLite.
- `sdk/`: Python SDK for instrumenting your code.
- `docs/`: Architecture and design documents.
- `examples/`: Mock pipelines demonstrating real-world usage.

## Setup & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the API Server
```bash
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```
The API will be available at `http://localhost:8000`.

### 3. Run the Example Pipeline
In a new terminal window:
```bash
PYTHONPATH=. python3 examples/scenario_competitor_discovery.py
```
This runs a mock "Competitor Discovery" pipeline that generates keywords, searches for products, filters them, and selects a winner.

### 4. Query Traces
You can inspect the recorded traces via the API:
```bash
curl -s http://localhost:8000/v1/runs | python3 -m json.tool
```

## Documentation
- **[Architecture](docs/ARCHITECTURE.md)**: Logic behind the data model and trade-offs.
- **[Walkthrough](walkthrough.md)**: Detailed guide and verification results.