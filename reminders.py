"""Reminder engine — cadence rules, date parsing, smart nudges."""

import re
from datetime import datetime, timedelta
from dateutil import parser as dateparser
from config import CADENCE_RULES, get_status_info, LLM_AVAILABLE, LLM_MODEL

DATE_PATTERNS = [
    r'\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b',
    r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}(?:,?\s*\d{4})?)\b',
    r'\b(\d{4}-\d{2}-\d{2})\b',
]

PARK_PATTERNS = [
    (r'FY(\d{2})', "fy"),
    (r'Q([1-4])(?:\s*(?:20)?(\d{2}))?', "quarter"),
    (r'later in the year|end of (?:the )?year', "eoy"),
    (r'next year', "next_year"),
    (r'not until (\w+)', "not_until"),
]

NOT_NOW_KEYWORDS = [
    "not a priority", "not now", "revisit", "circle back",
    "not in a position", "timing is better", "descoped",
]


def _quarter_to_date(q, year=None):
    now = datetime.now()
    y = int(f"20{year}") if year else now.year
    month = {1: 1, 2: 4, 3: 7, 4: 10}[int(q)]
    return datetime(y, month, 1)


def _parse_month(month_str):
    try:
        dt = dateparser.parse(f"{month_str} 1")
        if dt.year < datetime.now().year:
            dt = dt.replace(year=datetime.now().year)
        if dt < datetime.now():
            dt = dt.replace(year=datetime.now().year + 1)
        return dt
    except (ValueError, TypeError):
        return datetime.now() + timedelta(days=60)


def extract_dates_from_notes(row):
    """Extract follow-up dates from notes fields. Returns (next_date, park_until, source)."""
    text_parts = []
    for field in ["status_notes", "partner_notes", "our_notes", "next_steps", "last_next_touch"]:
        val = row.get(field)
        if val and isinstance(val, str):
            text_parts.append(val)
    text = " ".join(text_parts)
    if not text.strip():
        return None, None, None

    if LLM_AVAILABLE:
        try:
            return _llm_extract_dates(text)
        except Exception:
            pass

    # Check park patterns first
    for pattern, ptype in PARK_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if ptype == "fy":
                fy = int(m.group(1))
                park_date = datetime(2000 + fy - 1, 7, 1)
                return None, park_date, f"FY{fy}"
            elif ptype == "quarter":
                q = m.group(1)
                yr = m.group(2) if m.lastindex >= 2 else None
                park_date = _quarter_to_date(q, yr)
                return None, park_date, f"Q{q}"
            elif ptype == "eoy":
                park_date = datetime.now() + timedelta(days=180)
                return None, park_date, "end of year"
            elif ptype == "next_year":
                park_date = datetime(datetime.now().year + 1, 1, 1)
                return None, park_date, "next year"
            elif ptype == "not_until":
                park_date = _parse_month(m.group(1))
                return None, park_date, f"not until {m.group(1)}"

    # Check explicit dates
    for pattern in DATE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            try:
                dt = dateparser.parse(m.group(1))
                if dt and dt > datetime.now() - timedelta(days=365):
                    if dt < datetime.now():
                        dt = dt.replace(year=datetime.now().year + 1)
                    return dt, None, m.group(0)
            except (ValueError, TypeError):
                continue

    # Check "not now" keywords
    text_lower = text.lower()
    for kw in NOT_NOW_KEYWORDS:
        if kw in text_lower:
            return datetime.now() + timedelta(days=60), None, kw

    return None, None, None


