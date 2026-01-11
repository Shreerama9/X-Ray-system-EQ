# X-Ray SDK & API Architecture

## Table of Contents
1. [System Overview](#system-overview)
2. [Data Model Rationale](#data-model-rationale)
3. [Debugging Walkthrough](#debugging-walkthrough)
4. [Queryability](#queryability)
5. [Performance & Scale](#performance--scale)
6. [Developer Experience](#developer-experience)
7. [Real-World Application](#real-world-application)
8. [API Specification](#api-specification)
9. [What's Next](#whats-next)

---

## System Overview

X-Ray is a decision forensics system designed to answer "Why did my pipeline make this decision?" rather than "What functions were called?"

```
┌─────────────────────────────────────────────────────────────────┐
│                      Application Code                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  with xray_run("CompetitorDiscovery", metadata=...):      │  │
│  │    with xray_step("GenerateKeywords", "LLM"):             │  │
│  │      keywords = generate_keywords(product)                │  │
│  │      step.log_stats(input_count=1, output_count=3)        │  │
│  │                                                            │  │
│  │    with xray_step("FilterCompetitors", "FILTER"):         │  │
│  │      filtered = filter_by_price(candidates)               │  │
│  │      step.log_sampled_candidates(                         │  │
│  │        accepted=kept, rejected=dropped)                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ Async HTTP POST                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              X-Ray SDK (Fire-and-Forget)                  │  │
│  │  • Context management (run/step)                          │  │
│  │  • Serialization                                          │  │
│  │  • Graceful degradation                                   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        X-Ray API                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ POST /runs   │  │ POST /steps  │  │ GET /runs?filters... │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
│                          ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              PostgreSQL/SQLite Database                   │  │
│  │                                                            │  │
│  │  ┌──────────┐       ┌───────────┐       ┌──────────────┐  │  │
│  │  │   Runs   │───────│   Steps   │───────│  Candidates  │  │  │
│  │  └──────────┘ 1:N   └───────────┘ 1:N   └──────────────┘  │  │
│  │                                                            │  │
│  │  Indexes on: pipeline_type, step_type, stats.* (JSONB)   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Core Design Principles
1. **Decision-centric**: Model decisions, not function calls
2. **Fire-and-forget**: Never block the main pipeline
3. **Graceful degradation**: Pipeline continues even if X-Ray is down
4. **Cross-pipeline queryability**: Use standardized conventions

---

## Data Model Rationale

### Core Schema

```
Run
├── id: UUID
├── pipeline_type: string          # "CompetitorDiscovery", "ListingOptimization"
├── started_at: timestamp
├── status: enum                    # RUNNING, SUCCESS, FAILURE
├── metadata: jsonb                 # {product_id, user_id, ...}
├── repository: string              # Git repo for version tracking
└── version: string                 # Commit SHA or tag

Step
├── id: UUID
├── run_id: FK(Run)
├── step_name: string               # "FilterCompetitors"
├── step_type: enum                 # LLM, FILTER, API, RANKING
├── status: enum                    # SUCCESS, FAILURE
├── started_at: timestamp
├── ended_at: timestamp
├── input_summary: string           # "Count: 120 candidates"
├── output_summary: string          # "Count: 12 candidates (90% filtered)"
├── stats: jsonb                    # {input_count, output_count, custom_metrics}
├── inputs: jsonb                   # Optional: full input snapshot
├── outputs: jsonb                  # Optional: full output snapshot
└── meta: jsonb                     # {error, config, etc.}

CandidateDecision
├── id: UUID
├── step_id: FK(Step)
├── candidate_id: string            # Domain-specific ID
├── attributes: jsonb               # {title, price, rating, category, ...}
├── decision: enum                  # accepted, rejected, selected
├── score: jsonb                    # {relevance: 0.85, quality: 0.92}
└── reasoning: string               # "Rejected: price $150 exceeds threshold $100"
```

### Why This Structure?

**1. Three-tier hierarchy (Run → Step → Candidate)**

This mirrors how engineers mentally debug: "Which run failed?" → "Which step failed?" → "Which candidate was wrongly accepted/rejected?"

**2. Explicit `step_type` taxonomy**

Standardizing on LLM, FILTER, API, RANKING enables cross-pipeline queries like "show all FILTER steps that eliminated >90% of candidates" without requiring developers to use identical step names.

**3. Dual summary/detail pattern**

Steps have both `input_summary/output_summary` (always captured, lightweight) and optional `inputs/outputs` (opt-in, full detail). This balances debuggability with storage cost.

**4. JSONB for `attributes` and `stats`**

Different pipelines evaluate different attributes (products have price/rating, categories have hierarchy/keywords). JSONB allows schema flexibility while maintaining queryability via PostgreSQL's JSON operators.

**5. Separate `CandidateDecision` table**

Rather than embedding all candidates in Step.candidates (which would bloat rows for steps with 5,000 candidates), we use a separate table with indexed `step_id` for efficient querying.

### Alternatives Considered

| Alternative | Why Rejected |
|------------|--------------|
| **Flat event stream** (no hierarchy) | Cannot query "all steps in run X". Poor debuggability. |
| **Function-level tracing** (OpenTelemetry-style) | Captures "what happened" (timing), not "why" (decisions). |
| **Domain-specific schemas** (separate tables per pipeline) | Cannot query across pipelines. Doesn't scale to 100+ pipeline types. |
| **Embedding all candidates in Step.candidates** | PostgreSQL row size limits. Queries become slow with 5K+ candidates per step. |
| **No `step_type` taxonomy** | "Show all ranking failures" query becomes impossible without convention. |

### What Breaks With Different Choices

**If we removed `step_type`:**
- Cross-pipeline queries like "show all LLM steps with errors" become impossible
- Each team would use different naming ("RankProducts" vs "ScoreItems"), breaking aggregation

**If we embedded candidates in `steps.candidates` JSONB:**
- A step with 5,000 candidates would create a 5MB row
- PostgreSQL performance degrades on large JSON blobs
- Querying "all rejected candidates across runs" requires full table scans

**If we used separate tables per pipeline:**
- Adding a new pipeline requires schema migration
- No global dashboards ("show failure rate across all pipelines")
- Violates DRY - same query logic reimplemented 100 times

---

## Debugging Walkthrough

### Scenario: Bad Competitor Match

**Problem:** A "laptop stand" product was matched with a "phone case" as its competitor.

**Data:**
- Product ID: `prod_ABC123`
- Selected Competitor: `prod_XYZ789` (Premium Leather Phone Case)

### Debugging Steps

**1. Find the run**
```http
GET /v1/runs?metadata.product_id=prod_ABC123&pipeline_type=CompetitorDiscovery
```

**2. Inspect the steps**
```http
GET /v1/runs/{run_id}
```

Response shows 5 steps:
```json
{
  "id": "run_123",
  "pipeline_type": "CompetitorDiscovery",
  "steps": [
    {"step_name": "GenerateKeywords", "step_type": "LLM", "status": "SUCCESS"},
    {"step_name": "SearchCompetitors", "step_type": "API", "status": "SUCCESS"},
    {"step_name": "FilterCompetitors", "step_type": "FILTER", "status": "SUCCESS"},
    {"step_name": "RankAndSelect", "step_type": "LLM", "status": "SUCCESS"}
  ]
}
```

All steps succeeded, so this is a **logic bug**, not a crash.

**3. Check keyword generation**
```http
GET /v1/steps/{generate_keywords_step_id}
```

```json
{
  "step_name": "GenerateKeywords",
  "output_summary": "Count: 4 keywords",
  "outputs": ["laptop stand", "desk organizer", "monitor riser", "phone case"]
}
```

**🚨 Root cause identified:** The LLM hallucinated "phone case" as a relevant keyword. This is the failure point.

**4. Verify filtering didn't catch it**
```http
GET /v1/steps/{filter_step_id}?include_candidates=true
```

```json
{
  "step_name": "FilterCompetitors",
  "stats": {"input_count": 120, "output_count": 12},
  "candidates": [
    {
      "candidate_id": "prod_XYZ789",
      "attributes": {"title": "Premium Phone Case", "price": 25, "rating": 4.8, "category": "Accessories"},
      "decision": "accepted"
    }
  ]
}
```

**Diagnosis:** The phone case passed filtering because:
- Price ($25) was within range
- Rating (4.8) met threshold
- Category filter was too lenient or missing

**5. Check ranking logic**
```http
GET /v1/steps/{ranking_step_id}
```

```json
{
  "candidates": [
    {
      "candidate_id": "prod_XYZ789",
      "decision": "selected",
      "score": {"relevance": 0.6},
      "reasoning": "High rating and affordable price"
    }
  ]
}
```

**Conclusion:** The ranking LLM selected the phone case based on surface-level similarity (both are "desk accessories").

### Fix Recommendations

1. **Immediate fix:** Add strict category matching in FilterCompetitors
2. **LLM prompt improvement:** Add negative examples to keyword generation ("avoid unrelated product types")
3. **Ranking enhancement:** Add semantic similarity check between product titles

**Without X-Ray, this would have required:**
- Rerunning the pipeline with print statements
- Guessing which step failed
- No visibility into why the phone case was accepted at each stage

---

## Queryability

### Design Goal

A user should be able to ask: **"Show me all runs where filtering eliminated more than 90% of candidates"** across CompetitorDiscovery, ListingOptimization, Categorization, and any future pipeline.

### How We Support This

**1. Standardized `step_type` Taxonomy**

```python
# Developer constraint: Must use standardized enums
with xray_step("FilterByPrice", "FILTER"):  # Not "CUSTOM" or arbitrary names
    ...
```

This enables:
```sql
SELECT * FROM steps
WHERE step_type = 'FILTER'
  AND (stats->>'output_count')::int < (stats->>'input_count')::int * 0.1
```

**2. Mandatory `stats` Schema**

```python
# Developer convention: Always log input/output counts
step.log_stats(input_count=len(candidates), output_count=len(filtered))
```

This powers queries like:
```http
GET /v1/steps?step_type=FILTER&stats.output_count__lt=10&stats.input_count__gt=100
```

**3. Flexible `attributes` via JSONB**

Different domains store different data:
- E-commerce: `{price, rating, category}`
- Content generation: `{word_count, readability_score}`
- Categorization: `{confidence, hierarchy_level}`

PostgreSQL's JSONB operators allow querying without fixed schema:
```sql
SELECT * FROM candidate_decisions
WHERE attributes->>'price' > '100'
  AND decision = 'rejected'
```

### Constraints Imposed on Developers

To enable queryability, developers must:

1. **Use standardized `step_type` values**
   - LLM, FILTER, API, RANKING, TRANSFORM (extensible, but curated list)
   - SDK validates: `xray_step("foo", "INVALID")` → raises warning

2. **Always log `input_count` and `output_count`**
   - SDK auto-captures for list inputs/outputs
   - Decorator handles this automatically for simple cases

3. **Use consistent decision enum**
   - `accepted`, `rejected`, `selected` (not "kept", "discarded", etc.)

4. **Add context to metadata**
   - `metadata={"product_id": "..."}` enables filtering runs by product

### Query Examples

**"Show filtering steps that eliminated >90% of candidates"**
```http
GET /v1/steps?step_type=FILTER&filter_rate__gt=0.9
```

**"Find all LLM failures in the last 24 hours"**
```http
GET /v1/steps?step_type=LLM&status=FAILURE&started_at__gte=2024-01-07T00:00:00Z
```

**"Which products had >5 competitors rejected due to price?"**
```sql
SELECT run_id, COUNT(*) FROM candidate_decisions
WHERE decision = 'rejected'
  AND reasoning LIKE '%price%'
GROUP BY run_id
HAVING COUNT(*) > 5
```

### Variability & Extensibility

X-Ray is designed for **any multi-step decision pipeline**, not just e-commerce:

- **Content moderation:** Steps = DetectToxicity (LLM), FilterByThreshold (FILTER), EscalateToHuman (API)
- **Hiring:** Steps = ResumeScreening (LLM), SkillsMatch (FILTER), RankCandidates (RANKING)
- **Fraud detection:** Steps = ExtractFeatures (TRANSFORM), PredictRisk (LLM), BlockTransaction (FILTER)

The only requirement: Model your process as **candidates flowing through decision steps**.

---

## Performance & Scale

### The Challenge

A step processing 5,000 product candidates would create:
- **Without sampling:** 5,000 database rows, each storing 1-5KB of attributes = 25MB per step
- **At scale:** 100 runs/day × 4 steps/run × 5,000 candidates = 2M rows/day = 50GB/day

This is prohibitively expensive for always-on capture.

### Solution: Three-Tier Capture Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                     Capture Tiers                           │
├─────────────────────────────────────────────────────────────┤
│ Tier 1: Summary (always)                                    │
│   • input_count, output_count, duration                     │
│   • Stored in `steps.stats` (indexed JSONB)                 │
│   • Cost: <1KB per step                                     │
│   • Enables: Cross-pipeline queries, failure detection      │
├─────────────────────────────────────────────────────────────┤
│ Tier 2: Sampled Candidates (developer-controlled)           │
│   • Top 10 rejected (by score), bottom 10 accepted          │
│   • Random 1% sample for large sets                         │
│   • Stored in `candidate_decisions` table                   │
│   • Cost: ~50KB per step (for 20 sampled candidates)        │
│   • Enables: Understanding decision boundaries              │
├─────────────────────────────────────────────────────────────┤
│ Tier 3: Full Capture (explicit opt-in)                      │
│   • ALL candidates with full attributes                     │
│   • Stored in `steps.inputs/outputs` (JSONB)                │
│   • Cost: 5-50MB per step                                   │
│   • Enables: Complete replay, forensic debugging            │
│   • Use case: Debugging specific failing runs               │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

**Automatic (Tier 1 - Summary)**
```python
with xray_step("FilterCompetitors", "FILTER") as step:
    filtered = [c for c in candidates if c.price < 100]
    step.log_stats(input_count=len(candidates), output_count=len(filtered))
    # SDK automatically captures counts, duration, status
```

**Developer-Controlled (Tier 2 - Sampled)**
```python
with xray_step("FilterCompetitors", "FILTER") as step:
    kept, dropped = [], []
    for c in candidates:
        if c.price < 100:
            kept.append(c)
        else:
            dropped.append(c)

    # Sample: top 10 most expensive rejected, top 10 cheapest accepted
    sample_rejected = sorted(dropped, key=lambda c: c.price, reverse=True)[:10]
    sample_accepted = sorted(kept, key=lambda c: c.price)[:10]

    step.log_sampled_candidates(rejected=sample_rejected, accepted=sample_accepted)
```

**Explicit Opt-In (Tier 3 - Full Capture)**
```python
with xray_step("FilterCompetitors", "FILTER", capture_mode="FULL") as step:
    # SDK stores ALL candidates in steps.inputs/outputs
    filtered = filter_logic(candidates)
```

### Trade-offs

| Approach | Storage Cost | Debuggability | Latency Impact |
|----------|--------------|---------------|----------------|
| **Tier 1 only** | 1KB/step | Can identify WHICH step failed | <1ms |
| **Tier 2 (sampled)** | 50KB/step | Can see decision boundaries | 5-10ms |
| **Tier 3 (full)** | 5MB+/step | Complete replay possible | 50-100ms |

### Who Decides?

**The developer controls depth**, not the system.

- **Default:** Tier 1 (summary only) - safe for production, always-on
- **Debugging mode:** Tier 2 (sampled) - enable when investigating issues
- **Post-mortem:** Tier 3 (full) - one-off capture for forensic analysis

### Sampling Strategies (Future Enhancement)

1. **Intelligent sampling:** Capture candidates near decision boundaries (score ≈ threshold)
2. **Adaptive sampling:** Increase capture rate when steps show high variance
3. **Outlier focus:** Always capture top/bottom 1% by score

---

## Developer Experience

### Minimal Instrumentation

**Goal:** Get SOMETHING useful with <5 lines of code.

```python
from sdk import xray_run, xray_step

with xray_run("CompetitorDiscovery"):
    with xray_step("GenerateKeywords"):
        keywords = generate_keywords(product)

    with xray_step("SearchCompetitors"):
        candidates = search_api(keywords)

    with xray_step("FilterCompetitors"):
        filtered = apply_filters(candidates)
```

**What you get:**
- Run/step hierarchy
- Timing for each step
- Success/failure status
- Automatic context propagation

**What you DON'T get:**
- Candidate-level detail
- Rejection reasons
- Input/output counts

**This is ENOUGH to answer:**
- "Which step failed?"
- "Which step took 10 seconds?"
- "How many runs failed today?"

### Full Instrumentation

**Goal:** Capture rich context for deep debugging.

```python
with xray_run("CompetitorDiscovery", metadata={"product_id": product.id}) as run:

    with xray_step("GenerateKeywords", "LLM") as step:
        keywords = llm.generate(product.title)
        step.log_stats(
            input_count=1,
            output_count=len(keywords),
            model="gpt-4",
            tokens=response.usage.total_tokens
        )

    with xray_step("FilterCompetitors", "FILTER") as step:
        kept, dropped = [], []
        for c in candidates:
            if c.price > 100:
                dropped.append({"candidate": c, "reason": f"Price ${c.price} > $100"})
            elif c.rating < 4.0:
                dropped.append({"candidate": c, "reason": f"Rating {c.rating} < 4.0"})
            else:
                kept.append(c)

        step.log_stats(
            input_count=len(candidates),
            output_count=len(kept),
            rejection_rate=len(dropped) / len(candidates)
        )
        step.log_sampled_candidates(
            accepted=kept[:10],
            rejected=[d["candidate"] for d in dropped[:10]]
        )
```

**What you get:**
- Full decision context
- Rejection reasons
- Custom metrics (token usage, model version)
- Sampled candidates

**This is ENOUGH to answer:**
- "Why was candidate X rejected?"
- "What price threshold eliminated most candidates?"
- "Which LLM version performed better?"

### Backend Unavailable

**Scenario:** X-Ray API is down. What happens to your pipeline?

**Answer:** Nothing. It keeps running.

**Implementation:**
```python
# sdk/client.py
class XRayClient:
    def start_run(self, pipeline_type, metadata):
        try:
            resp = requests.post(f"{self.api_url}/runs", json=payload, timeout=2)
            return resp.json()["id"] if resp.status_code == 200 else None
        except Exception as e:
            logger.warning(f"X-Ray API unavailable: {e}")
            return None  # Run continues without X-Ray

    def record_step(self, step_data):
        try:
            requests.post(f"{self.api_url}/steps", json=step_data, timeout=2)
        except Exception:
            pass  # Fire-and-forget
```

**Key design decisions:**

1. **2-second timeout:** If API doesn't respond fast, move on
2. **No exceptions raised:** SDK swallows errors to avoid breaking pipeline
3. **Logging only:** Failed calls log warnings, don't crash
4. **Optional run_id:** Steps gracefully handle `run_id=None`

**Trade-off:** You lose observability, but your business logic is NEVER blocked.

**Future enhancement:** Local buffering + async retry (like Sentry SDK).

---

## Real-World Application

### The System: LLM-Based Content Ranker

**Context:** At a previous company, I worked on a system that ranked user-generated content (articles) for homepage placement. The pipeline had 4 steps:

1. **Extract Features** (API): Fetch article metadata (views, likes, author reputation)
2. **Generate Embeddings** (LLM): Create semantic embeddings for article titles/snippets
3. **Score Candidates** (LLM): GPT-4 scores articles 0-100 for "homepage worthiness"
4. **Apply Business Rules** (Filter): Remove articles <50 score, recent duplicates, banned authors

**The Problem:**

An article titled "How I Built a $1M SaaS in 6 Months" was **not** appearing on the homepage, despite having high engagement.

**Debugging Without X-Ray:**
1. Added print statements to each step → redeployed
2. Ran pipeline manually with that article → saw it got score 78 (should pass)
3. Realized business rules filter was dropping it
4. Added more print statements → redeployed again
5. Discovered it was flagged as "duplicate" due to title similarity to a post from 2 weeks ago
6. **Time spent:** 3 hours, 2 deployments, frustrated engineer

**Debugging With X-Ray:**
1. Query: `GET /runs?metadata.article_id=abc123`
2. View steps → all SUCCESS
3. Check "Apply Business Rules" step candidates:
   ```json
   {
     "candidate_id": "abc123",
     "decision": "rejected",
     "reasoning": "Duplicate title similarity 92% with article def456"
   }
   ```
4. **Time spent:** 2 minutes, 0 deployments, happy engineer

**How I'd Retrofit X-Ray:**

```python
# Before
def rank_articles(articles):
    features = fetch_features(articles)
    embeddings = generate_embeddings(articles)
    scores = score_with_llm(embeddings)
    final = apply_business_rules(scores)
    return final

# After (5 minutes of work)
def rank_articles(articles):
    with xray_run("ContentRanking", metadata={"request_id": request.id}):

        with xray_step("ExtractFeatures", "API") as step:
            features = fetch_features(articles)
            step.log_stats(input_count=len(articles), api_latency=features.latency)

        with xray_step("GenerateEmbeddings", "LLM") as step:
            embeddings = generate_embeddings(articles)
            step.log_stats(model="text-embedding-ada-002", tokens=embeddings.usage)

        with xray_step("ScoreCandidates", "LLM") as step:
            scores = score_with_llm(embeddings)
            step.log_sampled_candidates(
                accepted=[s for s in scores if s.score >= 50],
                rejected=[s for s in scores if s.score < 50]
            )

        with xray_step("ApplyBusinessRules", "FILTER") as step:
            final = apply_business_rules(scores)
            # Log rejection reasons
            for article in scores:
                if article not in final:
                    step.log_sampled_candidates(
                        rejected=[{"id": article.id, "reason": article.rejection_reason}]
                    )
            step.log_stats(input_count=len(scores), output_count=len(final))

        return final
```

**ROI:** 5 minutes of instrumentation → 3 hours saved per debugging session × 10 sessions/month = 30 hours/month saved.

---

## API Specification

### Base URL
```
http://localhost:8000/v1
```

### Endpoints

#### 1. Create Run
```http
POST /v1/runs
Content-Type: application/json

{
  "pipeline_type": "CompetitorDiscovery",
  "metadata": {
    "product_id": "prod_ABC123",
    "user_id": "user_456"
  },
  "repository": "github.com/company/pipelines",
  "version": "a3f8c2d"
}
```

**Response:**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "pipeline_type": "CompetitorDiscovery",
  "started_at": "2024-01-08T12:00:00Z",
  "status": "RUNNING",
  "metadata": {"product_id": "prod_ABC123", "user_id": "user_456"},
  "repository": "github.com/company/pipelines",
  "version": "a3f8c2d"
}
```

#### 2. Record Step
```http
POST /v1/steps
Content-Type: application/json

{
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "step_name": "FilterCompetitors",
  "step_type": "FILTER",
  "status": "SUCCESS",
  "started_at": "2024-01-08T12:00:01Z",
  "ended_at": "2024-01-08T12:00:02Z",
  "input_summary": "Count: 120 candidates",
  "output_summary": "Count: 12 candidates (90% filtered)",
  "stats": {
    "input_count": 120,
    "output_count": 12,
    "filter_rate": 0.9
  },
  "candidates": [
    {
      "candidate_id": "prod_XYZ789",
      "attributes": {"title": "Premium Phone Case", "price": 150, "rating": 4.5},
      "decision": "rejected",
      "reasoning": "Price $150 exceeds threshold $100"
    }
  ]
}
```

**Response:**
```json
{
  "id": "b2c3d479-58cc-4372-a567-f47ac10b",
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "step_name": "FilterCompetitors",
  "step_type": "FILTER",
  "status": "SUCCESS",
  "started_at": "2024-01-08T12:00:01Z",
  "ended_at": "2024-01-08T12:00:02Z",
  "input_summary": "Count: 120 candidates",
  "output_summary": "Count: 12 candidates (90% filtered)",
  "stats": {"input_count": 120, "output_count": 12, "filter_rate": 0.9}
}
```

#### 3. Query Runs
```http
GET /v1/runs?pipeline_type=CompetitorDiscovery&status=FAILURE&limit=10
```

**Response:**
```json
[
  {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "pipeline_type": "CompetitorDiscovery",
    "started_at": "2024-01-08T12:00:00Z",
    "status": "FAILURE",
    "metadata": {"product_id": "prod_ABC123"},
    "steps": [
      {
        "id": "b2c3d479-58cc-4372-a567-f47ac10b",
        "step_name": "GenerateKeywords",
        "step_type": "LLM",
        "status": "FAILURE",
        "meta": {"error": "API timeout"}
      }
    ]
  }
]
```

#### 4. Get Run Details
```http
GET /v1/runs/{run_id}
```

**Response:** Same as Query Runs, but single object with all nested steps.

#### 5. Query Steps (Cross-Pipeline)
```http
GET /v1/steps?step_type=FILTER&stats.filter_rate__gt=0.9&started_at__gte=2024-01-08T00:00:00Z
```

**Response:**
```json
[
  {
    "id": "b2c3d479-58cc-4372-a567-f47ac10b",
    "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "step_name": "FilterCompetitors",
    "step_type": "FILTER",
    "stats": {"input_count": 120, "output_count": 12, "filter_rate": 0.9},
    "started_at": "2024-01-08T12:00:01Z"
  }
]
```

### Query Parameters

| Parameter | Type | Example | Description |
|-----------|------|---------|-------------|
| `pipeline_type` | string | `CompetitorDiscovery` | Filter by pipeline |
| `status` | enum | `SUCCESS`, `FAILURE` | Filter by status |
| `step_type` | enum | `LLM`, `FILTER`, `API`, `RANKING` | Filter by step type |
| `metadata.{key}` | any | `metadata.product_id=prod_123` | Filter by metadata fields |
| `stats.{key}__gt` | number | `stats.filter_rate__gt=0.9` | Filter by stats (greater than) |
| `stats.{key}__lt` | number | `stats.input_count__lt=10` | Filter by stats (less than) |
| `started_at__gte` | ISO8601 | `2024-01-08T00:00:00Z` | Filter by start time (>=) |
| `limit` | int | `100` | Max results (default: 100) |
| `skip` | int | `50` | Pagination offset |

---

## What's Next

### Production-Ready Enhancements

1. **Adaptive Sampling**
   - Auto-increase capture rate when steps show high variance
   - Focus on decision boundaries (candidates with score ≈ threshold)
   - ML-based outlier detection: "This candidate is unusual, capture it"

2. **Schema Validation**
   - SDK validates `step_type` against whitelist
   - API enforces `stats.input_count` presence for FILTER steps
   - Custom validation rules per pipeline_type

3. **Async SDK with Local Buffering**
   - Buffer traces locally if API is unreachable
   - Retry with exponential backoff
   - Circuit breaker pattern (stop trying if API is dead for 5 minutes)

4. **Time-Travel Comparisons**
   - "Show me Run A vs Run B side-by-side"
   - Diff view: "Why did Run A select Candidate X but Run B selected Candidate Y?"
   - Regression detection: "This week's runs are 20% slower in step 3"

5. **Query API Enhancements**
   - GraphQL endpoint for complex nested queries
   - Aggregations: "Average filter rate by pipeline_type"
   - Export to CSV/Parquet for analytics

6. **Automated Failure Pattern Detection**
   - "80% of LLM step failures are due to timeout" → alert
   - "Price filter eliminates 95% of candidates" → flag for review
   - Anomaly detection: "Step 3 took 10x longer than usual"

7. **Cost-Aware Capture**
   - Estimate storage cost per run: "This run will cost $0.05 to fully capture"
   - Budget limits: "Stop capturing candidates after 1GB this month"
   - Archival policy: "Delete candidate_decisions older than 90 days"

8. **Multi-Tenancy**
   - Separate workspaces per team
   - API keys with scoped permissions
   - Data isolation (team A can't see team B's runs)

### Integrations

- **Slack/PagerDuty:** Alert when failure rate spikes
- **DataDog/Grafana:** Export metrics (step duration, failure rate)
- **Jupyter:** Python client for ad-hoc analysis
- **CI/CD:** Block deploys if test pipelines show regressions

---

## Conclusion

X-Ray is designed to answer the question **"Why did my pipeline make this decision?"** in production environments where:
- Decisions are non-deterministic (LLMs, ranking algorithms)
- Pipelines have multiple steps (not single-function calls)
- Debugging requires understanding flow, not just timing
- Storage cost must be balanced with debuggability

The core insight: **Every decision system can be modeled as candidates flowing through steps**. By enforcing this abstraction and a minimal set of conventions (`step_type`, `stats`, `decision` enum), we enable cross-pipeline queries while preserving flexibility for domain-specific attributes.
