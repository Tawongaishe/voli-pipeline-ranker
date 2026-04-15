"""Scoring engine — composite score calculation with all components."""

import math
from datetime import datetime, timedelta
import pandas as pd
from config import (
    get_status_info, TIER_SCORES, DEFAULT_TIER_SCORE,
    EXCLUDED_STATUSES, SIGNED_STATUS,
)


def compute_use_case_win_rates(df):
    """Calculate win rate per canonical use case with Bayesian smoothing."""
    win_rates = {}
    # Global stats for smoothing
    engaged_mask = df["_status_code"].isin([1, 2, 3.0, 3.1, 3.2, 7])
    global_wins = df["_status_code"].isin([1, 2, 3.0]).sum()
    global_engaged = engaged_mask.sum()
    global_rate = global_wins / max(global_engaged, 1)

    for uc in df["use_case"].dropna().unique():
        if not uc or str(uc).strip() == "":
            continue
        uc_df = df[df["use_case"] == uc]
        uc_engaged = uc_df["_status_code"].isin([1, 2, 3.0, 3.1, 3.2, 7])
        n = uc_engaged.sum()
        wins = uc_df["_status_code"].isin([1, 2, 3.0]).sum()

        if n == 0:
            win_rates[uc] = global_rate
        else:
            raw_rate = wins / n
            # Bayesian smoothing: blend with global when n < 3
            blended = (n * raw_rate + 3 * global_rate) / (n + 3)
            win_rates[uc] = blended

    return win_rates, global_rate


def _tam_score(tam_value):
    """TAM component using log scale (max 15)."""
    if tam_value is None or not isinstance(tam_value, (int, float)) or tam_value <= 0:
        return 5  # default for unknown
    return min(15, max(0, math.log10(tam_value * 10) * 3.75))


def _engagement_score(row):
    """Sum engagement signals, capped at 15."""
    score = 0
    if _is_yes(row.get("outreach")):
        score += 1
    responded = str(row.get("responded", "")).lower()
    if responded in ("warm", "inbound"):
        score += 3
    elif responded == "cold":
        score += 1
    # Check inbound/cold/warm columns from actual sheet
    if _is_yes(row.get("inbound")):
        score += 3
    if _is_yes(row.get("warm_intro")):
        score += 2
    if _is_yes(row.get("meeting")):
        score += 3
    if _is_yes(row.get("interested")):
        score += 3
    if _is_yes(row.get("reviewing_contract")):
        score += 4
    if _is_yes(row.get("signed_col")):
        score += 5
    if _is_yes(row.get("want_exec_intro")):
        score -= 1
    if _is_true(row.get("deprioritize")):
        score -= 5
    return max(0, min(15, score))


def _tier_score(tier):
    """Tier bonus (max 10)."""
    tier_str = str(tier).strip() if tier else ""
    return TIER_SCORES.get(tier_str, DEFAULT_TIER_SCORE)


def _staleness_factor(row):
    """Reduce score for stale statuses."""
    status_code = row.get("_status_code", 10)
    # Don't decay signed, parked, or no-outreach
    if status_code in (1, 10):
        return 1.0
    date_str = row.get("status_written") or row.get("last_next_touch")
    if not date_str or not isinstance(date_str, str):
        return 1.0
    try:
        from dateutil import parser as dateparser
        dt = dateparser.parse(str(date_str))
        days = (datetime.now() - dt).days
        if days >= 90:
            return 0.6
        elif days >= 60:
            return 0.75
        elif days >= 30:
            return 0.9
    except (ValueError, TypeError):
        pass
    return 1.0


def _decay_penalty(row):
    """Decay for non-responsive companies."""
    status_code = row.get("_status_code", 10)
    days = _days_since_outreach(row)
    if days is None:
        return 0
    if status_code == 6:  # Haven't responded
        if days <= 30:
            return 0
        elif days <= 60:
            return 3
        elif days <= 90:
            return 6
        else:
            return 10
    elif status_code == 5:  # Responded, no next steps
        if days <= 14:
            return 0
        elif days <= 30:
            return 3
        elif days <= 60:
            return 6
        else:
            return 10
    return 0