def compute_reminders(df, state):
    """Generate reminders for all active companies."""
    reminders = {}
    now = datetime.now()

    for _, row in df.iterrows():
        company = row.get("company")
        if not company:
            continue
        status_code = row.get("_status_code", 10)
        if status_code in (1, 9, 11):  # Signed, declined, cut
            continue

        existing = state.get("reminders", {}).get(company, {})

        # Extract dates from notes
        next_date, park_until, source = extract_dates_from_notes(row.to_dict())

        if park_until:
            reminders[company] = {
                "next_followup": park_until.strftime("%Y-%m-%d"),
                "cadence_days": 0,
                "parked_until": park_until.strftime("%Y-%m-%d"),
                "park_reason": source or "timing",
                "followup_count": existing.get("followup_count", 0),
                "suggested_action": f"Parked until {park_until.strftime('%b %Y')} — {source}",
                "status": row.get("status", ""),
                "owner": row.get("owner", ""),
            }
            continue

        # Get cadence rule
        cadence = CADENCE_RULES.get(status_code, {"days": 30, "max_attempts": 3})
        cadence_days = cadence["days"]
        max_attempts = cadence["max_attempts"]
        followup_count = existing.get("followup_count", 0)

        # Determine next followup date
        if next_date:
            followup_date = next_date
        elif existing.get("next_followup"):
            try:
                followup_date = datetime.strptime(existing["next_followup"], "%Y-%m-%d")
            except (ValueError, TypeError):
                followup_date = now + timedelta(days=cadence_days)
        else:
            followup_date = now + timedelta(days=cadence_days)

        # Check if max attempts exceeded
        needs_decision = max_attempts and followup_count >= max_attempts

        # Generate suggested action
        suggested = _suggest_action(row.to_dict(), status_code, followup_count)

        reminders[company] = {
            "next_followup": followup_date.strftime("%Y-%m-%d"),
            "cadence_days": cadence_days,
            "parked_until": None,
            "park_reason": None,
            "followup_count": followup_count,
            "suggested_action": suggested,
            "needs_decision": needs_decision,
            "status": row.get("status", ""),
            "owner": row.get("owner", ""),
        }

    return reminders


def _suggest_action(row, status_code, followup_count):
    """Generate a context-aware action suggestion."""
    company = row.get("company", "Company")
    if status_code == 2:
        return "Push for contract finalization"
    elif status_code in (3.0, 3.1):
        return "Check in on progress, share recent wins"
    elif status_code == 3.2:
        if followup_count > 2:
            return "Consider sharing social proof or escalating"
        return "Re-engage with new value prop"
    elif status_code == 4:
        return "Share a relevant partner success story"
    elif status_code == 5:
        return "Propose a specific next step or meeting"
    elif status_code == 6:
        if followup_count > 3:
            return "Try different channel or contact"
        return "Send follow-up email"
    elif status_code == 7:
        return "90-day re-engagement check — has anything changed?"
    elif status_code == 10:
        return "Plan initial outreach"
    return "Follow up"


def generate_nudges(df, state):
    """Generate smart nudges based on pipeline state."""
    nudges = []

    # Social proof nudge: recent wins
    for event in reversed(state.get("event_log", [])[-10:]):
        new_code = get_status_info(event.get("new_status", ""))["code"]
        if new_code in (1, 2, 3.0):
            use_case = None
            company_row = df[df["company"] == event["company"]]
            if not company_row.empty:
                use_case = company_row.iloc[0].get("use_case")
            if use_case:
                stalled = df[
                    (df["use_case"] == use_case)
                    & (df["_status_code"].isin([3.2, 4, 5, 6]))
                    & (df["company"] != event["company"])
                ]
                if not stalled.empty:
                    names = stalled["company"].tolist()[:5]
                    nudges.append({
                        "type": "social_proof",
                        "icon": "🏆",
                        "message": f"{event['company']} advanced to {event['new_status']} → share with {', '.join(names)} as social proof",
                    })

    # Use case gap alert
    from scoring import compute_use_case_win_rates
    win_rates, _ = compute_use_case_win_rates(df)
    for uc, rate in win_rates.items():
        active = df[(df["use_case"] == uc) & (~df["_status_code"].isin({1, 7, 9, 11}))]
        if rate > 0.5 and len(active) <= 2:
            nudges.append({
                "type": "gap",
                "icon": "🔍",
                "message": f"{uc} has {rate:.0%} win rate but only {len(active)} active prospects — time to prospect",
            })

    # Staleness alert
    for uc in df["use_case"].dropna().unique():
        if not uc:
            continue
        uc_companies = df[(df["use_case"] == uc) & (~df["_status_code"].isin({1, 9, 11}))]
        # Count stale (rough: status code 5 or 6)
        stale = uc_companies[uc_companies["_status_code"].isin([5, 6])]
        if len(stale) >= 5:
            nudges.append({
                "type": "staleness",
                "icon": "⏰",
                "message": f"{len(stale)} {uc} companies are stalled (status 5-6) — review batch",
            })

    # Batch outreach
    for uc in df["use_case"].dropna().unique():
        if not uc:
            continue
        no_outreach = df[(df["use_case"] == uc) & (df["_status_code"] == 10)]
        if len(no_outreach) >= 4:
            names = no_outreach["company"].tolist()[:6]
            nudges.append({
                "type": "batch",
                "icon": "📧",
                "message": f"{len(no_outreach)} {uc} companies have no outreach ({', '.join(names)}) — consider batch campaign",
            })

    return nudges
