# X-Ray SDK & API

**Decision Forensics for Non-Deterministic Pipelines**

An observability system that answers *"Why did my pipeline make this decision?"* rather than *"What functions were called?"*

---

## 🎯 What is X-Ray?

Modern software relies on multi-step, non-deterministic processes (LLMs, ranking algorithms, filters). When outputs are wrong, traditional logging shows *what* happened but not *why*.

X-Ray provides **decision forensics** by capturing:
- Which candidates were considered
- Why they were accepted or rejected
- Scores and reasoning at each step
- Cross-pipeline queryability

**Example Use Case:** A competitor discovery system incorrectly matches a "phone case" with a "laptop stand." X-Ray lets you trace back through the pipeline to find the LLM hallucinated a bad keyword, filters were too lenient, and ranking used surface-level similarity.

---

## 📁 Project Structure

```
xray-sdk/
├── sdk/                      # Python SDK
│   ├── core.py              # Context managers (xray_run, xray_step)
│   ├── client.py            # Fire-and-forget HTTP client
│   └── __init__.py
├── api/                      # FastAPI service
│   ├── main.py              # App entry point
│   ├── models.py            # SQLAlchemy models (3-tier: Run→Step→Candidate)
│   ├── schemas.py           # Pydantic schemas
│   ├── routes.py            # REST endpoints
│   └── database.py          # Database setup
├── examples/                 # Demo scenarios
│   ├── scenario_competitor_discovery.py
│   ├── scenario_categorization.py
│   ├── scenario_listing_optimization.py
│   └── scenario_bad_match_demo.py        # Debugging walkthrough
├── tests/                    # Unit + integration tests
│   ├── test_sdk.py
│   ├── test_api.py
│   └── test_integration.py
├── ARCHITECTURE.md           # Comprehensive design doc
├── SUBMISSION_CHECKLIST.md   # Pre-submission verification
├── VIDEO_WALKTHROUGH_SCRIPT.md
└── requirements.txt
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Requirements:**
- Python 3.8+
- FastAPI
- SQLAlchemy
- Pydantic
- Requests
- Pytest (for tests)

### 2. Start the API Server

```bash
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

**Verify it's running:**
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### 3. Run Example Pipelines

In a new terminal:

**Competitor Discovery:**
```bash
PYTHONPATH=. python3 examples/scenario_competitor_discovery.py
```

**Product Categorization:**
```bash
PYTHONPATH=. python3 examples/scenario_categorization.py
```

**Bad Match Debugging Demo:**
```bash
PYTHONPATH=. python3 examples/scenario_bad_match_demo.py
```

### 4. Query Traces

**Get all runs:**
```bash
curl -s http://localhost:8000/v1/runs | python3 -m json.tool
```

**Filter by pipeline type:**
```bash
curl -s 'http://localhost:8000/v1/runs?pipeline_type=CompetitorDiscovery' | python3 -m json.tool
```

**Query steps by type:**
```bash
curl -s 'http://localhost:8000/v1/steps?step_type=FILTER' | python3 -m json.tool
```

**Get specific run with all steps:**
```bash
curl -s http://localhost:8000/v1/runs/{run_id} | python3 -m json.tool
```

---

## 📖 How to Use

### Minimal Instrumentation

Get *something* useful with just context managers:

```python
from sdk import xray_run, xray_step

with xray_run("CompetitorDiscovery"):
    with xray_step("GenerateKeywords", "LLM"):
        keywords = generate_keywords(product)

    with xray_step("FilterCompetitors", "FILTER"):
        filtered = apply_filters(candidates)
```

**What you get:**
- Run/step hierarchy
- Timing for each step
- Success/failure status

### Full Instrumentation

Add stats, candidates, and reasoning:

