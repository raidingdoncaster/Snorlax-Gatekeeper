from dataclasses import dataclass
from typing import List

@dataclass
class Member:
    id: str
    name: str
    avatar: str

@dataclass
class Event:
    id: str
    title: str
    description: str
    start_time: str
    end_time: str
    location: str

@dataclass
class Attendee:
    id: str
    name: str
    avatar: str