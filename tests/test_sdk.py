import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import Mock, patch
from sdk.core import xray_run, xray_step, serialize
from sdk.client import XRayClient


class TestSerialization:
    def test_serialize_primitives(self):
        assert serialize("test") == "test"
        assert serialize(123) == 123
        assert serialize(1.5) == 1.5
        assert serialize(True) == True
        assert serialize(None) is None

    def test_serialize_dict(self):
        data = {"key": "value", "number": 42}
        result = serialize(data)
        assert result == {"key": "value", "number": 42}

    def test_serialize_list(self):
        data = [1, "two", 3.0]
        result = serialize(data)
        assert result == [1, "two", 3.0]

    def test_serialize_nested(self):
        data = {"list": [1, 2, {"nested": "value"}], "dict": {"key": "val"}}
        result = serialize(data)
        assert result == {"list": [1, 2, {"nested": "value"}], "dict": {"key": "val"}}

    def test_serialize_object_with_dict(self):
        class TestObj:
            def __init__(self):
                self.public = "visible"
                self._private = "hidden"

        obj = TestObj()
        result = serialize(obj)
        assert result == {"public": "visible"}
        assert "_private" not in result


class TestXRayClient:
    @patch("sdk.client.requests.post")
    def test_start_run_success(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"id": "run_123"}

        client = XRayClient()
        run_id = client.start_run("TestPipeline", {"key": "value"})

        assert run_id == "run_123"
        mock_post.assert_called_once()

    @patch("sdk.client.requests.post")
    def test_start_run_api_failure(self, mock_post):
        mock_post.return_value.status_code = 500

        client = XRayClient()
        run_id = client.start_run("TestPipeline", {"key": "value"})

        assert run_id is None

    @patch("sdk.client.requests.post")
    def test_start_run_timeout(self, mock_post):
        mock_post.side_effect = Exception("Timeout")

        client = XRayClient()
        run_id = client.start_run("TestPipeline", {"key": "value"})

        assert run_id is None  # Should gracefully return None

    @patch("sdk.client.requests.post")
    def test_record_step_success(self, mock_post):
        mock_post.return_value.status_code = 200

        client = XRayClient()
        client.record_step({"run_id": "run_123", "step_name": "TestStep"})

        mock_post.assert_called_once()

    @patch("sdk.client.requests.post")
    def test_record_step_failure_does_not_crash(self, mock_post):
        mock_post.side_effect = Exception("Network error")

        client = XRayClient()
        # Should not raise exception
        client.record_step({"run_id": "run_123", "step_name": "TestStep"})


class TestXRayRun:
    @patch("sdk.client.client.start_run")
    def test_run_context_creates_run(self, mock_start_run):
        mock_start_run.return_value = "run_123"

        with xray_run("TestPipeline", metadata={"key": "value"}) as run:
            assert run.run_id == "run_123"

        mock_start_run.assert_called_once_with("TestPipeline", {"key": "value"}, None, None)

    @patch("sdk.client.client.start_run")
    def test_run_context_handles_no_run_id(self, mock_start_run):
        mock_start_run.return_value = None

        with xray_run("TestPipeline") as run:
            assert run.run_id is None
            # Should not crash


