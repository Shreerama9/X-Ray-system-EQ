from fastapi import FastAPI
from . import models, database, routes

# Create tables on startup
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="X-Ray API", description="Debugging for non-deterministic pipelines")

app.include_router(routes.router, prefix="/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
