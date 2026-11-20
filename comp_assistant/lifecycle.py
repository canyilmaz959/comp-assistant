"""Shared assistant lifecycle states."""
from enum import Enum


class RuntimeState(str, Enum):
    STANDBY = "STANDBY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
