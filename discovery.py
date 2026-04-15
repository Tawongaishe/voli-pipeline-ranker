"""Discovery engine — hunting briefs and new company intake parsing."""

import re
from datetime import datetime
from config import (
    CANONICAL_USE_CASES, USE_CASE_SEARCH_TERMS,
    LLM_AVAILABLE, LLM_MODEL, TIER_SCORES,
)
from scoring import compute_use_case_win_rates


def generate_hunting_brief(df, use_case, state=None):
    """Generate a hunting brief for a given use case."""
    uc_df = df[df["use_case"] == use_case]
    if uc_df.empty:
        return None

    # Performance stats
    win_rates, global_rate = compute_use_case_win_rates(df)
    win_rate = win_rates.get(use_case, global_rate)

    signed = uc_df[uc_df["_status_code"] == 1]
    warm = uc_df[uc_df["_status_code"].isin([2, 3.0, 3.1])]
    lost = uc_df[uc_df["_status_code"].isin([7, 9])]
    active = uc_df[~uc_df["_status_code"].isin({1, 7, 9, 11})]

    # Gap assessment
    remaining = len(active)
    if remaining > 5:
        gap = "HEALTHY"
    elif remaining >= 2:
        gap = "LOW"
    else:
        gap = "EMPTY"

    # Common traits
    signed_tiers = signed["tier"].value_counts().to_dict() if not signed.empty else {}
    signed_names = signed["company"].tolist()
    lost_names = lost["company"].tolist()

    # Inbound vs outbound
    inbound_count = 0
    outbound_count = 0
    for _, row in uc_df.iterrows():
        if str(row.get("inbound", "")).strip().upper() in ("Y", "YES", "TRUE", "1"):
            inbound_count += 1
        if str(row.get("outreach", "")).strip().upper() in ("Y", "YES", "TRUE", "1"):
            outbound_count += 1

    # Search terms
    search_terms = USE_CASE_SEARCH_TERMS.get(use_case, [use_case.lower()])

    # All companies in pipeline for exclusion
    all_companies = df["company"].tolist()

    brief = {
        "use_case": use_case,
        "win_rate": win_rate,
        "signed_count": len(signed),
        "warm_count": len(warm),
        "lost_count": len(lost),
        "active_count": remaining,
        "gap_assessment": gap,
        "signed_partners": [{"name": r["company"], "tier": r.get("tier", "")}
                            for _, r in signed.iterrows()],
        "lost_partners": [{"name": r["company"]} for _, r in lost.iterrows()],
        "tier_breakdown": signed_tiers,
        "inbound_count": inbound_count,
        "outbound_count": outbound_count,
        "search_terms": search_terms,
        "all_pipeline_companies": all_companies,
        "generated": datetime.now().strftime("%Y-%m-%d"),
    }

    # LLM-enhanced suggestions
    if LLM_AVAILABLE:
        try:
            suggestions = _llm_hunting_suggestions(brief, df, use_case)
            brief["ai_suggestions"] = suggestions
        except Exception:
            brief["ai_suggestions"] = None
    else:
        brief["ai_suggestions"] = None

    return brief


def format_hunting_brief_text(brief):
    """Format a hunting brief as readable text."""
    uc = brief["use_case"]
    lines = [
        f"HUNTING BRIEF: {uc}",
        "━" * 50,
        f"Performance: {brief['win_rate']:.0%} win rate ({brief['signed_count']} signed, {brief['warm_count']} warm, {brief['lost_count']} lost)",
        f"Pipeline depth: {brief['active_count']} companies still in queue",
        f"Gap assessment: {brief['gap_assessment']}",
        "",
    ]
    if brief["signed_partners"]:
        lines.append("Signed partners:")
        for p in brief["signed_partners"]:
            lines.append(f"  - {p['name']} (Tier {p.get('tier', '?')})")
    if brief["lost_partners"]:
        lines.append("Lost partners:")
        for p in brief["lost_partners"]:
            lines.append(f"  - {p['name']}")
    lines.append("")
    lines.append(f"Inbound: {brief['inbound_count']} | Outbound: {brief['outbound_count']}")
    lines.append("")
    lines.append("WHAT TO LOOK FOR:")
    if brief["signed_partners"]:
        names = ", ".join(p["name"] for p in brief["signed_partners"])
        lines.append(f"  Companies similar to: {names}")
    lines.append("")
    lines.append("Sales Navigator search terms:")
    for term in brief["search_terms"]:
        lines.append(f"  - {term}")

    if brief.get("ai_suggestions"):
        lines.append("")
        lines.append("AI-SUGGESTED COMPANIES:")
        lines.append(brief["ai_suggestions"])

    return "\n".join(lines)


