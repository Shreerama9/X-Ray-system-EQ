from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from . import schemas, models, database
import uuid

router = APIRouter()

@router.post("/runs", response_model=schemas.Run)
def create_run(run: schemas.RunCreate, db: Session = Depends(database.get_db)):
    db_run = models.Run(**run.dict())
    # Ensure ID is generated if not provided (though model default handles it, explicit is safe)
    if not db_run.id:
        db_run.id = str(uuid.uuid4())
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run

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
def get_runs(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    runs = db.query(models.Run).offset(skip).limit(limit).all()
    return runs

@router.get("/runs/{run_id}", response_model=schemas.Run)
def get_run(run_id: str, db: Session = Depends(database.get_db)):
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
