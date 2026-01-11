import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from api.database import Base, get_db
from api import models


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    return TestClient(app)


class TestRunEndpoints:
    def test_create_run(self, client):
        response = client.post(
            "/v1/runs",
            json={
                "pipeline_type": "CompetitorDiscovery",
                "metadata": {"product_id": "prod_123"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_type"] == "CompetitorDiscovery"
        assert data["status"] == "RUNNING"
        assert "id" in data

    def test_get_runs(self, client):
        # Create a run first
        client.post(
            "/v1/runs", json={"pipeline_type": "TestPipeline", "metadata": {}}
        )

        response = client.get("/v1/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_get_runs_with_filters(self, client):
        # Create runs with different types
        client.post(
            "/v1/runs", json={"pipeline_type": "PipelineA", "metadata": {}}
        )
        client.post(
            "/v1/runs", json={"pipeline_type": "PipelineB", "metadata": {}}
        )

        response = client.get("/v1/runs?pipeline_type=PipelineA")
        assert response.status_code == 200
        data = response.json()
        assert all(run["pipeline_type"] == "PipelineA" for run in data)

    def test_get_run_by_id(self, client):
        # Create a run
        create_response = client.post(
            "/v1/runs", json={"pipeline_type": "TestPipeline", "metadata": {}}
        )
        run_id = create_response.json()["id"]

        # Get by ID
        response = client.get(f"/v1/runs/{run_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == run_id

    def test_get_nonexistent_run(self, client):
        response = client.get("/v1/runs/nonexistent-id")
        assert response.status_code == 404


class TestStepEndpoints:
    def test_create_step(self, client):
        # Create a run first
        run_response = client.post(
            "/v1/runs", json={"pipeline_type": "TestPipeline", "metadata": {}}
        )
        run_id = run_response.json()["id"]

        # Create a step
        response = client.post(
            "/v1/steps",
            json={
                "run_id": run_id,
                "step_name": "TestStep",
                "step_type": "LLM",
                "status": "SUCCESS",
                "started_at": "2024-01-08T12:00:00Z",
                "ended_at": "2024-01-08T12:00:01Z",
                "stats": {"input_count": 10, "output_count": 5},
                "candidates": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["step_name"] == "TestStep"
        assert data["step_type"] == "LLM"
        assert data["run_id"] == run_id

    def test_create_step_with_candidates(self, client):
        # Create a run
        run_response = client.post(
            "/v1/runs", json={"pipeline_type": "TestPipeline", "metadata": {}}
        )
        run_id = run_response.json()["id"]

        # Create step with candidates
        response = client.post(
            "/v1/steps",
            json={
                "run_id": run_id,
                "step_name": "FilterStep",
                "step_type": "FILTER",
                "status": "SUCCESS",
                "started_at": "2024-01-08T12:00:00Z",
                "ended_at": "2024-01-08T12:00:01Z",
                "stats": {"input_count": 100, "output_count": 10},
                "candidates": [
                    {
                        "candidate_id": "prod_1",
                        "attributes": {"price": 50, "rating": 4.5},
                        "decision": "accepted",
                        "score": {"relevance": 0.85},
                        "reasoning": "High rating, good price",
                    },
                    {
                        "candidate_id": "prod_2",
                        "attributes": {"price": 150, "rating": 3.5},
                        "decision": "rejected",
                        "reasoning": "Price too high",
                    },
                ],
            },
        )
        assert response.status_code == 200

    def test_query_steps(self, client):
        # Create run and steps
        run_response = client.post(
            "/v1/runs", json={"pipeline_type": "TestPipeline", "metadata": {}}
        )
        run_id = run_response.json()["id"]

        client.post(
            "/v1/steps",
            json={
                "run_id": run_id,
                "step_name": "Step1",
                "step_type": "LLM",
                "status": "SUCCESS",
                "started_at": "2024-01-08T12:00:00Z",
                "stats": {},
                "candidates": [],
            },
        )
        client.post(
            "/v1/steps",
            json={
                "run_id": run_id,
                "step_name": "Step2",
                "step_type": "FILTER",
                "status": "SUCCESS",
                "started_at": "2024-01-08T12:00:00Z",
                "stats": {},
                "candidates": [],
            },
        )

        # Query all steps
        response = client.get("/v1/steps")
        assert response.status_code == 200
        assert len(response.json()) >= 2

        # Query by step_type
        response = client.get("/v1/steps?step_type=LLM")
        assert response.status_code == 200
        data = response.json()
        assert all(step["step_type"] == "LLM" for step in data)

        # Query by run_id
        response = client.get(f"/v1/steps?run_id={run_id}")
        assert response.status_code == 200
        data = response.json()
        assert all(step["run_id"] == run_id for step in data)


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
