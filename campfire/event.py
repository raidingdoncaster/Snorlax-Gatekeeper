from .client import CampfireClient

def get_group_events(client: CampfireClient, group_id: str):
    data = client.get(f"/groups/{group_id}/events")
    return data.get("events", [])

def get_event_attendees(client: CampfireClient, event_id: str):
    data = client.get(f"/events/{event_id}/attendees")
    return data.get("attendees", [])