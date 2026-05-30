import os

class GitLabTool:
    def __init__(self, demo_mode=False):
        self.demo_mode = demo_mode
        self.token = os.getenv("GITLAB_TOKEN")
        self.project_id = os.getenv("GITLAB_PROJECT_ID")
        self.base_url = os.getenv("GITLAB_BASE_URL", "https://gitlab.com/api/v4")

    def _headers(self) -> dict:
        return {"PRIVATE-TOKEN": self.token or ""}

    def get_recent_deployments(self, limit: int = 5) -> list:
        if self.demo_mode:
            return [{
                "id": "1842",
                "status": "success",
                "created_at": "4h 31m ago",
                "ref": "refactor/schema-v2",
                "user": "jane.doe"
            }]
        import requests
        response = requests.get(
            f"{self.base_url}/projects/{self.project_id}/deployments",
            headers=self._headers(),
            params={"per_page": limit, "order_by": "created_at", "sort": "desc"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def get_pipeline_status(self, pipeline_id: str) -> dict:
        if self.demo_mode:
            return {"id": pipeline_id, "status": "success"}
        import requests
        response = requests.get(
            f"{self.base_url}/projects/{self.project_id}/pipelines/{pipeline_id}",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def rollback_deployment(self, deployment_id: str, project_id: str | None = None) -> dict:
        if self.demo_mode:
            return {"status": "success", "message": f"Rolled back to deployment {deployment_id}"}
        import requests
        target_project = project_id or self.project_id
        response = requests.post(
            f"{self.base_url}/projects/{target_project}/deployments/{deployment_id}/rollback",
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