def _days_since_outreach(row):
    """Estimate days since first outreach from available dates."""
    for field in ["status_written", "last_next_touch"]:
        date_str = row.get(field)
        if date_str and isinstance(date_str, str):
            try:
                from dateutil import parser as dateparser
                dt = dateparser.parse(str(date_str))
                return (datetime.now() - dt).days
            except (ValueError, TypeError):
                continue
    return None


def _is_yes(val):
    if val is None:
        return False
    return str(val).strip().upper() in ("Y", "YES", "TRUE", "1")


def _is_true(val):
    if val is None:
        return False
    return str(val).strip().upper() in ("TRUE", "Y", "YES", "1")


def compute_scores(df, state=None):
    """Compute composite scores for all companies. Returns df with score columns."""
    # Add status code column
    df["_status_code"] = df["status"].apply(lambda s: get_status_info(s)["code"])
    df["_status_score"] = df["status"].apply(lambda s: get_status_info(s)["score"])

    # Compute use case win rates
    win_rates, global_rate = compute_use_case_win_rates(df)

    # Get propagation penalties from state
    prop_penalties = {}
    if state:
        for company, score_data in state.get("scores", {}).items():
            if "propagation_penalty" in score_data:
                prop_penalties[company] = score_data["propagation_penalty"]

    scores = []
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        uc = row_dict.get("use_case", "")
        uc_rate = win_rates.get(uc, global_rate) if uc else global_rate

        use_case_component = uc_rate * 35
        stage_raw = (row_dict.get("_status_score", 8) / 100) * 25
        staleness = _staleness_factor(row_dict)
        stage_component = stage_raw * staleness

        # Parse TAM
        tam_val = row_dict.get("tam")
        try:
            tam_val = float(tam_val) if tam_val else None
        except (ValueError, TypeError):
            tam_val = None
        tam_component = _tam_score(tam_val)

        engagement_component = _engagement_score(row_dict)
        tier_component = _tier_score(row_dict.get("tier"))
        decay = _decay_penalty(row_dict)
        propagation = prop_penalties.get(row_dict.get("company", ""), 0)

        composite = (
            use_case_component
            + stage_component
            + tam_component
            + engagement_component
            + tier_component
            - decay
            - propagation
        )
        composite = max(0, min(100, composite))

        scores.append({
            "composite_score": round(composite, 1),
            "use_case_win_rate": round(uc_rate, 3),
            "stage_score": round(stage_component, 1),
            "tam_score": round(tam_component, 1),
            "engagement_score": engagement_component,
            "tier_score": tier_component,
            "decay_penalty": decay,
            "propagation_penalty": propagation,
        })

    score_df = pd.DataFrame(scores, index=df.index)
    result = pd.concat([df, score_df], axis=1)
    return result, win_rates


def apply_propagation(df, lost_company, failure_category, state):
    """Apply propagation penalties when a company is lost."""
    from config import get_status_info
    use_case = None
    company_row = df[df["company"] == lost_company]
    if not company_row.empty:
        use_case = company_row.iloc[0].get("use_case")

    if not use_case:
        return []

    penalty_map = {
        "gone_cold": 2,
        "no_bandwidth": 1,
        "infosec_legal": 3,
        "existing_solution": 4,
        "bad_fit": 5,
        "contact_lost": 0,
        "external_blocker": 0,
    }
    penalty = penalty_map.get(failure_category, 0)
    if penalty == 0:
        return []

    affected = df[
        (df["use_case"] == use_case)
        & (df["company"] != lost_company)
        & (~df["_status_code"].isin(EXCLUDED_STATUSES | SIGNED_STATUS))
    ]

    actions = []
    for _, row in affected.iterrows():
        company = row["company"]
        current = state.get("scores", {}).get(company, {}).get("propagation_penalty", 0)
        state.setdefault("scores", {}).setdefault(company, {})["propagation_penalty"] = current + penalty
        actions.append(f"{company}: +{penalty}pt penalty (same use case: {use_case}, reason: {failure_category})")

    return actions
