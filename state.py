"""Local state management — read/write JSON state file."""

import json
import os
from datetime import datetime

STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")

DEFAULT_STATE = {
    "scores": {},
    "event_log": [],
    "reminders": {},
    "hunting_briefs": {},
    "added_companies": [],
}


def load_state():
    """Load state from JSON file, or return default."""
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r") as f:
                state = json.load(f)
            # Ensure all keys exist
            for k, v in DEFAULT_STATE.items():
                if k not in state:
                    state[k] = v if not isinstance(v, (dict, list)) else type(v)()
            return state
        except (json.JSONDecodeError, IOError):
            return {k: (type(v)() if isinstance(v, (dict, list)) else v) for k, v in DEFAULT_STATE.items()}
    return {k: (type(v)() if isinstance(v, (dict, list)) else v) for k, v in DEFAULT_STATE.items()}


def save_state(state):
    """Persist state to JSON file."""
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


def log_event(state, company, old_status, new_status, reason_text="", reason_category="", propagation_actions=None):
    """Append an event to the event log."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "company": company,
        "old_status": old_status,
        "new_status": new_status,
        "reason_text": reason_text,
        "reason_category": reason_category,
        "propagation_actions": propagation_actions or [],
    }
    state["event_log"].append(event)
    return event


def update_score(state, company, score_data):
    """Update a company's score in state."""
    score_data["last_computed"] = datetime.now().strftime("%Y-%m-%d")
    state["scores"][company] = score_data


def update_reminder(state, company, reminder_data):
    """Update a company's reminder in state."""
    state["reminders"][company] = reminder_data


def add_company(state, company, source="manual", initial_score=0):
    """Track a newly added company."""
    state["added_companies"].append({
        "company": company,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "source": source,
        "initial_score": initial_score,
    })
