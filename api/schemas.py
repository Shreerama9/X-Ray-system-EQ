import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Candidate abstraction is usually part of metadata or inputs/outputs, 
# but could be explicit if we want strict validation.
# For now, we follow the "jsonb" approach but encourage keys.

class CandidateCreate(BaseModel):
    candidate_id: str
    attributes: Optional[Dict[str, Any]] = None
    decision: str
    score: Optional[Any] = None
    reasoning: Optional[str] = None

class StepBase(BaseModel):
    step_name: str
    step_type: str  # "LLM", "FILTER", "API", "RANKING"
    
    # New Architecture Fields
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None # input_count, output_count
    
    # Flexible JSON blobs (keeping these for detailed candidates)
    inputs: Optional[Any] = None
    outputs: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None
    
    status: str = "SUCCESS"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None

    class Config:
        populate_by_name = True

class StepCreate(StepBase):
    run_id: uuid.UUID
    candidates: List[CandidateCreate] = [] # Optional list of candidates to create with step

class Step(StepBase):
    id: uuid.UUID
    run_id: uuid.UUID

    class Config:
        from_attributes = True
        populate_by_name = True

class RunBase(BaseModel):
    pipeline_type: str
    metadata: Optional[Dict[str, Any]] = None
    repository: Optional[str] = None
    version: Optional[str] = None

    class Config:
        populate_by_name = True

class RunCreate(RunBase):
    pass

class Run(RunBase):
    id: uuid.UUID
    started_at: datetime
    status: str = "RUNNING"
    steps: List[Step] = []

    class Config:
        from_attributes = True
