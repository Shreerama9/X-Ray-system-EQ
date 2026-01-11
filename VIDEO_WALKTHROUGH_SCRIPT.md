# Video Walkthrough Script & Talking Points
**Hard Limit: 10 minutes** | Face on camera required

---

## 🎬 Setup Before Recording

**Technical:**
- [ ] Close unnecessary tabs/apps
- [ ] Turn off notifications (Slack, email, etc.)
- [ ] Test audio (use headphones/mic if needed)
- [ ] Test screen sharing (record 30 sec test)
- [ ] Have terminal ready with project directory open
- [ ] Set up split screen: Code on left, terminal on right
- [ ] Start timer visible on screen (or have phone timer)

**Environment:**
- [ ] API server **NOT** running yet (will start during demo)
- [ ] Fresh database: `rm xray.db 2>/dev/null`
- [ ] Virtual environment activated
- [ ] All example files ready to run

---

## 📝 Script Outline (10 minutes)

### Section 1: Introduction (1 min) [0:00-1:00]

**On Camera (30 sec):**
> "Hi! I'm Shreerama Shiva Sai Bharadwaja. I'm excited to show you X-Ray, a decision forensics system for debugging non-deterministic pipelines.
>
> Traditional tracing tells you *what* functions were called. X-Ray tells you *why* your pipeline made a specific decision.
>
> In the next 10 minutes, I'll walk you through the architecture, show you a live demo debugging a bad match, and share what I learned building this."

**Screen Share - Show Project Structure (30 sec):**
```
xray-sdk/
├── sdk/           ← Context managers, fire-and-forget client
├── api/           ← FastAPI service with 3-tier data model
├── examples/      ← 4 scenarios including bad match demo
├── tests/         ← Unit + integration tests
└── ARCHITECTURE.md ← Comprehensive design doc
```

> "Let's dive into the architecture."

---

### Section 2: Architecture Deep Dive (4 min) [1:00-5:00]

#### 2.1 The Problem (30 sec)
> "Imagine a competitor discovery pipeline for Amazon's 4 billion products. It has 4 steps:
> 1. Generate keywords with an LLM
> 2. Search for products
> 3. Filter by price, rating, category
> 4. Rank with another LLM
>
> When it selects a **phone case** as a competitor for a **laptop stand**, which step failed?"

#### 2.2 Data Model (1.5 min) [1:30-3:00]

**Show ARCHITECTURE.md diagram:**
```
Run (pipeline execution)
  ├── Step (decision point)
      ├── CandidateDecision (what was accepted/rejected and why)
```

> "Three-tier hierarchy mirrors how we debug:
> - 'Which run failed?' → Run
> - 'Which step failed?' → Step
> - 'Which candidate was wrong?' → CandidateDecision
>
> **Key design decision:** Separate CandidateDecision table.
>
> **Alternative:** Could embed all candidates in steps.candidates JSONB.
> **Problem:** A step with 5,000 candidates → 5MB row → PostgreSQL chokes.
>
> **Trade-off:** Separate table costs a join, but scales to millions of candidates."

**Show models.py quickly:**
> "Run tracks pipeline_type, metadata for filtering.
> Step has step_type taxonomy—LLM, FILTER, API, RANKING.
> CandidateDecision has attributes (JSONB for flexibility), decision enum, score, and reasoning."

#### 2.3 Queryability (1 min) [3:00-4:00]

> "Cross-pipeline queries: 'Show all FILTER steps that eliminated >90% of candidates.'
>
> **How?** Standardized step_type taxonomy enforced by SDK.
>
> **Developer constraint:** Must use LLM, FILTER, API, RANKING—not arbitrary names.
>
> **Why?** Without this, every team uses different names. Can't query across pipelines.
>
> **Trade-off:** Less flexibility, more queryability. Worth it for global dashboards."

**Show API route quickly:**
```python
GET /v1/steps?step_type=FILTER&stats.filter_rate__gt=0.9
```

#### 2.4 Fire-and-Forget (1 min) [4:00-5:00]

**Show client.py:**
> "SDK never blocks the main pipeline.
> - 2-second timeout on API calls
> - Exceptions swallowed, logged as warnings
> - Returns None if API is down
>
> **Why?** Business logic > observability. Pipeline continues even if X-Ray is dead.
>
> **Trade-off:** You lose visibility, but never lose money."

---

### Section 3: Live Demo (3 min) [5:00-8:00]

#### 3.1 Start the API (15 sec)

