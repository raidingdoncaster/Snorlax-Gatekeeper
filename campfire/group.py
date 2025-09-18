from .client import CampfireClient

def get_group_info(client: CampfireClient, group_id: str):
    return client.get(f"/groups/{group_id}")

def get_group_members(client: CampfireClient, group_id: str):
    data = client.get(f"/groups/{group_id}/members")
    return data.get("members", [])