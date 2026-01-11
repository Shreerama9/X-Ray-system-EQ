import functools
import contextvars
from datetime import datetime
from typing import Optional, Any, Dict, List
from .client import client
import traceback

_current_run_id = contextvars.ContextVar("current_run_id", default=None)
# Track current step context to allow adding candidates inside the step
_current_step_context = contextvars.ContextVar("current_step_context", default=None)

def serialize(obj):
    """Recursively ensure object is JSON serializable."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {str(k): serialize(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    try:
        if hasattr(obj, "__dict__"):
            return {str(k): serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        return str(obj)
    except Exception:
        return str(obj)

class XRayRunContext:
    def __init__(self, pipeline_type: str, metadata: Dict[str, Any] = None, repository: str = None, version: str = None):
        self.pipeline_type = pipeline_type
        self.metadata = metadata
        self.repository = repository
        self.version = version
        self.run_id = None
        self.token = None

    def __enter__(self):
        self.run_id = client.start_run(self.pipeline_type, self.metadata, self.repository, self.version)
        if self.run_id:
            self.token = _current_run_id.set(self.run_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            _current_run_id.reset(self.token)

class XRayStepContext:
    def __init__(self, name: str, step_type: str = "GENERIC"):
        self.name = name
        self.step_type = step_type
        self.stats = {}
        self.candidates = []
        self.token = None
        self.start_time = None
        
    def __enter__(self):
        self.start_time = datetime.utcnow()
        self.token = _current_step_context.set(self)
        return self

    def log_stats(self, **kwargs):
        """Log statistics for the step (e.g. input_count, output_count)."""
        self.stats.update(kwargs)

    def log_sampled_candidates(self, rejected: List[Any] = None, accepted: List[Any] = None, selected: List[Any] = None):
        """
        Log sampled candidates with decisions.

        Candidates can be:
        - Simple dicts with {id, attributes, optional: score, reasoning}
        - Objects with those attributes
        - Tuples of (candidate, reasoning) or (candidate, score, reasoning)
        """
        rejected = rejected or []
        accepted = accepted or []
        selected = selected or []

        def _process(objs, decision):
            for item in objs:
                # Support tuple format: (candidate, reasoning) or (candidate, score, reasoning)
                candidate = item
                reasoning = None
                score = None

                if isinstance(item, tuple):
                    if len(item) == 2:
                        candidate, reasoning = item
                    elif len(item) == 3:
                        candidate, score, reasoning = item

                # Extract ID and attributes
                candidate_id = "unknown"
                attributes = {}

                if isinstance(candidate, dict):
                    candidate_id = candidate.get("id", "unknown")
                    attributes = {k: v for k, v in candidate.items() if k not in ["reasoning", "score"]}
                    # Allow reasoning/score in dict if not provided separately
                    if reasoning is None:
                        reasoning = candidate.get("reasoning")
                    if score is None:
                        score = candidate.get("score")
                else:
                    candidate_id = getattr(candidate, "id", "unknown")
                    attributes = serialize(candidate)
                    if reasoning is None:
                        reasoning = getattr(candidate, "reasoning", None)
                    if score is None:
                        score = getattr(candidate, "score", None)

                self.candidates.append({
                    "candidate_id": str(candidate_id),
                    "attributes": serialize(attributes),
                    "decision": decision,
                    "score": serialize(score) if score is not None else None,
                    "reasoning": str(reasoning) if reasoning is not None else None
                })

        _process(rejected, "rejected")
        _process(accepted, "accepted")
        _process(selected, "selected")
    
    # helper for backward compatibility with my previous implementation
    def add_candidates(self, candidates: List[Any], processed: bool = False):
        if processed:
             self.log_sampled_candidates(accepted=candidates)
        else:
             # Just input logging, maybe not a decision yet? 
             # The Authoritative plan implies logging decisions.
             pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        run_id = _current_run_id.get()
        if not run_id:
            return

        end_time = datetime.utcnow()
        status = "FAILURE" if exc_type else "SUCCESS"
        
        meta = {}
        if exc_type:
            meta["error"] = str(exc_val)
        
        step_data = {
            "run_id": run_id,
            "step_name": self.name,
            "step_type": self.step_type,
            "status": status,
            "started_at": self.start_time.isoformat(),
            "ended_at": end_time.isoformat(),
            "stats": self.stats,
            "meta": meta,
            "candidates": self.candidates, # Now a list of candidate dicts
            "input_summary": f"Count: {self.stats.get('input_count', 'N/A')}",
            "output_summary": f"Count: {self.stats.get('output_count', 'N/A')}"
        }
        client.record_step(step_data)
        
        if self.token:
            _current_step_context.reset(self.token)

# Aliases matching User Architecture
xray_run = XRayRunContext
xray_step = XRayStepContext

# Decorator - kept simple
def step(name: str, step_type: str = "GENERIC"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with xray_step(name, step_type) as ctx:
                if args and isinstance(args[0], list):
                    ctx.log_stats(input_count=len(args[0]))
                
                try:
                    result = func(*args, **kwargs)
                    if isinstance(result, list):
                        ctx.log_stats(output_count=len(result))
                    return result
                except Exception:
                    raise
        return wrapper
    return decorator
