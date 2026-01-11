from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from .database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    # Mapping pipeline_name to pipeline_type column for compatibility or just rename
    pipeline_type = Column(String, index=True) # Underlying DB col
    
    started_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="RUNNING")
    
    repository = Column(String, nullable=True)
    version = Column(String, nullable=True)
    
    # "metadata" in User Arch. We named it "meta" in DB to avoid SQLAlchemy conflict.
    meta = Column(JSON, nullable=True)

    steps = relationship("Step", back_populates="run", cascade="all, delete-orphan")

class Step(Base):
    __tablename__ = "steps"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("runs.id"))
    
    step_name = Column(String, index=True) # step_name
    step_type = Column(String)
    status = Column(String, default="SUCCESS")
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # New Fields
    input_summary = Column(String, nullable=True)
    output_summary = Column(String, nullable=True)
    stats = Column(JSON, nullable=True)
    
    inputs = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    run = relationship("Run", back_populates="steps")
    candidates = relationship("CandidateDecision", back_populates="step", cascade="all, delete-orphan")

class CandidateDecision(Base):
    __tablename__ = "candidate_decisions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    step_id = Column(String, ForeignKey("steps.id"))
    candidate_id = Column(String)
    
    attributes = Column(JSON, nullable=True) # The flexible content
    decision = Column(String) # accepted | rejected | selected
    score = Column(JSON, nullable=True) # single score or map of scores
    reasoning = Column(String, nullable=True)
    
    step = relationship("Step", back_populates="candidates")