class TestXRayStep:
    @patch("sdk.client.client.record_step")
    @patch("sdk.client.client.start_run")
    def test_step_records_success(self, mock_start_run, mock_record_step):
        mock_start_run.return_value = "run_123"

        with xray_run("TestPipeline"):
            with xray_step("TestStep", "LLM"):
                pass

        assert mock_record_step.called
        call_args = mock_record_step.call_args[0][0]
        assert call_args["step_name"] == "TestStep"
        assert call_args["step_type"] == "LLM"
        assert call_args["status"] == "SUCCESS"

    @patch("sdk.client.client.record_step")
    @patch("sdk.client.client.start_run")
    def test_step_records_failure(self, mock_start_run, mock_record_step):
        mock_start_run.return_value = "run_123"

        try:
            with xray_run("TestPipeline"):
                with xray_step("TestStep", "LLM"):
                    raise ValueError("Test error")
        except ValueError:
            pass

        call_args = mock_record_step.call_args[0][0]
        assert call_args["status"] == "FAILURE"
        assert "Test error" in call_args["meta"]["error"]

    @patch("sdk.client.client.record_step")
    @patch("sdk.client.client.start_run")
    def test_step_logs_stats(self, mock_start_run, mock_record_step):
        mock_start_run.return_value = "run_123"

        with xray_run("TestPipeline"):
            with xray_step("TestStep", "FILTER") as step:
                step.log_stats(input_count=100, output_count=10, custom_metric=42)

        call_args = mock_record_step.call_args[0][0]
        assert call_args["stats"]["input_count"] == 100
        assert call_args["stats"]["output_count"] == 10
        assert call_args["stats"]["custom_metric"] == 42

    @patch("sdk.client.client.record_step")
    @patch("sdk.client.client.start_run")
    def test_step_logs_candidates(self, mock_start_run, mock_record_step):
        mock_start_run.return_value = "run_123"

        with xray_run("TestPipeline"):
            with xray_step("TestStep", "FILTER") as step:
                step.log_sampled_candidates(
                    accepted=[{"id": "prod_1", "price": 50}],
                    rejected=[{"id": "prod_2", "price": 150}],
                )

        call_args = mock_record_step.call_args[0][0]
        candidates = call_args["candidates"]

        accepted = [c for c in candidates if c["decision"] == "accepted"]
        rejected = [c for c in candidates if c["decision"] == "rejected"]

        assert len(accepted) == 1
        assert len(rejected) == 1
        assert accepted[0]["candidate_id"] == "prod_1"
        assert rejected[0]["candidate_id"] == "prod_2"

    @patch("sdk.client.client.record_step")
    @patch("sdk.client.client.start_run")
    def test_step_logs_candidates_with_reasoning(self, mock_start_run, mock_record_step):
        """Test logging candidates with reasoning using tuple format."""
        mock_start_run.return_value = "run_123"

        with xray_run("TestPipeline"):
            with xray_step("FilterStep", "FILTER") as step:
                # Tuple format: (candidate, reasoning)
                step.log_sampled_candidates(
                    rejected=[
                        ({"id": "prod_1", "price": 150}, "Price too high"),
                        ({"id": "prod_2", "rating": 3.0}, "Rating too low"),
                    ]
                )

        call_args = mock_record_step.call_args[0][0]
        candidates = call_args["candidates"]

        assert len(candidates) == 2
        assert candidates[0]["candidate_id"] == "prod_1"
        assert candidates[0]["reasoning"] == "Price too high"
        assert candidates[1]["candidate_id"] == "prod_2"
        assert candidates[1]["reasoning"] == "Rating too low"

    @patch("sdk.client.client.record_step")
    @patch("sdk.client.client.start_run")
    def test_step_logs_candidates_with_score_and_reasoning(self, mock_start_run, mock_record_step):
        """Test logging candidates with score and reasoning using 3-tuple format."""
        mock_start_run.return_value = "run_123"

        with xray_run("TestPipeline"):
            with xray_step("RankingStep", "LLM") as step:
                # 3-tuple format: (candidate, score, reasoning)
                step.log_sampled_candidates(
                    selected=[
                        (
                            {"id": "prod_1", "title": "Winner"},
                            {"relevance": 0.95, "quality": 0.88},
                            "Best overall match",
                        )
                    ],
                    rejected=[
                        (
                            {"id": "prod_2", "title": "Runner-up"},
                            {"relevance": 0.75},
                            "Good but not the best",
                        )
                    ],
                )

        call_args = mock_record_step.call_args[0][0]
        candidates = call_args["candidates"]

        selected = [c for c in candidates if c["decision"] == "selected"]
        rejected = [c for c in candidates if c["decision"] == "rejected"]

        assert len(selected) == 1
        assert selected[0]["candidate_id"] == "prod_1"
        assert selected[0]["score"]["relevance"] == 0.95
        assert selected[0]["reasoning"] == "Best overall match"

        assert len(rejected) == 1
        assert rejected[0]["score"]["relevance"] == 0.75
        assert rejected[0]["reasoning"] == "Good but not the best"

    @patch("sdk.client.client.record_step")
    @patch("sdk.client.client.start_run")
    def test_step_logs_candidates_with_reasoning_in_dict(self, mock_start_run, mock_record_step):
        """Test that reasoning/score can also be in the dict directly."""
        mock_start_run.return_value = "run_123"

        with xray_run("TestPipeline"):
            with xray_step("FilterStep", "FILTER") as step:
                step.log_sampled_candidates(
                    rejected=[
                        {
                            "id": "prod_1",
                            "price": 150,
                            "reasoning": "Price exceeds threshold",
                            "score": {"relevance": 0.3},
                        }
                    ]
                )

        call_args = mock_record_step.call_args[0][0]
        candidates = call_args["candidates"]

        assert len(candidates) == 1
        assert candidates[0]["reasoning"] == "Price exceeds threshold"
        assert candidates[0]["score"]["relevance"] == 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
