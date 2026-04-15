"""Constants, status mappings, use case lists, and column normalization."""

import os

# Google Sheets config
SHEET_ID = os.getenv("GOOGLE_SHEETS_ID", "1NeBFnOax3GwMQXP8MFoZbA7q5rUfZ-jmobLH1S_8Ewo")
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials/service_account.json")
SHEET_TAB = os.getenv("SHEET_TAB", "Pipeline map")

# LLM config
try:
    import anthropic
    LLM_AVAILABLE = bool(os.getenv("ANTHROPIC_API_KEY"))
except ImportError:
    LLM_AVAILABLE = False

LLM_MODEL = "claude-sonnet-4-6"

# --- Column name normalization ---
# Maps various sheet column names to canonical internal names
COLUMN_ALIASES = {
    # Primary key
    "Unique_ID_Company": "company",
    "Company": "company",
    "company": "company",
    # Status
    "Status_dropdown": "status",
    "Current Status": "status",
    "status": "status",
    # Tier
    "Tier": "tier",
    "tier": "tier",
    # Use case
    "Canonical use case": "use_case",
    "Use case": "use_case",
    "use_case": "use_case",
    # Use case status
    "Use case status": "use_case_status",
    "H2 prio": "use_case_status",
    # TAM
    "Est. TAM (M)": "tam",
    "Est. MAUs": "tam",
    # Outreach
    "Outreach Y/N": "outreach",
    # Response
    "Responded?": "responded",
    "Inbound": "inbound",
    "Cold outreach": "cold_outreach",
    "Warm intro": "warm_intro",
    # Engagement
    "Meeting Y/N": "meeting",
    "Interested": "interested",
    "Reviewing contract offline": "reviewing_contract",
    "Signed": "signed_col",
    "Want exec intro?": "want_exec_intro",
    "Deprioritize company?": "deprioritize",
    # Notes
    "Status notes": "status_notes",
    "Status written": "status_written",
    "Last / next touch": "last_next_touch",
    "Next steps": "next_steps",
    "next step": "next_steps",
    "Partner notes": "partner_notes",
    "Our notes": "our_notes",
    "Notes": "our_notes",
    # Owner
    "TG Owner": "owner",
    "Owner": "owner",
    # Display-only
    "Mickey mapping (rough)": "mickey_mapping",
    "Simplified categories": "simplified_categories",
    "Simpler categories": "simplified_categories",
    "Simple category": "simplified_categories",
    "Outreach wave": "outreach_wave",
    "Outreach stage": "outreach_stage",
    "Outreach type": "outreach_type",
    "Intended use": "intended_use",
    "Recommended Intro": "recommended_intro",
    "Potential connection": "recommended_intro",
    "CPO": "cpo",
    "CEO": "ceo",
    "Sub-type": "sub_type",
    "Market concentration": "market_concentration",
    "Estimated MAUs (extremely rough)": "estimated_maus",
    "ID": "row_id",
    "VP outreach": "vp_outreach",
    "C-suite outreach": "csuite_outreach",
}

# --- Status mapping ---
# Supports both spec labels and actual sheet labels
STATUS_MAP = {
    # Spec labels
    "1 - Signed": {"code": 1, "score": 100},
    "2 - Intent to sign": {"code": 2, "score": 85},
    "2 - Intent to Sign": {"code": 2, "score": 85},
    "3.0 - Warm / engaged (more likely)": {"code": 3.0, "score": 70},
    "3.1 - Warm / engaged": {"code": 3.1, "score": 55},
    "3.2 - Cool-ish": {"code": 3.2, "score": 40},
    "4 - Interesting but not priority": {"code": 4, "score": 25},
    "5 - Responded, no next steps yet": {"code": 5, "score": 15},
    "6 - Haven't responded to outbound": {"code": 6, "score": 5},
    "Haven't responded to outbound": {"code": 6, "score": 5},
    "7 - Lost": {"code": 7, "score": 0},
    "8 - Other": {"code": 8, "score": 10},
    "9 - We have declined to move forward": {"code": 9, "score": 0},
    "No outreach yet": {"code": 10, "score": 8},
    "Cut from pipeline": {"code": 11, "score": 0},
    # Actual sheet labels (Pipeline map tab)
    "1 - Live": {"code": 1, "score": 100},
    "2 - Signed, not live": {"code": 2, "score": 85},
    "3 - Warm Intro": {"code": 3.0, "score": 70},
    "3 - Warm / currently engaged": {"code": 3.0, "score": 70},
    "3.5 Actively Engaged": {"code": 3.0, "score": 70},
    "3.5 - Actively Engaged": {"code": 3.0, "score": 70},
    "4 - Cold": {"code": 6, "score": 5},
    "4 - Interesting but not a priority": {"code": 4, "score": 25},
    "5 - No outreach": {"code": 10, "score": 8},
    "6 - Not interested / declined": {"code": 9, "score": 0},
    "6 - Not interested": {"code": 9, "score": 0},
    "7 - Deprioritized": {"code": 9, "score": 0},
    "9 - We have declined": {"code": 9, "score": 0},
    "9 - Lost / not a current priority": {"code": 9, "score": 0},
    "Semi-engaged": {"code": 3.1, "score": 55},
}