def parse_company_text(text, default_use_case=""):
    """Parse unstructured text into company entries. Returns list of dicts."""
    if LLM_AVAILABLE:
        try:
            return _llm_parse_companies(text)
        except Exception:
            pass

    # Rule-based parsing
    companies = []
    # Split by sentences or newlines
    segments = re.split(r'[.\n]+', text)

    for seg in segments:
        seg = seg.strip()
        if len(seg) < 3:
            continue

        # Try to find company name: capitalized words at start, or before "is a/an"
        name_match = re.match(r'^([A-Z][A-Za-z0-9&\' ]+?)(?:\s+is\s|\s+does\s|\s*[-—]\s|\s+has\s|\s*,)', seg)
        if not name_match:
            # Try: just the first few capitalized words
            name_match = re.match(r'^([A-Z][A-Za-z0-9&\']+(?:\s+[A-Z][A-Za-z0-9&\']+)*)', seg)

        if not name_match:
            continue

        company_name = name_match.group(1).strip()
        if len(company_name) < 2:
            continue

        rest = seg[name_match.end():].strip()

        # Try to match use case
        matched_uc = default_use_case
        rest_lower = rest.lower()
        for uc in CANONICAL_USE_CASES:
            if uc.lower() in rest_lower:
                matched_uc = uc
                break

        # Try to extract employee count for rough TAM
        tam = None
        emp_match = re.search(r'(\d[\d,]+)\s*(?:employees|people|staff)', rest_lower)
        if emp_match:
            try:
                employees = int(emp_match.group(1).replace(",", ""))
                tam = round(employees * 0.01, 1)  # Very rough
            except ValueError:
                pass

        # Tier
        tier = "2"
        if any(w in rest_lower for w in ["large", "leading", "major", "well-known", "enterprise"]):
            tier = "1"
        elif any(w in rest_lower for w in ["small", "startup", "early"]):
            tier = "2"

        companies.append({
            "company": company_name,
            "use_case": matched_uc,
            "tier": tier,
            "tam": tam,
            "notes": rest,
            "status": "No outreach yet",
        })

    return companies


def _llm_parse_companies(text):
    import json as json_mod
    import anthropic
    client = anthropic.Anthropic()
    uc_list = ", ".join(CANONICAL_USE_CASES)
    resp = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": f"""Parse the following unstructured text into a list of companies. For each:
- company_name (string, required)
- canonical_use_case (one of: {uc_list})
- estimated_tier (1 or 2)
- estimated_tam (number in millions, your best guess)
- notes (any other details)

Text: {text}

Respond as JSON array only."""}],
    )
    result = resp.content[0].text.strip()
    # Try to extract JSON
    if "[" in result:
        json_str = result[result.index("["):result.rindex("]") + 1]
        parsed = json_mod.loads(json_str)
        return [
            {
                "company": p.get("company_name", ""),
                "use_case": p.get("canonical_use_case", ""),
                "tier": str(p.get("estimated_tier", "2")),
                "tam": p.get("estimated_tam"),
                "notes": p.get("notes", ""),
                "status": "No outreach yet",
            }
            for p in parsed
        ]
    return []


def _llm_hunting_suggestions(brief, df, use_case):
    import anthropic
    client = anthropic.Anthropic()
    signed = ", ".join(p["name"] for p in brief["signed_partners"]) or "none"
    lost = ", ".join(p["name"] for p in brief["lost_partners"]) or "none"
    exclude = ", ".join(brief["all_pipeline_companies"][:100])

    resp = client.messages.create(
        model=LLM_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": f"""Suggest 5-10 NEW companies for LinkedIn's VOLI API product.
Use case: {use_case}
Signed partners: {signed}
Lost partners: {lost}
Do NOT suggest: {exclude}

For each company, one sentence on why they're a good fit. Focus on companies that would benefit from professional identity verification."""}],
    )
    return resp.content[0].text.strip()
