"""Failure and win classification — keyword-based + optional LLM."""

import os
from config import LLM_AVAILABLE, LLM_MODEL

FAILURE_KEYWORDS = {
    "gone_cold": [
        "stopped responding", "no response", "ghosted", "went cold",
        "gone cold", "haven't heard", "not responding", "silent",
        "multiple followups", "multiple follow-ups", "no reply",
    ],
    "no_bandwidth": [
        "not a priority", "roadmap", "bandwidth", "not now", "revisit",
        "deprioritized", "no bandwidth", "tight from other", "descoped",
        "not in a position", "circle back", "later in the year",
        "FY27", "FY28", "next version", "next year", "H2",
    ],
    "infosec_legal": [
        "infosec", "security", "legal", "compliance", "vendor assessment",
        "pen-test", "penetration", "security assessment", "won't pass",
        "redlines", "contract review",
    ],
    "existing_solution": [
        "already using", "using Persona", "building in-house", "built their own",
        "competitor", "alternative", "existing vendor", "incumbent",
    ],
    "bad_fit": [
        "not interested", "don't see value", "doesn't align", "not relevant",
        "not a fit", "wrong", "declined", "no interest",
    ],
    "contact_lost": [
        "left the company", "reorg", "departed", "no longer at", "VP left",
        "champion left", "team dissolved", "replacement",
    ],
    "external_blocker": [
        "LTS", "broader engagement", "negotiate broader", "internal politics",
        "budget freeze", "blocked until", "acquired",
    ],
}

WIN_KEYWORDS = {
    "quick_close": ["short sales cycle", "fast", "quick", "urgent", "acute"],
    "strong_fit": ["perfect fit", "exactly what", "aligned", "solves"],
    "champion_driven": ["champion", "evangelist", "internal advocate"],
    "social_proof": ["saw that", "like Zoom", "like Adobe", "other partners"],
    "inbound": ["inbound", "they came to us", "they reached out"],
}

FAILURE_LABELS = {
    "gone_cold": "Gone cold — stopped responding",
    "no_bandwidth": "No bandwidth — can't prioritize now",
    "infosec_legal": "InfoSec/Legal — blocked by security or compliance",
    "existing_solution": "Existing solution — using competitor or building in-house",
    "bad_fit": "Bad fit — use case doesn't align",
    "contact_lost": "Contact lost — champion left or reorg",
    "external_blocker": "External blocker — politics, budget freeze, etc.",
}

WIN_LABELS = {
    "quick_close": "Quick close — short sales cycle, strong urgency",
    "strong_fit": "Strong fit — use case aligned perfectly",
    "champion_driven": "Champion driven — strong internal advocate",
    "social_proof": "Social proof — influenced by other signed partners",
    "inbound": "Inbound — they came to us",
}


def _keyword_classify(text, keyword_dict):
    """Match text against keyword categories, return (category, hit_count) list."""
    text_lower = text.lower()
    matches = []
    for category, keywords in keyword_dict.items():
        hits = sum(1 for kw in keywords if kw.lower() in text_lower)
        if hits > 0:
            matches.append((category, hits))
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def classify_failure(combined_text, company_name="", use_case="", notes_dict=None):
    """Classify failure reason. Returns (category, explanation, confidence)."""
    if LLM_AVAILABLE:
        try:
            return _llm_classify_failure(combined_text, company_name, use_case, notes_dict or {})
        except Exception:
            pass  # Fall through to keyword mode

    matches = _keyword_classify(combined_text, FAILURE_KEYWORDS)
    if len(matches) == 1:
        return matches[0][0], FAILURE_LABELS[matches[0][0]], "high"
    elif len(matches) > 1:
        return matches[0][0], FAILURE_LABELS[matches[0][0]], "medium"
    else:
        return "gone_cold", FAILURE_LABELS["gone_cold"], "low"


def classify_win(combined_text, company_name="", use_case=""):
    """Classify win reason. Returns (category, explanation, confidence)."""
    if LLM_AVAILABLE:
        try:
            return _llm_classify_win(combined_text, company_name, use_case)
        except Exception:
            pass

    matches = _keyword_classify(combined_text, WIN_KEYWORDS)
    if matches:
        return matches[0][0], WIN_LABELS[matches[0][0]], "medium"
    return "strong_fit", WIN_LABELS["strong_fit"], "low"


def _llm_classify_failure(text, company_name, use_case, notes_dict):
    import anthropic
    client = anthropic.Anthropic()
    prompt = f"""You are classifying why a business development conversation did not succeed.
Given the following notes about a conversation with a company, classify the
failure reason into exactly one of these categories:

- gone_cold: Stopped responding, no clear reason
- no_bandwidth: Interested but can't prioritize (roadmap full, timing)
- infosec_legal: Blocked by security, legal, compliance, or vendor review
- existing_solution: Already using a competitor or building in-house
- bad_fit: Use case doesn't align, don't see value
- contact_lost: Champion left, reorg, team change
- external_blocker: Broader relationship issues, politics, budget freeze

Company: {company_name}
Use case: {use_case}
Notes: {text}

Respond with ONLY the category name and a one-sentence explanation."""

    resp = client.messages.create(
        model=LLM_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    result = resp.content[0].text.strip()
    for cat in FAILURE_KEYWORDS:
        if cat in result.lower():
            explanation = result.split("\n")[0] if "\n" in result else result
            return cat, explanation, "high"
    return "gone_cold", result, "medium"


def _llm_classify_win(text, company_name, use_case):
    import anthropic
    client = anthropic.Anthropic()
    prompt = f"""Classify this win into one category:
- quick_close, strong_fit, champion_driven, social_proof, inbound

Company: {company_name}, Use case: {use_case}
Notes: {text}

Respond with ONLY the category name and one sentence."""

    resp = client.messages.create(
        model=LLM_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    result = resp.content[0].text.strip()
    for cat in WIN_KEYWORDS:
        if cat in result.lower():
            return cat, result, "high"
    return "strong_fit", result, "medium"
