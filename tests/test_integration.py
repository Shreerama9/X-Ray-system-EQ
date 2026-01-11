"""
Integration tests for X-Ray SDK + API
Tests the full flow: SDK -> API -> Database -> Query
"""

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from api.database import Base, get_db
from api import models  # Import models to register them with Base
from sdk import xray_run, xray_step, client as xray_client


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_integration.db"
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
def api_client(test_db):
    return TestClient(app)


@pytest.fixture
def sdk_client(api_client, monkeypatch):
    """Patch the SDK client to use TestClient instead of real HTTP requests."""
    import requests

    # Store original requests.post before patching
    original_post = requests.post

    # Create a wrapper that converts requests calls to TestClient calls
    class MockResponse:
        def __init__(self, response):
            self._response = response
            self.status_code = response.status_code
            self.text = response.text

        def json(self):
            return self._response.json()

    def mock_post(url, **kwargs):
        # Only intercept testserver URLs, let others fail naturally
        if url.startswith("http://testserver"):
            path = url.replace("http://testserver", "")
            return MockResponse(api_client.post(path, **kwargs))
        else:
            # Let real requests.post handle non-testserver URLs (will fail)
            return original_post(url, **kwargs)

    # Patch requests.post to use TestClient
    monkeypatch.setattr(requests, "post", mock_post)

    # Point SDK to test server
    xray_client.api_url = "http://testserver/v1"
    return xray_client


