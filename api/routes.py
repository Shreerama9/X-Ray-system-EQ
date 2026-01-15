from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from . import schemas, models, database
import uuid

router = APIRouter()

@router.post("/runs", response_model=schemas.Run)
def create_run(run: schemas.RunCreate, db: Session = Depends(database.get_db)):
    # Map metadata -> meta for DB
    run_data = run.dict()
    if "metadata" in run_data:
        run_data["meta"] = run_data.pop("metadata")

    db_run = models.Run(**run_data)
    if not db_run.id:
        db_run.id = str(uuid.uuid4())
    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    # Map back meta -> metadata for response
    return schemas.Run(
        id=db_run.id,
        pipeline_type=db_run.pipeline_type,
        started_at=db_run.started_at,
        status=db_run.status,
        repository=db_run.repository,
        version=db_run.version,
        metadata=db_run.meta,
        steps=[schemas.Step.from_orm(s) for s in db_run.steps]
    )

@router.post("/steps", response_model=schemas.Step)
def create_step(step: schemas.StepCreate, db: Session = Depends(database.get_db)):
    step_data = step.dict(exclude={"run_id", "candidates"})
    db_step = models.Step(**step_data)
    db_step.run_id = str(step.run_id)
    
    db.add(db_step)
    db.commit() # Commit step first to get ID
    
    if step.candidates:
        decisions = []
        for c in step.candidates:
            cd = models.CandidateDecision(**c.dict())
            cd.step_id = db_step.id
            decisions.append(cd)
        db.add_all(decisions)
        db.commit()

    db.refresh(db_step)
    return db_step

@router.get("/runs", response_model=List[schemas.Run])
def get_runs(
    skip: int = 0,
    limit: int = 100,
    pipeline_type: str = None,
    status: str = None,
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Run)

    if pipeline_type:
        query = query.filter(models.Run.pipeline_type == pipeline_type)
    if status:
        query = query.filter(models.Run.status == status)

    runs = query.offset(skip).limit(limit).all()

    # Map meta -> metadata for response
    return [
        schemas.Run(
            id=run.id,
            pipeline_type=run.pipeline_type,
            started_at=run.started_at,
            status=run.status,
            repository=run.repository,
            version=run.version,
            metadata=run.meta,
            steps=[schemas.Step.from_orm(s) for s in run.steps]
        )
        for run in runs
    ]

@router.get("/runs/{run_id}", response_model=schemas.Run)
def get_run(run_id: str, db: Session = Depends(database.get_db)):
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Map meta -> metadata for response
    return schemas.Run(
        id=run.id,
        pipeline_type=run.pipeline_type,
        started_at=run.started_at,
        status=run.status,
        repository=run.repository,
        version=run.version,
        metadata=run.meta,
        steps=[schemas.Step.from_orm(s) for s in run.steps]
    )

@router.get("/steps", response_model=List[schemas.Step])
def query_steps(
    skip: int = 0,
    limit: int = 100,
    step_type: str = None,
    status: str = None,
    run_id: str = None,
    db: Session = Depends(database.get_db)
):
    """
    Cross-pipeline step querying.
    Supports filtering by step_type, status, run_id.

    Examples:
    - /steps?step_type=FILTER
    - /steps?step_type=LLM&status=FAILURE
    - /steps?run_id=abc123
    """
    query = db.query(models.Step)

    if step_type:
        query = query.filter(models.Step.step_type == step_type)
    if status:
        query = query.filter(models.Step.status == status)
    if run_id:
        query = query.filter(models.Step.run_id == run_id)

    steps = query.offset(skip).limit(limit).all()
    return steps

@router.get("/candidates", response_model=List[schemas.Candidate])
def query_candidates(
    skip: int = 0,
    limit: int = 100,
    decision: str = None,
    step_id: str = None,
    db: Session = Depends(database.get_db)
):
    """
    Query candidate decisions across all steps.
    Supports filtering by decision type and step_id.

    Examples:
    - /candidates?decision=selected
    - /candidates?decision=rejected&limit=50
    - /candidates?step_id=abc123
    """
    query = db.query(models.CandidateDecision)

    if decision:
        query = query.filter(models.CandidateDecision.decision == decision)
    if step_id:
        query = query.filter(models.CandidateDecision.step_id == step_id)

    candidates = query.offset(skip).limit(limit).all()
    return candidates

@router.get("/stats")
def get_stats(db: Session = Depends(database.get_db)):
    """
    Get database statistics for the dashboard.
    Returns counts of runs, steps, and candidates.
    """
    total_runs = db.query(models.Run).count()
    successful_runs = db.query(models.Run).filter(models.Run.status == "SUCCESS").count()
    failed_runs = db.query(models.Run).filter(models.Run.status == "FAILURE").count()

    total_steps = db.query(models.Step).count()
    successful_steps = db.query(models.Step).filter(models.Step.status == "SUCCESS").count()
    failed_steps = db.query(models.Step).filter(models.Step.status == "FAILURE").count()

    total_candidates = db.query(models.CandidateDecision).count()
    selected_candidates = db.query(models.CandidateDecision).filter(models.CandidateDecision.decision == "selected").count()
    accepted_candidates = db.query(models.CandidateDecision).filter(models.CandidateDecision.decision == "accepted").count()
    rejected_candidates = db.query(models.CandidateDecision).filter(models.CandidateDecision.decision == "rejected").count()

    pipeline_types = db.query(models.Run.pipeline_type).distinct().count()
    step_types = db.query(models.Step.step_type).distinct().all()

    return {
        "runs": {
            "total": total_runs,
            "successful": successful_runs,
            "failed": failed_runs
        },
        "steps": {
            "total": total_steps,
            "successful": successful_steps,
            "failed": failed_steps
        },
        "candidates": {
            "total": total_candidates,
            "selected": selected_candidates,
            "accepted": accepted_candidates,
            "rejected": rejected_candidates
        },
        "pipeline_types": pipeline_types,
        "step_types": [s[0] for s in step_types]
    }
