from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import models, database, routes

# Create tables on startup
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="X-Ray API", description="Debugging for non-deterministic pipelines")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
