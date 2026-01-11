import requests
import uuid
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("xray")

class XRayClient:
    def __init__(self, api_url: str = "http://localhost:8000/v1"):
        self.api_url = api_url.rstrip("/")
    
    def start_run(self, pipeline_type: str, metadata: Dict[str, Any] = None, repository: str = None, version: str = None) -> Optional[str]:
        """Creates a new run."""
        payload = {
            "pipeline_type": pipeline_type,
            "metadata": metadata or {}
        }
        if repository:
            payload["repository"] = repository
        if version:
            payload["version"] = version
        try:
            resp = requests.post(f"{self.api_url}/runs", json=payload, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                return data["id"]
            else:
                logger.error(f"Failed to start run: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"X-Ray API unavailable: {e}")
            return None

    def record_step(self, step_data: Dict[str, Any]):
        """Records a step."""
        try:
            # step_data will match StepCreate schema (step_name, step_type, stats, etc.)
            resp = requests.post(f"{self.api_url}/steps", json=step_data, timeout=2)
            if resp.status_code != 200:
                logger.error(f"Failed to record step: {resp.text}")
        except Exception as e:
            logger.error(f"X-Ray API unavailable: {e}")

client = XRayClient()