**Terminal 1:**
```bash
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

> "API starting... and we're live at localhost:8000."

#### 3.2 Run Bad Match Scenario (45 sec)

**Terminal 2:**
```bash
PYTHONPATH=. python3 examples/scenario_bad_match_demo.py
```

**While running, narrate:**
> "This simulates the bad match scenario:
> - Step 1: LLM generates keywords → **notice it hallucinates 'phone case'**
> - Step 2: Search returns products including the phone case
> - Step 3: Filter is too lenient → **phone case passes** (good price & rating)
> - Step 4: Ranking LLM selects phone case as best match
>
> And there it is—**BAD MATCH DETECTED**. Phone case matched with laptop stand."

#### 3.3 Debug with X-Ray (2 min) [6:30-8:00]

**Terminal 3 - Query the run:**
```bash
curl -s 'http://localhost:8000/v1/runs?pipeline_type=CompetitorDiscovery' | python3 -m json.tool | less
```

> "Let's debug. Query runs for CompetitorDiscovery..."

**Show JSON output, scroll to interesting parts:**
```json
{
  "id": "run_abc123",
  "pipeline_type": "CompetitorDiscovery",
  "metadata": {"product_id": "prod_ABC123", "scenario": "bad_match_demo"},
  "steps": [...]
}
```

> "Here's our run. Let me expand the steps..."

**Expand GenerateKeywords step:**
```json
{
  "step_name": "GenerateKeywords",
  "step_type": "LLM",
  "stats": {"output_count": 4},
  "output_summary": "Count: 4 keywords"
}
```

> "Step 1: GenerateKeywords. Output count is 4. One of those is 'phone case'—the hallucination."

**Expand FilterCompetitors step:**
```json
{
  "step_name": "FilterCompetitors",
  "step_type": "FILTER",
  "stats": {"input_count": 4, "output_count": 4, "filter_rate": 0.0}
}
```

> "Step 3: FilterCompetitors. Filter rate is 0—nothing was filtered!
> Why? We only checked price and rating, not category.
> **Fix:** Add category matching."

**Query candidates (if time allows):**
```bash
curl -s 'http://localhost:8000/v1/runs/[run_id]' | python3 -m json.tool | grep -A 5 "reasoning"
```

> "We can see rejection reasoning: 'Price exceeds threshold', 'Rating too low'.
> But phone case? No reasoning because it was accepted."

**Summarize:**
> "In 60 seconds, we found the root cause:
> 1. LLM hallucinated keyword
> 2. Filter had no category check
> 3. Ranking picked based on surface similarity
>
> Without X-Ray, this would've taken hours of print statements and rerunning."

---

### Section 4: Reflection (1.5 min) [8:00-9:30]

**Back to camera:**

> "One moment I got stuck: metadata field mapping.
>
> **Problem:** Pydantic schema used 'metadata', but SQLAlchemy model used 'meta' (reserved word in Python).
>
> **Symptom:** API returned empty metadata. No errors—just missing data.
>
> **Debug process:**
> 1. Checked API response—metadata: null
> 2. Checked database—meta column had data
> 3. Realized Pydantic wasn't mapping correctly
>
> **Solution:** Explicit mapping in routes.py:
> ```python
> run_data['meta'] = run_data.pop('metadata')
> return schemas.Run(..., metadata=db_run.meta)
> ```
>
> **Lesson:** Don't rely on ORM magic for field name aliasing. Be explicit."

**Trade-offs reflection (30 sec):**
> "Biggest trade-off: **storage vs debuggability**.
>
> Full capture of 5,000 candidates = 25MB per step.
>
> **Solution:** 3-tier capture strategy:
> - Tier 1: Summary stats (always) → 1KB
> - Tier 2: Sampled candidates (developer-controlled) → 50KB
> - Tier 3: Full capture (explicit opt-in) → 5MB+
>
> **Who decides?** The developer. System provides tools, not rules."

---

### Section 5: AI Assistance (30 sec) [9:30-10:00]

**On camera:**

> "Did I use AI? Yes—Claude helped with:
> - FastAPI boilerplate (routes, schemas)
> - Test structure and fixtures
> - Documentation formatting
>
> But every design decision came from me:
> - Why 3-tier hierarchy vs flat events
> - Why separate CandidateDecision table
> - Why step_type taxonomy
> - The 3-tier capture strategy
>
> AI sped up execution, not thinking."

**Closing (10 sec):**
> "Thanks for watching! I'm excited to discuss this further. The repo link and architecture doc have all the details."

**[END AT 10:00]**

---

## 🎯 Key Points to Hit

**Architecture:**
- ✅ 3-tier data model (Run → Step → Candidate)
- ✅ Why not flat? Why not embedded?
- ✅ step_type taxonomy for cross-pipeline queries
- ✅ Fire-and-forget client (2s timeout)
- ✅ 3-tier capture strategy (trade-off)

**Demo:**
- ✅ Show bad match happening
- ✅ Use X-Ray to find root cause
- ✅ Point out specific data (keywords, filter stats, reasoning)
- ✅ Under 3 minutes for demo

**Reflection:**
- ✅ Specific stuck moment (metadata mapping)
- ✅ How you debugged it
- ✅ Key trade-off explained

**Communication:**
- ✅ Clear, concise language
- ✅ Avoid jargon unless explaining it
- ✅ Show, don't just tell

---

## ⚠️ Common Pitfalls to Avoid

1. **Going over time** → Practice! Cut content if needed
2. **Too much code reading** → Show architecture, not implementation
3. **Generic explanations** → Be specific ("5,000 candidates", "25MB", "2s timeout")
4. **No reasoning** → Always explain *why*, not just *what*
5. **Forgetting face cam** → Stay on camera throughout
6. **No demo** → Must show it working, not just talk about it

---

## 📊 Time Checkpoints

| Timestamp | Section | Check |
|-----------|---------|-------|
| 1:00 | End Intro | "Now let's look at architecture" |
| 3:00 | Mid Architecture | Showing data model trade-offs |
| 5:00 | Start Demo | API server starting |
| 8:00 | Start Reflection | Back to camera |
| 9:30 | AI Section | Final 30 seconds |
| 10:00 | END | Stop recording |

**If running long:** Cut Section 4 reflection short. Demo is most important.

---

## 🎥 Recording Checklist

**Before recording:**
- [ ] Fresh database
- [ ] API not running
- [ ] Terminal ready
- [ ] Face visible
- [ ] Timer set

**During recording:**
- [ ] Narrate what you're doing
- [ ] Pause briefly between sections
- [ ] Check time at checkpoints
- [ ] Speak clearly and enthusiastically

**After recording:**
- [ ] Watch full video
- [ ] Check audio quality
- [ ] Verify under 10 minutes
- [ ] Ensure link is shareable

---

## 💡 Tips for Success

1. **Practice once** → Find your rough edges
2. **Script key phrases** → But don't read verbatim
3. **Zoom in** → Make code readable
4. **Slow down** → Excited talking = fast talking
5. **Smile** → Show you enjoyed building this!

Good luck! 🚀