```python
from sdk import xray_run, xray_step

with xray_run("CompetitorDiscovery", metadata={"product_id": "prod_123"}):

    with xray_step("FilterCompetitors", "FILTER") as step:
        kept = []
        rejected_with_reasons = []

        for candidate in candidates:
            if candidate["price"] > 100:
                rejected_with_reasons.append(
                    (candidate, f"Price ${candidate['price']} exceeds threshold $100")
                )
            else:
                kept.append(candidate)

        step.log_stats(
            input_count=len(candidates),
            output_count=len(kept),
            filter_rate=len(rejected_with_reasons) / len(candidates)
        )

        step.log_sampled_candidates(
            accepted=kept,
            rejected=rejected_with_reasons  # Tuple format: (candidate, reasoning)
        )
```

**What you get:**
- All of the above, plus:
- Input/output counts
- Rejection reasons
- Custom metrics (filter_rate, etc.)
- Sampled candidates for analysis

### Logging Candidates with Scores

```python
with xray_step("RankAndSelect", "LLM") as step:
    # 3-tuple format: (candidate, score, reasoning)
    step.log_sampled_candidates(
        selected=[
            (
                {"id": "prod_1", "title": "Winner"},
                {"relevance": 0.95, "quality": 0.92},
                "Best overall match"
            )
        ]
    )
```

---

## 🧪 Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_sdk.py -v
pytest tests/test_api.py -v
pytest tests/test_integration.py -v

# With coverage
pytest tests/ --cov=sdk --cov=api
```

**Test Coverage:**
- SDK unit tests with mocking
- API integration tests
- Full pipeline integration tests
- Reasoning and score field tests
- Graceful degradation tests (API unavailable)

---

## 🏗️ Architecture Highlights

### 3-Tier Data Model

```
Run (pipeline execution)
├── id, pipeline_type, metadata
├── repository, version (for tracking code changes)
└── Steps (1:N)
    ├── id, step_name, step_type
    ├── stats (JSONB: input_count, output_count, custom metrics)
    └── CandidateDecisions (1:N)
        ├── candidate_id, attributes (JSONB)
        ├── decision (accepted | rejected | selected)
        ├── score (JSONB)
        └── reasoning (text)
```

### Key Design Decisions

**1. Why separate CandidateDecision table?**
- **Alternative:** Embed in `steps.candidates` JSONB
- **Problem:** 5,000 candidates = 5MB row → PostgreSQL performance degrades
- **Solution:** Separate table with indexed `step_id`

**2. Why `step_type` taxonomy?**
- Enables cross-pipeline queries: "Show all FILTER steps that eliminated >90%"
- Without it, teams use different names → no aggregation possible
- Constraint on developers, but necessary for queryability

**3. Fire-and-forget client**
- 2-second timeout on API calls
- Exceptions swallowed, logged as warnings
- **Trade-off:** Pipeline never blocks, but you might lose traces

**4. 3-tier capture strategy**
- Tier 1: Summary stats (always) → 1KB per step
- Tier 2: Sampled candidates (developer-controlled) → 50KB per step
- Tier 3: Full capture (opt-in) → 5MB+ per step
- **Trade-off:** Storage cost vs debuggability

---

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Comprehensive design document with:
  - Data model rationale
  - Debugging walkthrough (phone case vs laptop stand)
  - Queryability design
  - Performance & scale considerations
  - Developer experience
  - Real-world application
  - API specification

- **[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md)**: Pre-submission verification

- **[VIDEO_WALKTHROUGH_SCRIPT.md](VIDEO_WALKTHROUGH_SCRIPT.md)**: Talking points for demo

---

## 🔍 Debugging Example: Bad Match

**Scenario:** A "laptop stand" is matched with a "phone case" competitor.

**Run the demo:**
```bash
PYTHONPATH=. python3 examples/scenario_bad_match_demo.py
```

**Debug with X-Ray:**
```bash
# Get the run
curl -s 'http://localhost:8000/v1/runs?pipeline_type=CompetitorDiscovery' | python3 -m json.tool