class TestFullPipelineFlow:
    """Test the complete flow from SDK instrumentation to API querying."""

    def test_simple_pipeline_with_stats(self, api_client, sdk_client):
        """Test a simple pipeline with stats tracking."""
        # Override the client in the SDK
        from sdk import client as sdk_client_module

        sdk_client_module.client = sdk_client

        # Run a simple pipeline
        with xray_run("TestPipeline", metadata={"test": "simple"}) as run:
            run_id = run.run_id
            assert run_id is not None

            with xray_step("Step1", "LLM") as step:
                step.log_stats(input_count=10, output_count=5, tokens=150)

            with xray_step("Step2", "FILTER") as step:
                step.log_stats(input_count=5, output_count=2, filter_rate=0.6)

        # Query the run
        response = api_client.get(f"/v1/runs/{run_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["pipeline_type"] == "TestPipeline"
        assert data["metadata"]["test"] == "simple"
        assert len(data["steps"]) == 2

        # Check step stats
        step1 = next(s for s in data["steps"] if s["step_name"] == "Step1")
        assert step1["stats"]["input_count"] == 10
        assert step1["stats"]["output_count"] == 5
        assert step1["stats"]["tokens"] == 150

        step2 = next(s for s in data["steps"] if s["step_name"] == "Step2")
        assert step2["stats"]["filter_rate"] == 0.6

    def test_pipeline_with_candidates_and_reasoning(self, api_client, sdk_client):
        """Test pipeline with candidates that have reasoning and scores."""
        from sdk import client as sdk_client_module

        sdk_client_module.client = sdk_client

        with xray_run("CompetitorDiscovery", metadata={"product_id": "prod_123"}) as run:
            run_id = run.run_id

            with xray_step("FilterStep", "FILTER") as step:
                # Test candidate with reasoning (tuple format)
                rejected = [
                    (
                        {"id": "prod_1", "title": "Expensive Product", "price": 150},
                        "Price $150 exceeds threshold $100",
                    ),
                    (
                        {"id": "prod_2", "title": "Low Rating", "rating": 3.0},
                        "Rating 3.0 below minimum 4.0",
                    ),
                ]

                accepted = [
                    {"id": "prod_3", "title": "Good Product", "price": 50, "rating": 4.5}
                ]

                step.log_stats(input_count=3, output_count=1)
                step.log_sampled_candidates(accepted=accepted, rejected=rejected)

            with xray_step("RankingStep", "LLM") as step:
                # Test candidate with score and reasoning (3-tuple format)
                selected = [
                    (
                        {"id": "prod_3", "title": "Good Product"},
                        {"relevance": 0.85, "quality": 0.92},
                        "Best match based on price and rating",
                    )
                ]

                step.log_stats(input_count=1, output_count=1)
                step.log_sampled_candidates(selected=selected)

        # Verify via API
        response = api_client.get(f"/v1/runs/{run_id}")
        assert response.status_code == 200

        data = response.json()

        # We need to query candidates separately since they're in a related table
        # For now, verify the structure exists
        assert len(data["steps"]) == 2

    def test_pipeline_with_repository_tracking(self, api_client, sdk_client):
        """Test repository and version tracking."""
        from sdk import client as sdk_client_module

        sdk_client_module.client = sdk_client

        with xray_run(
            "TestPipeline",
            metadata={"test": "repo"},
            repository="github.com/company/pipelines",
            version="a3f8c2d",
        ) as run:
            run_id = run.run_id

            with xray_step("Step1", "LLM"):
                pass

        # Query and verify
        response = api_client.get(f"/v1/runs/{run_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["repository"] == "github.com/company/pipelines"
        assert data["version"] == "a3f8c2d"

    def test_cross_pipeline_step_query(self, api_client, sdk_client):
        """Test querying steps across multiple pipelines."""
        from sdk import client as sdk_client_module

        sdk_client_module.client = sdk_client

        # Create multiple runs with different pipelines
        with xray_run("Pipeline1") as run:
            with xray_step("FilterStep", "FILTER") as step:
                step.log_stats(input_count=100, output_count=10, filter_rate=0.9)

        with xray_run("Pipeline2") as run:
            with xray_step("FilterStep", "FILTER") as step:
                step.log_stats(input_count=50, output_count=5, filter_rate=0.9)

        with xray_run("Pipeline2") as run:
            with xray_step("LLMStep", "LLM") as step:
                step.log_stats(input_count=5, output_count=1)

        # Query all FILTER steps
        response = api_client.get("/v1/steps?step_type=FILTER")
        assert response.status_code == 200

        steps = response.json()
        filter_steps = [s for s in steps if s["step_type"] == "FILTER"]
        assert len(filter_steps) >= 2

        # All should be FILTER type
        assert all(s["step_type"] == "FILTER" for s in filter_steps)

    def test_pipeline_failure_tracking(self, api_client, sdk_client):
        """Test that failures are properly tracked."""
        from sdk import client as sdk_client_module

        sdk_client_module.client = sdk_client

        try:
            with xray_run("TestPipeline") as run:
                run_id = run.run_id

                with xray_step("Step1", "LLM"):
                    pass

                with xray_step("Step2", "API"):
                    raise ValueError("API timeout")
        except ValueError:
            pass  # Expected

        # Verify failure was recorded
        response = api_client.get(f"/v1/runs/{run_id}")
        assert response.status_code == 200

        data = response.json()
        step2 = next(s for s in data["steps"] if s["step_name"] == "Step2")
        assert step2["status"] == "FAILURE"
        assert "API timeout" in step2["meta"]["error"]

    def test_graceful_degradation_when_api_down(self, sdk_client):
        """Test that pipeline continues when X-Ray API is unavailable."""
        # Import the client module directly
        from sdk.client import client as xray_client_instance

        # Point to non-existent API
        original_url = xray_client_instance.api_url
        xray_client_instance.api_url = "http://nonexistent:9999/v1"

        # Pipeline should not crash
        executed = False
        try:
            with xray_run("TestPipeline") as run:
                assert run.run_id is None  # Should be None when API is down

                with xray_step("Step1", "LLM"):
                    executed = True
                    # Business logic continues
                    result = 42

            assert executed  # Verify business logic ran
        finally:
            # Restore
            xray_client_instance.api_url = original_url


class TestQueryingCapabilities:
    """Test advanced querying capabilities."""

    def test_query_by_pipeline_type(self, api_client, sdk_client):
        """Test filtering runs by pipeline type."""
        from sdk import client as sdk_client_module

        sdk_client_module.client = sdk_client

        with xray_run("PipelineA"):
            pass

        with xray_run("PipelineB"):
            pass

        with xray_run("PipelineA"):
            pass

        # Query for PipelineA only
        response = api_client.get("/v1/runs?pipeline_type=PipelineA")
        assert response.status_code == 200

        runs = response.json()
        assert len(runs) >= 2
        assert all(r["pipeline_type"] == "PipelineA" for r in runs)

    def test_query_by_status(self, api_client, sdk_client):
        """Test filtering runs by status."""
        from sdk import client as sdk_client_module

        sdk_client_module.client = sdk_client

        # Create successful run
        with xray_run("TestPipeline"):
            with xray_step("Step1", "LLM"):
                pass

        # Create failed run
        try:
            with xray_run("TestPipeline"):
                with xray_step("Step1", "LLM"):
                    raise Exception("Failure")
        except:
            pass

        # Both should show up (status is tracked at step level, not run level in our simple impl)
        response = api_client.get("/v1/runs?pipeline_type=TestPipeline")
        assert response.status_code == 200
        assert len(response.json()) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
