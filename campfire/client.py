import requests

BASE_URL = "https://campfire-api.nianticlabs.com/v1"

class CampfireClient:
    def __init__(self, token: str):
        """
        token = your Campfire auth token (string).
        """
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def get(self, endpoint: str, params=None):
        """
        Makes a GET request to Campfire API.
        """
        url = f"{BASE_URL}{endpoint}"
        r = requests.get(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r.json()