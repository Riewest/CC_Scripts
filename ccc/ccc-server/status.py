from enum import Enum


class Status(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    NEEDS_FUEL = "needs_fuel"
    REFUELING = "refueling"
    RETURNING = "returning"
    UNLOADING = "unloading"
    USER_ACTION = "user_action"
    PANIC = "panic"


# CSS color tokens for each status, used by the dashboard.
# Each entry: { "background": <css>, "color": <css>, "border": <css> }
STATUS_COLORS = {
    Status.IDLE:        {"background": "#3f3f4633", "color": "#a1a1aa", "border": "1px solid #3f3f4666"},
    Status.WORKING:     {"background": "#2563eb22", "color": "#60a5fa", "border": "1px solid #2563eb55"},
    Status.NEEDS_FUEL:  {"background": "#ea580c22", "color": "#fb923c", "border": "1px solid #ea580c55"},
    Status.REFUELING:   {"background": "#ca8a0422", "color": "#fbbf24", "border": "1px solid #ca8a0455"},
    Status.RETURNING:   {"background": "#16a34a22", "color": "#4ade80", "border": "1px solid #16a34a55"},
    Status.UNLOADING:   {"background": "#7c3aed22", "color": "#a78bfa", "border": "1px solid #7c3aed55"},
    Status.USER_ACTION: {"background": "#0d948822", "color": "#2dd4bf", "border": "1px solid #0d948855"},
    Status.PANIC:       {"background": "#dc262622", "color": "#f87171", "border": "1px solid #dc262655"},
}