# For looking up by partial match
def get_status_info(status_str):
    """Get status code and score, with fuzzy matching."""
    if not status_str or not isinstance(status_str, str):
        return {"code": 10, "score": 8}  # Default: no outreach
    status_str = status_str.strip()
    # Exact match
    if status_str in STATUS_MAP:
        return STATUS_MAP[status_str]
    # Partial match
    s_lower = status_str.lower()
    for key, val in STATUS_MAP.items():
        if key.lower() in s_lower or s_lower in key.lower():
            return val
    # Number prefix match
    for key, val in STATUS_MAP.items():
        if key.split(" - ")[0] == status_str.split(" - ")[0]:
            return val
    return {"code": 10, "score": 8}

# Status labels for dropdowns
STATUS_OPTIONS = [
    "1 - Signed",
    "2 - Intent to sign",
    "3.0 - Warm / engaged (more likely)",
    "3.1 - Warm / engaged",
    "3.2 - Cool-ish",
    "4 - Interesting but not priority",
    "5 - Responded, no next steps yet",
    "6 - Haven't responded to outbound",
    "7 - Lost",
    "8 - Other",
    "9 - We have declined to move forward",
    "No outreach yet",
    "Cut from pipeline",
]

# Excluded from active ranking
EXCLUDED_STATUSES = {1, 9, 11}  # Signed, Declined, Cut
SIGNED_STATUS = {1}
DEPRIORITIZED_STATUSES = {9, 11}

# --- Canonical use cases ---
CANONICAL_USE_CASES = [
    "Content provenance",
    "Professional collaboration",
    "Expert networks",
    "Professional reviews",
    "Freemium abuse for subscriptions (professional)",
    "Freemium abuse for subscriptions (personal)",
    "Freemium abuse for subscriptions (news)",
    "P2P digital marketplaces",
    "Identity in Professional Events",
    "Job Scams (hirer/seeker)",
    "Gig platforms",
    "Chargeback fraud (high cart value)",
    "B2C chargebacks",
    "Other",
]

# --- Tier scoring ---
TIER_SCORES = {
    "1": 10,
    "2": 5,
    "3": 3,
    "ATS": 7,
}
DEFAULT_TIER_SCORE = 3

# --- Cadence rules ---
CADENCE_RULES = {
    2: {"days": 5, "max_attempts": None},
    3.0: {"days": 7, "max_attempts": None},
    3.1: {"days": 14, "max_attempts": None},
    3.2: {"days": 21, "max_attempts": 4},
    4: {"days": 30, "max_attempts": 3},
    5: {"days": 21, "max_attempts": 3},
    6: {"days": 14, "max_attempts": 5},
    7: {"days": 90, "max_attempts": 1},
    10: {"days": 0, "max_attempts": None},  # Flag for outreach planning
}

# --- Use case search terms for Sales Navigator ---
USE_CASE_SEARCH_TERMS = {
    "Expert networks": ["expert network", "research network", "advisory marketplace", "expert consultation platform"],
    "Content provenance": ["content authentication", "digital media", "AI video", "image editing", "camera manufacturer", "content creation platform"],
    "Professional reviews": ["software reviews", "product reviews", "B2B reviews", "peer reviews"],
    "Professional collaboration": ["collaboration software", "team communication", "workplace platform", "project management"],
    "Freemium abuse for subscriptions (professional)": ["SaaS", "developer tools", "cloud platform", "freemium B2B"],
    "Freemium abuse for subscriptions (news)": ["digital news", "news publisher", "media subscription", "digital journalism"],
    "Freemium abuse for subscriptions (personal)": ["consumer SaaS", "website builder", "personal productivity"],
    "P2P digital marketplaces": ["peer to peer marketplace", "P2P platform", "rental marketplace", "resale platform"],
    "Identity in Professional Events": ["event management", "event technology", "conference platform", "virtual events"],
    "Job Scams (hirer/seeker)": ["ATS", "applicant tracking", "hiring platform", "recruitment software"],
    "Gig platforms": ["gig economy", "freelance marketplace", "gig worker platform"],
    "Chargeback fraud (high cart value)": ["luxury retail", "high value ecommerce", "luxury marketplace"],
    "B2C chargebacks": ["luxury retail", "high value ecommerce", "luxury marketplace"],
}
