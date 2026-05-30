import os
from requests.auth import HTTPBasicAuth

class FivetranTool:
    def __init__(self, demo_mode=False):
        self.demo_mode = demo_mode
        self.api_key = os.getenv("FIVETRAN_API_KEY")
        self.api_secret = os.getenv("FIVETRAN_API_SECRET")
        self.base_url = "https://api.fivetran.com/v1"

    def get_connector_status(self, connector_id: str) -> dict:
        if self.demo_mode:
            return {
                "id": connector_id,
                "status": "failed",
                "last_sync": "4h 12m ago",
                "health": "critical",
                "error": "Destination schema field arr_amount_usd missing after deployment #1842",
            }
        import requests
        response = requests.get(
            f"{self.base_url}/connectors/{connector_id}",
            auth=HTTPBasicAuth(self.api_key or "", self.api_secret or ""),
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get("data", {})

    def get_recent_failures(self) -> list:
        if self.demo_mode:
            return [{"id": "salesforce-crm", "error": "Schema field arr_amount_usd not found"}]
        status = self.get_connector_status(os.getenv("FIVETRAN_CONNECTOR_ID", ""))
        return [status] if status.get("status", {}).get("sync_state") == "failed" else []

    def trigger_resync(self, connector_id: str) -> dict:
        if self.demo_mode:
            return {"status": "success", "message": f"Resync triggered for {connector_id}"}
        import requests
        response = requests.post(
            f"{self.base_url}/connectors/{connector_id}/force",
            auth=HTTPBasicAuth(self.api_key or "", self.api_secret or ""),
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get("data", {"status": "success"})

    def get_sync_stats(self, connector_id: str) -> dict:
        if self.demo_mode:
            return {"rows_synced": 14882, "source_rows": 14882, "parity": True}
        import requests
        response = requests.get(
            f"{self.base_url}/connectors/{connector_id}/schemas",
            auth=HTTPBasicAuth(self.api_key or "", self.api_secret or ""),
            timeout=20,
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        return {
            "rows_synced": data.get("rows_synced", 0),
            "source_rows": data.get("source_rows", data.get("rows_synced", 0)),
            "parity": data.get("rows_synced") == data.get("source_rows") if "rows_synced" in data else None,
            "schemas": data,
        }