# Inspect steps
curl -s http://localhost:8000/v1/runs/{run_id} | python3 -m json.tool
```

**What you'll find:**
1. **GenerateKeywords step**: LLM hallucinated "phone case" as a keyword
2. **FilterCompetitors step**: Phone case passed (good price/rating, no category check)
3. **RankAndSelect step**: Phone case scored high due to surface similarity

**Fix:** Add category matching to filter step.

---

## 🚧 Known Limitations

### Current Implementation
- **SQLite only**: Production would use PostgreSQL for JSONB queries
- **No advanced query filters**: `stats.filter_rate__gt=0.9` not yet implemented
- **No sampling strategies**: Always captures what developer logs (no auto-sampling)
- **No async buffering**: If API is down, traces are lost (not buffered locally)

### Scope Constraints (Take-Home)
- **No UI**: API-first, querying via curl/code
- **No authentication**: Single-tenant, localhost only
- **No schema validation**: step_type values not enforced by SDK
- **Limited test coverage**: Core flows tested, edge cases not exhaustive

---

## 🔮 Future Improvements

### Production-Ready Enhancements
1. **Adaptive Sampling**
   - Auto-increase capture rate for steps with high variance
   - Focus on decision boundaries (candidates near score threshold)

2. **Async SDK with Local Buffering**
   - Buffer traces locally if API unreachable
   - Retry with exponential backoff
   - Circuit breaker pattern

3. **Advanced Query API**
   - JSONB query operators: `stats.filter_rate__gt=0.9`
   - Aggregations: "Average filter rate by pipeline_type"
   - GraphQL endpoint for complex queries

4. **Schema Validation**
   - SDK validates `step_type` against whitelist
   - API enforces required fields per step_type

5. **Time-Travel Comparisons**
   - "Show Run A vs Run B side-by-side"
   - Regression detection: "Why did this week's runs get slower?"

6. **Automated Failure Detection**
   - "80% of LLM failures are timeouts" → alert
   - Anomaly detection: "Step 3 took 10x longer than usual"

---

## 📝 API Reference

### Endpoints

**Create Run**
```http
POST /v1/runs
{
  "pipeline_type": "CompetitorDiscovery",
  "metadata": {"product_id": "prod_123"},
  "repository": "github.com/company/repo",
  "version": "a3f8c2d"
}
```

**Record Step**
```http
POST /v1/steps
{
  "run_id": "uuid",
  "step_name": "FilterCompetitors",
  "step_type": "FILTER",
  "stats": {"input_count": 120, "output_count": 12},
  "candidates": [
    {
      "candidate_id": "prod_1",
      "attributes": {"price": 150},
      "decision": "rejected",
      "reasoning": "Price exceeds threshold"
    }
  ]
}
```

**Query Runs**
```http
GET /v1/runs?pipeline_type=CompetitorDiscovery&status=SUCCESS&limit=10
```

**Query Steps**
```http
GET /v1/steps?step_type=FILTER&status=FAILURE
```

**Get Run by ID**
```http
GET /v1/runs/{run_id}
```

---

## 🤝 Contributing

This is a take-home assignment submission. Not accepting contributions, but feel free to fork and extend!

---

## 📄 License

MIT License - See LICENSE file for details.

---

## 🙏 Acknowledgments

Built as a take-home assignment for Equal Collective's Founding Full-Stack Engineer position.

**Assignment Requirements:**
- Build X-Ray SDK and API for decision forensics
- Write comprehensive architecture document
- Create video walkthrough (10 min max)
- Demonstrate debugging workflow

**Time Spent:** ~[Fill in after completion] hours

---

## 📬 Contact

[Your Name] - [Your Email]

**Links:**
- GitHub: [Repo URL]
- Video Walkthrough: [Video URL]
- LinkedIn: [Optional]

---

**Built with:** Python, FastAPI, SQLAlchemy, Pydantic, SQLite