# VOLI Pipeline Ranker — Build Specification

## Overview

Build an interactive pipeline management tool for LinkedIn's "Verified on LinkedIn" (VOLI) partnerships program. The tool ranks prospective partner companies using a composite scoring algorithm that adapts based on conversation outcomes, suggests where to find new partners, and generates follow-up reminders for the BD team.

**Users**: A PM, a BD lead, and product managers on the team (3-5 people).
**Deployment**: Streamlit web app, initially run locally, shareable via URL.
**Data source**: A Google Sheet containing the current pipeline (see Data Model section).

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      STREAMLIT WEB APP                        │
├───────────┬───────────────┬──────────────┬───────────────────┤
│ LOG       │ STACK RANK    │ REMINDERS    │ DISCOVERY         │
│ OUTCOME   │               │              │                   │
│           │ Score-sorted  │ This week    │ Hunting briefs    │
│ Company + │ pipeline with │ Overdue      │ per use case      │
│ status +  │ scores,       │ Coming up    │                   │
│ free-text │ color-coded   │ Parked       │ + New company     │
│ reason    │ by use case   │              │   intake (paste)  │
│           │ + filters     │ Smart nudges │                   │
├───────────┴───────────────┴──────────────┴───────────────────┤
│  SCORING ENGINE  │  REMINDER ENGINE  │  DISCOVERY ENGINE     │
│  Composite score │  Cadence rules    │  Hunting briefs       │
│  + propagation   │  + date parsing   │  (data-driven or      │
│  + classify      │  + social proof   │   LLM-enhanced)       │
│    failure reason│  + nudges         │  + batch paste intake  │
├──────────────────┴───────────────────┴───────────────────────┤
│  Google Sheets API (read/write to live pipeline sheet)        │
│  Local JSON state (score history, reminders, event log)       │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Source: Google Sheet

**Sheet ID**: `1NeBFnOax3GwMQXP8MFoZbA7q5rUfZ-jmobLH1S_8Ewo`

The sheet has many columns. The system should read ALL columns but only use the following for scoring and display. Preserve all other columns as passthrough data.

#### Columns used for scoring

| Column | Type | Description |
|---|---|---|
| `Unique_ID_Company` | string | Company name (primary key) |
| `Status_dropdown` | string | Pipeline stage (see Status Mapping below) |
| `Tier` | int or string | 1, 2, or "ATS" |
| `Canonical use case` | string | Standardized use case category |
| `Use case status` | string | Prioritize / Deprioritize / Inbound only / To be categorized |
| `Est. TAM (M)` | float | Estimated total addressable market in millions |
| `Outreach Y/N` | Y/N | Whether outreach has been attempted |
| `Responded?` | string | Warm / Cold / Inbound / empty |
| `Meeting Y/N` | Y/N | Whether a meeting has occurred |
| `Interested` | Y/N | Whether they expressed interest |
| `Reviewing contract offline` | Y/N | Whether they're reviewing a contract |
| `Signed` | Y/N | Whether they've signed |
| `Want exec intro?` | Y/N | Whether they want an exec introduction |
| `Deprioritize company?` | boolean/TRUE | Whether currently deprioritized |
| `Status notes` | string | Free-text notes on current status |
| `Status written` | date string | When the status was last updated |
| `Last / next touch` | string | Date/description of last or next contact |
| `Next steps` | string | What happens next |
| `Partner notes` | string | What the partner said about their status |
| `Our notes` | string | Internal notes |
| `TG Owner` | string | Who on the team owns this relationship |

#### Columns used for display only (not scoring)

| Column | Description |
|---|---|
| `Mickey mapping (rough)` | Original use case mapping |
| `Simplified categories` | Simplified category |
| `Outreach wave` | When outreach was planned |
| `Outreach stage` | Outreach timing |
| `Outreach type` | Type of outreach |
| `Intended use` | What the partner would use VOLI for |
| `Recommended Intro` | Who to ask for an introduction |
| `CPO` | Company's CPO name |
| `CEO` | Company's CEO name |

### Status Mapping

These are the pipeline stages, ordered from most to least advanced:

| Status String | Numeric Code | Score Weight |
|---|---|---|
| `1 - Signed` | 1 | 100 |
| `2 - Intent to sign` | 2 | 85 |
| `3.0 - Warm / engaged (more likely)` | 3.0 | 70 |
| `3.1 - Warm / engaged` | 3.1 | 55 |
| `3.2 - Cool-ish` | 3.2 | 40 |
| `4 - Interesting but not priority` | 4 | 25 |
| `5 - Responded, no next steps yet` | 5 | 15 |
| `6 - Haven't responded to outbound` | 6 | 5 |
| `7 - Lost` | 7 | 0 |
| `8 - Other` | 8 | 10 |
| `9 - We have declined to move forward` | 9 | 0 |
| `No outreach yet` | 10 | 8 |
| `Cut from pipeline` | 11 | 0 |

### Canonical Use Cases

These are the standardized use case categories. The system must recognize all of them:

```
- Content provenance
- Professional collaboration
- Expert networks
- Professional reviews
- Freemium abuse for subscriptions (professional)
- Freemium abuse for subscriptions (personal)
- Freemium abuse for subscriptions (news)
- P2P digital marketplaces
- Identity in Professional Events
- Job Scams (hirer/seeker)
- Gig platforms
- Chargeback fraud (high cart value)
- Other
```

New use cases can be added by the user at any time.

### Local State (JSON)

The system maintains a local JSON file (`state.json`) that stores:

```json
{
  "scores": {
    "CompanyName": {
      "composite_score": 78.5,
      "use_case_win_rate": 0.75,
      "stage_score": 70,
      "tam_score": 8.2,
      "engagement_score": 11,
      "tier_score": 10,
      "decay_penalty": 0,
      "propagation_penalty": 0,
      "last_computed": "2026-04-15"
    }
  },
  "event_log": [
    {
      "timestamp": "2026-04-15T10:30:00",
      "company": "Databricks",
      "old_status": "3.0 - Warm / engaged (more likely)",
      "new_status": "1 - Signed",
      "reason_text": "They had acute freemium abuse problem, short sales cycle",
      "reason_category": "N/A (win)",
      "propagation_actions": ["Boosted Freemium abuse (professional) win rate from 29% to 37%"]
    }
  ],
  "reminders": {
    "CompanyName": {
      "next_followup": "2026-04-18",
      "cadence_days": 7,
      "parked_until": null,
      "park_reason": null,
      "followup_count": 3,
      "suggested_action": "Check in on contract status"
    }
  },
  "hunting_briefs": {
    "Expert networks": {
      "generated": "2026-04-15",
      "brief": "...",
      "suggested_companies": ["Guidepoint", "Dialectica"]
    }
  },
  "added_companies": [
    {
      "company": "Guidepoint",
      "added_date": "2026-04-15",
      "source": "discovery",
      "initial_score": 65.2
    }
  ]
}
```

---

## Scoring Engine

### Composite Score Formula

```
SCORE = (use_case_win_rate × 35)
      + (stage_momentum × 25)
      + (tam_score × 15)
      + (engagement_signals × 15)
      + (tier_bonus × 10)
      - decay_penalty
      - propagation_penalty
```

**Maximum possible score**: 100 (before penalties)
**Companies with status "1 - Signed" are excluded from the active rank** — they appear in a separate "Signed Partners" section for reference.
**Companies with status "9 - We have declined" or "Cut from pipeline" are excluded entirely.**

### Component Details

#### 1. Use Case Win Rate (weight: 35)

Calculate for each canonical use case:

```
win_rate = (signed + intent_to_sign + warm_more_likely) / 
           (signed + intent_to_sign + warm_more_likely + warm + cool + lost)
```

- Only count companies that have had meaningful engagement (exclude "No outreach yet" and "Haven't responded to outbound" from the denominator)
- If a use case has fewer than 3 data points, blend with the global average win rate (Bayesian smoothing): `blended = (n × use_case_rate + 3 × global_rate) / (n + 3)`
- Multiply the win rate (0.0 to 1.0) by 35 to get the component score

#### 2. Stage Momentum (weight: 25)

Use the stage score from the Status Mapping table (0-100), normalized to 0-25.

```
stage_momentum = (stage_score / 100) × 25
```

**Staleness decay**: If `Status written` date is available and the status hasn't changed in:
- 30+ days: reduce by 10%
- 60+ days: reduce by 25%
- 90+ days: reduce by 40%

Do NOT apply staleness decay to:
- Signed companies
- Companies explicitly parked ("said FY28", "circle back in Q2", etc.)
- Companies in "No outreach yet" (haven't started yet, not stale)

#### 3. TAM Score (weight: 15)

Use log scale to prevent mega-companies from dominating:

```python
import math

def tam_score(tam_millions):
    if tam_millions is None or tam_millions <= 0:
        return 5  # default middle score for unknown TAM
    # log10 scale: $0.1M = 3.75, $1M = 7.5, $10M = 11.25, $100M = 15
    return min(15, max(0, math.log10(tam_millions * 10) * 3.75))
```

#### 4. Engagement Signals (weight: 15)

Sum of binary signals, capped at 15:

| Signal | Points |
|---|---|
| Outreach Y/N = Y | +1 |
| Responded = Warm or Inbound | +3 |
| Responded = Cold | +1 |
| Meeting Y/N = Y | +3 |
| Interested = Y | +3 |
| Reviewing contract = Y | +4 |
| Signed = Y | +5 |
| Want exec intro = Y | -1 (indicates friction) |
| Deprioritize = TRUE | -5 |

Cap at 15, floor at 0.

#### 5. Tier Bonus (weight: 10)

| Tier | Score |
|---|---|
| 1 | 10 |
| 2 | 5 |
| ATS | 7 |
| Unknown/empty | 3 |

#### 6. Decay Penalty

For companies in status 6 ("Haven't responded to outbound"):

```python
def decay_penalty(days_since_first_outreach):
    if days_since_first_outreach <= 30:
        return 0
    elif days_since_first_outreach <= 60:
        return 3
    elif days_since_first_outreach <= 90:
        return 6
    else:
        return 10
```

For companies in status 5 ("Responded, no next steps"):
- Same formula but starting at 14 days instead of 30

#### 7. Propagation Penalty

Applied when a company in the same canonical use case is lost. The penalty depends on the auto-classified failure reason (see Failure Classification section):

| Failure Category | Penalty to same-use-case companies | Extra targeting |
|---|---|---|
| Gone cold | 2 points | Companies also in status 5-6 |
| No bandwidth | 1 point | Companies with similar TAM range |
| InfoSec/Legal | 3 points | Tier 2 companies (smaller = more likely to fail infosec) |
| Existing solution | 4 points | Companies in same vertical |
| Bad fit | 5 points | All companies in same canonical use case |
| Contact lost | 0 points | Company-specific, no propagation |
| External blocker | 0 points | LinkedIn-specific, no propagation |

Propagation penalties decay by 1 point per month (they shouldn't haunt companies forever).

---

## Failure Classification

When a user logs an outcome, the system classifies the failure reason. This works in two modes depending on whether an LLM API key is configured.

**IMPORTANT: The LLM API key (ANTHROPIC_API_KEY) is OPTIONAL. The entire app must work fully without it. All LLM-powered features have a rule-based fallback. Check for the key at runtime and gracefully degrade.**

### Failure Categories

```
1. gone_cold        — Stopped responding, no clear reason given
2. no_bandwidth     — Interested but can't prioritize now (roadmap full, not this quarter)
3. infosec_legal    — Blocked by security review, legal review, compliance, or vendor assessment
4. existing_solution — Already using a competitor or building in-house
5. bad_fit          — Use case doesn't align, don't see the value, wrong product
6. contact_lost     — Champion left the company, reorg, team dissolved
7. external_blocker — Broader LinkedIn relationship issue, internal politics, budget freeze
```

### Win Categories

```
- quick_close: Short sales cycle, strong urgency
- strong_fit: Use case aligned perfectly with their needs
- champion_driven: Had a strong internal champion
- social_proof: Influenced by other signed partners
- inbound: They came to us (low effort to close)
```

### Mode 1: Keyword-Based Classification (default, no API needed)

Use keyword matching on the combined text of status notes, partner notes, and our notes:

```python
FAILURE_KEYWORDS = {
    "gone_cold": [
        "stopped responding", "no response", "ghosted", "went cold",
        "gone cold", "haven't heard", "not responding", "silent",
        "multiple followups", "multiple follow-ups", "no reply"
    ],
    "no_bandwidth": [
        "not a priority", "roadmap", "bandwidth", "not now", "revisit",
        "deprioritized", "no bandwidth", "tight from other", "descoped",
        "not in a position", "circle back", "later in the year",
        "FY27", "FY28", "next version", "next year", "H2"
    ],
    "infosec_legal": [
        "infosec", "security", "legal", "compliance", "vendor assessment",
        "pen-test", "penetration", "security assessment", "won't pass",
        "redlines", "contract review"
    ],
    "existing_solution": [
        "already using", "using Persona", "building in-house", "built their own",
        "competitor", "alternative", "existing vendor", "incumbent"
    ],
    "bad_fit": [
        "not interested", "don't see value", "doesn't align", "not relevant",
        "not a fit", "wrong", "declined", "no interest"
    ],
    "contact_lost": [
        "left the company", "reorg", "departed", "no longer at", "VP left",
        "champion left", "team dissolved", "replacement"
    ],
    "external_blocker": [
        "LTS", "broader engagement", "negotiate broader", "internal politics",
        "budget freeze", "blocked until", "acquired"
    ]
}

WIN_KEYWORDS = {
    "quick_close": ["short sales cycle", "fast", "quick", "urgent", "acute"],
    "strong_fit": ["perfect fit", "exactly what", "aligned", "solves"],
    "champion_driven": ["champion", "evangelist", "internal advocate"],
    "social_proof": ["saw that", "like Zoom", "like Adobe", "other partners"],
    "inbound": ["inbound", "they came to us", "they reached out"]
}
```

Match logic:
1. Combine `status_notes + partner_notes + our_notes + user's free-text input` into lowercase text
2. Check each category's keywords against the text
3. If exactly one category matches, auto-select it
4. If multiple match, pick the one with the most keyword hits
5. If zero match, default to `gone_cold` for Lost status, or show a dropdown for the user to pick manually

After auto-classification, **always show the user the result and let them override** via a dropdown before confirming.

### Mode 2: LLM-Enhanced Classification (when API key is available)

If `ANTHROPIC_API_KEY` is set in the environment, use Claude API for smarter classification instead of keywords. Send this prompt:

```
You are classifying why a business development conversation did not succeed.
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
Use case: {canonical_use_case}
Status notes: {status_notes}
Partner notes: {partner_notes}
Our notes: {our_notes}

Respond with ONLY the category name (e.g., "no_bandwidth") and a one-sentence 
explanation of why you chose it.
```

Use the same override-able dropdown UI regardless of mode — the LLM just provides a better initial guess.

---

## Reminder Engine

### Cadence Rules

Each company gets an auto-generated follow-up cadence based on status:

| Status | Default Cadence | Max Attempts Before Flag |
|---|---|---|
| 2 - Intent to sign | 5 days | No limit (keep pushing) |
| 3.0 - Warm (more likely) | 7 days | No limit |
| 3.1 - Warm / engaged | 14 days | No limit |
| 3.2 - Cool-ish | 21 days | 4, then suggest deprioritize |
| 4 - Interesting not priority | 30 days | 3, then suggest deprioritize |
| 5 - Responded, no next steps | 21 days | 3, then suggest deprioritize |
| 6 - No response to outbound | 14d, 14d, 14d, 30d, 30d | 5, then auto-flag |
| 7 - Lost | 90-day re-engagement check | 1 attempt |
| No outreach yet | Flag for outreach planning | N/A |

### Smart Overrides

The system should parse `Partner notes`, `Status notes`, `Next steps`, and `Our notes` for date references and timing language. This works in two modes:

#### Mode 1: Regex-Based Date Parsing (default, no API needed)

Use regex and keyword patterns to extract dates and timing signals:

```python
import re
from dateutil import parser as dateparser

DATE_PATTERNS = [
    # Explicit dates: "3/19", "March 19", "2026-04-01", "April 7"
    r'\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b',
    r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}(?:,?\s*\d{4})?)\b',
    r'\b(\d{4}-\d{2}-\d{2})\b',
]

PARK_PATTERNS = {
    # "FY28" → July 2027 (LinkedIn FY starts Feb)
    r'FY(\d{2})': lambda m: f"20{int(m.group(1))-1}-07-01",
    # "Q2" / "Q3 2026" → start of that quarter
    r'Q([1-4])(?:\s*(?:20)?(\d{2}))?': lambda m: quarter_to_date(m),
    # "later in the year" / "end of year" → 6 months out
    r'later in the year|end of (?:the )?year': lambda m: six_months_from_now(),
    # "next year" / "2027" → Jan of next year
    r'next year|20(\d{2})': lambda m: f"20{m.group(1)}-01-01" if m.group(1) else next_jan(),
    # "not until July" → that month
    r'not until (\w+)': lambda m: parse_month(m.group(1)),
}

NOT_NOW_KEYWORDS = [
    "not a priority", "not now", "revisit", "circle back", 
    "not in a position", "timing is better", "descoped"
]
```

Logic:
1. Combine all notes fields into one text block
2. Search for explicit dates → these become `next_followup` dates
3. Search for park patterns → these become `park_until` dates
4. Search for "not now" keywords without a date → set a 60-day reminder
5. If no dates found, fall back to default cadence for the company's status

#### Mode 2: LLM-Enhanced Date Parsing (when API key is available)

If `ANTHROPIC_API_KEY` is set, use Claude for more nuanced extraction:

```
Extract any follow-up dates, deadlines, or timing references from these notes.
Return as JSON: {"next_date": "YYYY-MM-DD", "park_until": "YYYY-MM-DD" or null, 
"confidence": "high/medium/low", "source_text": "the exact phrase you found"}

Notes: {combined_notes}
```

Specific timing signals to handle (in either mode):

- **Explicit dates**: "follow up on 3/19", "meeting scheduled for April 7" → set reminder for that date
- **Relative timing**: "circle back in Q2" → set reminder for start of Q2
- **Long deferrals**: "FY28 item", "not until 2027" → park with a long-horizon reminder, remove from active cadence
- **"Not now" language**: "not a priority right now", "revisit when timing is better" → set 60-day reminder + flag for re-engagement with social proof

### Smart Nudges

Generate contextual suggestions based on pipeline state:

- **Social proof nudge**: When a company signs or advances, suggest sharing that win with stalled companies in the same use case. Example: "Economist moved to Warm → share this with CNN and WSJ as social proof"
- **Use case gap alert**: When a use case has high win rate but few remaining prospects. Example: "Expert networks has 100% win rate but 0 companies left in queue → time to prospect"
- **Staleness alert**: When multiple companies in the same use case have gone stale. Example: "5 Professional Collaboration companies haven't been touched in 30+ days"
- **Batch outreach suggestion**: When multiple no-outreach companies share a use case. Example: "6 camera companies (Canon, Leica, Nikon, Sony, Fujifilm, Panasonic) all in Content Provenance with no outreach → consider a batch campaign"

### Reminder Display

Group reminders into:

1. **OVERDUE** — Past the follow-up date, sorted by how overdue (most overdue first)
2. **THIS WEEK** — Due within the next 7 days
3. **NEXT TWO WEEKS** — Due in 8-14 days
4. **PARKED** — Companies with a `park_until` date, showing when they'll reactivate
5. **NEEDS DECISION** — Companies that have hit their max attempts and need to be deprioritized or escalated

Each reminder should show:
- Company name
- Current status
- Days since last touch
- A one-line suggested action (generated from context)
- TG Owner (who's responsible)

---

## Discovery Engine

### Hunting Briefs

Generate one hunting brief per canonical use case. A hunting brief answers:

1. **How is this use case performing?** — Win rate, # signed, # warm, # lost
2. **What's the gap?** — How many companies remain in the queue? Are there enough?
3. **What pattern do wins share?** — Company size, specific sub-vertical, inbound vs outbound
4. **What to look for** — Characteristics of ideal new targets for this use case
5. **Suggested companies** — 5-10 specific company names to research (LLM-generated if available, otherwise a prompt for manual research)

#### Mode 1: Data-Driven Hunting Briefs (default, no API needed)

Generate briefs purely from pipeline data. For each canonical use case, compute and display:

```
HUNTING BRIEF: {use_case}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Performance: {win_rate}% win rate ({signed} signed, {warm} warm, {lost} lost)
Pipeline depth: {remaining} companies still in queue
Gap assessment: {"HEALTHY" if remaining > 5, "LOW" if 2-5, "EMPTY" if 0-1}

Signed partners: {list with company names and TAM}
Lost partners: {list with company names and failure categories}

Common traits of wins:
  - Avg TAM: ${avg_tam}M
  - Tiers: {tier breakdown}
  - Inbound vs outbound: {breakdown}
  
Common traits of losses:
  - Failure reasons: {breakdown of categories}
  - Avg TAM: ${avg_tam}M

WHAT TO LOOK FOR:
  Companies in the {use_case} space that are similar to {signed_list}.
  Prioritize: {tier} companies, TAM ~${avg_tam}M.
  Avoid: {common failure traits}.
  
  Search suggestions for Sales Navigator:
  - Industry keywords: {derived from use case}
  - Company size: {derived from successful partner sizes}
  - Exclude: {all companies already in pipeline}
```

Include Sales Navigator search keyword suggestions per use case:

```python
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
}
```

#### Mode 2: LLM-Enhanced Hunting Briefs (when API key is available)

If `ANTHROPIC_API_KEY` is set, enrich the data-driven brief with AI-generated company suggestions:

```
You are helping a business development team find new partner companies for 
LinkedIn's "Verified on LinkedIn" (VOLI) API product.

Use case category: {canonical_use_case}

Here are the companies we've already engaged in this category:
{list of companies with their status, TAM, and notes}

Signed partners in this category: {signed_list}
Lost partners in this category: {lost_list_with_reasons}

Based on the pattern of which companies signed vs. which were lost:
1. What characteristics do the successful partners share?
2. What characteristics do the lost partners share?
3. Suggest 5-10 NEW companies (not already in our pipeline) that match 
   the successful pattern. For each, explain in one sentence why they're 
   a good fit.
4. Are there adjacent use cases or verticals we should explore based on 
   these patterns?

Focus on companies that:
- Are likely to have the problem this use case solves
- Are mid-to-large enough to pass LinkedIn's InfoSec requirements
- Have a product surface where VOLI verification would be visible to users

Do NOT suggest companies that are: {list of all companies already in pipeline}
```

### Refresh schedule

- Hunting briefs should be regenerated when:
  - A new outcome is logged (win rate changed)
  - User explicitly requests a refresh
  - It's been 14+ days since last generation

### New Company Intake

The user will paste unstructured text describing companies they found. This could come from voice typing, notes, or Sales Navigator research. This works in two modes:

**Input example (voice-typed):**
```
"Guidepoint is an expert network similar to AlphaSights, probably about 
500 employees. Dialectica is in the same space, based in London, slightly 
smaller. NewtonX does AI-powered expert matching, probably a good fit. 
Capvision is another one, big in Asia Pacific."
```

#### Mode 1: Regex-Based Parsing (default, no API needed)

Parse the pasted text using pattern matching:

```python
def parse_company_text(text, canonical_use_cases):
    """
    Split text into company chunks and extract structured data.
    
    Strategy:
    1. Split on company-name-like patterns (capitalized words followed 
       by "is a", "is an", "does", "—", etc.)
    2. For each chunk, try to extract:
       - company_name: The capitalized word(s) at the start
       - use_case: Match against canonical_use_case_list using keyword overlap
       - tier: If "small" or employee count < 200 → Tier 2; 
               if "large" or well-known → Tier 1; default Tier 2
       - tam: If a number + "employees" is found, rough estimate:
              employees * 0.01 = TAM in millions (very rough)
       - notes: Everything else in the chunk
    """
```

Parsing rules:
1. Split text by sentences or line breaks
2. Look for company names: capitalized words at the start of segments, or words before "is a/an", "does", "—"
3. Match use case by checking if any canonical use case keywords appear near the company name
4. If use case can't be determined, leave it blank for user to fill in
5. Default tier to 2 unless the text says "large", "leading", "major", etc.
6. TAM defaults to blank for user to fill in

**Show the parsed result in an editable Streamlit data_editor table** so the user can correct any parsing errors before confirming.

#### Mode 2: LLM-Enhanced Parsing (when API key is available)

If `ANTHROPIC_API_KEY` is set, use Claude for much better parsing:

```
Parse the following unstructured text into a list of companies. For each 
company, extract:
- company_name (string, required)
- canonical_use_case (string, must be one of: {canonical_use_case_list})
- estimated_tier (1 or 2, based on company size — Tier 1 = large/well-known, Tier 2 = mid-market)
- estimated_tam (number in millions, your best guess based on context)
- notes (any other details mentioned)

If information is missing, make reasonable inferences but flag low confidence.

Text: {user_input}

Respond as JSON array.
```

#### After parsing (both modes):

1. Show the user the parsed results in an **editable table** (Streamlit `st.data_editor`)
2. User corrects any errors, fills in missing fields (use case, tier, TAM)
3. On "Confirm & Add":
   - Add companies to the pipeline with status "No outreach yet"
   - Compute initial scores (they inherit the use case win rate)
   - Optionally write back to Google Sheet
4. Show a summary: "Added 4 companies. Guidepoint ranked #12, Dialectica ranked #18..."

---

## Streamlit UI Specification

### Page Layout

Use Streamlit's sidebar for navigation between four main views:

### View 1: Stack Rank (default/home)

**Top bar**: 
- Filter by: Canonical use case (multiselect), Status (multiselect), Tier (multiselect), TG Owner (multiselect)
- Sort by: Composite score (default), TAM, Status, Use case
- Toggle: Show/hide signed partners, Show/hide deprioritized

**Main content**:
- Table with columns:
  - Rank (#)
  - Company name
  - Composite Score (with a small bar chart or color gradient)
  - Status
  - Canonical Use Case (color-coded badge)
  - Tier
  - Est. TAM
  - Days Since Last Touch
  - Next Reminder Date
  - TG Owner
- Each row is expandable to show: Status notes, Partner notes, Our notes, Score breakdown (what contributed to the score)
- Color coding:
  - Green: Score > 70
  - Yellow: Score 40-70
  - Orange: Score 20-40
  - Red: Score < 20
  - Gray: Deprioritized or Lost

**Side panel** (below filters):
- Use Case Win Rate summary (small bar chart showing each use case's win rate)
- Pipeline health metrics: Total active, This month's movements, Use cases with gaps

### View 2: Log Outcome

**Form fields:**
1. **Company** — Searchable dropdown of all companies in pipeline
2. **New status** — Dropdown of all status options
3. **What happened?** — Large text area (free-text, voice-typing friendly)
4. **Date of interaction** — Date picker, defaults to today

**On submit:**
1. Show: "Here's what will happen" preview:
   - Status change: X → Y
   - Auto-classified reason: {category} — {explanation}
   - Score impact on this company: old → new
   - Propagation effects: "This will boost/reduce scores for N companies in {use case}"
2. User confirms
3. System updates state, recalculates scores, updates reminders
4. Optionally writes status update back to Google Sheet

### View 3: Reminders

**Layout:**

Section 1: **OVERDUE** (red header)
- List of companies past their follow-up date
- Each shows: company, status, days overdue, suggested action, TG owner

Section 2: **THIS WEEK** (yellow header)
- Companies due for follow-up in next 7 days

Section 3: **COMING UP** (blue header)
- Companies due in 8-21 days

Section 4: **PARKED** (gray header)
- Companies with long-horizon reminders
- Shows: company, park reason, reactivation date

Section 5: **NEEDS DECISION** (orange header)
- Companies that have exceeded max follow-up attempts
- Options: Deprioritize / Escalate / Reset cadence

**Interaction**: Each reminder has action buttons:
- "Mark as done" (logs a touch, resets the cadence timer)
- "Snooze 7 days"
- "Park until [date]"
- "Log outcome" (jumps to View 2 with company pre-selected)

### View 4: Discovery

**Top section: Hunting Briefs**
- One expandable card per canonical use case
- Card shows: win rate, # in pipeline, gap assessment, suggested companies
- "Regenerate" button per card

**Bottom section: Add New Companies**
- Large text area: "Paste your research notes here (voice typing welcome)"
- "Parse" button
- After parsing: editable table showing extracted companies
- "Confirm & Add" button
- After adding: show where new companies landed in the stack rank

---

## Tech Stack

### Required packages

```
streamlit>=1.30.0
pandas>=2.0.0
gspread>=5.12.0
google-auth>=2.25.0
google-auth-oauthlib>=1.2.0
plotly>=5.18.0
python-dateutil>=2.8.0

# Optional — only needed if using LLM-enhanced features
# anthropic>=0.40.0
```

The `anthropic` package should be an optional dependency. Import it with a try/except and set a flag:

```python
try:
    import anthropic
    LLM_AVAILABLE = bool(os.getenv("ANTHROPIC_API_KEY"))
except ImportError:
    LLM_AVAILABLE = False
```

### File Structure

```
voli-pipeline-ranker/
├── SPEC.md                  # This file
├── requirements.txt         # Python dependencies
├── .env.example             # Template for environment variables
├── app.py                   # Streamlit entry point
├── config.py                # Constants, use case lists, status mappings
├── scoring.py               # Scoring engine (composite score calculation)
├── reminders.py             # Reminder engine (cadence, parsing, nudges)
├── discovery.py             # Discovery engine (hunting briefs, company parsing — rule-based + optional LLM)
├── classifier.py            # Failure/win classification (keyword-based + optional LLM)
├── sheets.py                # Google Sheets API integration (read/write)
├── state.py                 # Local state management (JSON read/write)
├── ui/
│   ├── stack_rank.py        # View 1: Stack rank table + filters
│   ├── log_outcome.py       # View 2: Outcome logging form
│   ├── reminders_view.py    # View 3: Reminders dashboard
│   └── discovery_view.py    # View 4: Discovery + new company intake
├── state.json               # Local state (auto-generated, gitignored)
└── credentials/
    └── .gitkeep             # Google service account key goes here
```

### Environment Variables

```
# Required
GOOGLE_SHEETS_ID=1NeBFnOax3GwMQXP8MFoZbA7q5rUfZ-jmobLH1S_8Ewo
GOOGLE_CREDENTIALS_PATH=./credentials/service_account.json

# Optional — enables LLM-enhanced features (classification, parsing, discovery)
# The entire app works without this. See "LLM API Integration" section.
# ANTHROPIC_API_KEY=sk-ant-...
```

---

## Google Sheets Setup

### Required steps (one-time)

1. Create a Google Cloud project (or use existing)
2. Enable Google Sheets API
3. Create a service account and download the JSON key
4. Share the Google Sheet with the service account email (Editor access)
5. Place the JSON key in `credentials/service_account.json`

### Read/Write Behavior

- **On startup**: Read all data from the sheet into a pandas DataFrame
- **On score recalculation**: Update local state only (don't write scores to sheet)
- **On outcome logging**: Optionally write the new status back to the sheet (user confirms first)
- **On new company added**: Optionally write a new row to the sheet (user confirms first)
- **Sync button**: Manual "Refresh from Sheet" button to pull latest data

---

## LLM API Integration (OPTIONAL)

**The LLM API is entirely optional.** The app must be fully functional without it. When no API key is set, all features use rule-based/keyword fallbacks as described in their respective sections.

When `ANTHROPIC_API_KEY` is set in the environment, the following features are enhanced:

### Model

Use `claude-sonnet-4-6` for all API calls (good balance of speed and quality for classification and generation tasks).

### LLM-enhanced features (all have non-LLM fallbacks)

| Feature | Without API | With API |
|---|---|---|
| Failure classification | Keyword matching → user confirms/overrides via dropdown | Claude classifies → user confirms/overrides via dropdown |
| Win classification | Keyword matching → user confirms/overrides via dropdown | Claude classifies → user confirms/overrides via dropdown |
| Date parsing from notes | Regex patterns for dates, FY refs, quarter refs | Claude extracts dates with context understanding |
| Hunting brief company suggestions | Data-driven stats + Sales Navigator search terms | Data-driven stats + AI-generated company suggestions |
| New company intake parsing | Regex-based text splitting + keyword matching | Claude parses unstructured/voice-typed text into structured data |
| Reminder suggested actions | Template-based ("Follow up on contract status") | Claude generates context-aware action suggestions |

### Calls made (when API is available)

1. **Failure classification** — On each outcome log (~200 tokens in, ~50 tokens out)
2. **Win classification** — On each positive outcome (~200 tokens in, ~50 tokens out)
3. **Date parsing** — On each company's notes for reminder scheduling (~300 tokens in, ~100 tokens out)
4. **Hunting brief generation** — On demand, per use case (~1000 tokens in, ~500 tokens out)
5. **New company parsing** — On each batch paste (~500 tokens in, ~300 tokens out)
6. **Suggested action generation** — For each reminder (~200 tokens in, ~50 tokens out)

### Caching

- Cache hunting briefs for 14 days (or until a new outcome is logged)
- Cache date parsing results in state.json (only re-parse when notes change)
- Cache failure/win classifications permanently in event log

### Error Handling

- If API key is not set: use rule-based fallbacks silently (no error messages)
- If API key is set but call fails: fall back to rule-based mode and show a small warning banner ("LLM unavailable, using keyword matching")
- Never block the UI on an API call — use Streamlit's async patterns
- Show a small indicator in the sidebar: "LLM: Connected" or "LLM: Off (using rules)" so the user knows which mode they're in

---

## Scoring Examples

### Example 1: High-scoring company

**Guidepoint** (newly added via discovery)
- Use case: Expert networks (win rate: 1.0)
- Status: No outreach yet (stage score: 8)
- TAM: $2M
- Tier: 2
- No engagement signals yet

```
use_case_component = 1.0 × 35 = 35.0
stage_component = (8 / 100) × 25 = 2.0
tam_component = log10(2 × 10) × 3.75 = log10(20) × 3.75 = 1.30 × 3.75 = 4.88
engagement_component = 0
tier_component = 5
decay = 0
propagation = 0

TOTAL = 35.0 + 2.0 + 4.88 + 0 + 5 = 46.88
```

This scores HIGHER than many "Haven't responded to outbound" SaaS companies because Expert Networks has a 100% win rate. This is the correct behavior — the system is telling you "prospect here, not there."

### Example 2: Decaying company

**Canon** (Content provenance, Tier 1, no response for 60+ days)
- Use case: Content provenance (win rate: 0.75)
- Status: Haven't responded to outbound (stage score: 5)
- TAM: $2M
- Tier: 1
- Responded: Cold, no meeting

```
use_case_component = 0.75 × 35 = 26.25
stage_component = (5 / 100) × 25 = 1.25
tam_component = 4.88
engagement_component = 1 (outreach) + 1 (cold response) = 2
tier_component = 10
decay = 3 (30-60 days no response)
propagation = 0

TOTAL = 26.25 + 1.25 + 4.88 + 2 + 10 - 3 = 41.38
```

### Example 3: Post-propagation penalty

**Atlassian was just lost** (Freemium abuse professional, reason: bad_fit)

**Hubspot** (same use case, Tier 2, no response)
- Previous score: 35.2
- Propagation penalty: 5 (bad_fit in same use case)
- New score: 30.2
- System flags: "Atlassian loss suggests freemium abuse (professional) may have fit issues — review Hubspot's positioning before next outreach"

---

## Key Behaviors

### Ranking should surface non-obvious insights

The ranking shouldn't just mirror the status column. It should highlight cases like:
- "This no-outreach company scores higher than 10 companies you've been emailing for months" (because its use case converts well)
- "These 5 companies all have the same failure pattern — consider deprioritizing the category"
- "Your highest-TAM prospect is also your most stale — decision needed"

### The system learns from every interaction

Every logged outcome changes the use case win rates, which ripple through the entire pipeline. The more data you feed it, the better the rankings get.

### Voice-typing friendly

All text inputs (outcome notes, new company descriptions) should be large text areas that accept unstructured, conversational text. The system parses structure from natural language using keyword/regex rules (or Claude API when available). No rigid forms or required fields beyond company name and status. Parsed results are always shown in an editable table so the user can correct before confirming.

---

## V1 Acceptance Criteria

The tool is ready for use when:

1. [ ] Connects to Google Sheet and loads all pipeline data
2. [ ] Computes composite scores for all companies
3. [ ] Displays a sortable, filterable stack rank table
4. [ ] Allows logging an outcome (company + status + free-text reason)
5. [ ] Classifies failure reasons (keyword-based) and shows propagation preview
6. [ ] Recalculates scores after an outcome is logged
7. [ ] Generates follow-up reminders with cadence rules
8. [ ] Parses date references from notes for smart scheduling
9. [ ] Shows overdue / this week / coming up reminder sections
10. [ ] Generates hunting briefs per use case
11. [ ] Accepts batch-pasted new companies and parses them
12. [ ] Scores new companies and inserts them into the stack rank
13. [ ] All state persists across app restarts (via state.json)
14. [ ] Writes are optional and always confirmed by user before executing
15. [ ] All features work fully WITHOUT an Anthropic API key (rule-based fallbacks)
16. [ ] When API key IS provided, LLM-enhanced features activate automatically

---

## Setup Instructions (for team distribution)

The app runs on localhost, similar to the LinkedIn Verified Mockup Generator. Here's what users need:

### Prerequisites
- **Operating System**: Mac or Windows
- **Python 3.10+** installed
- **Time Estimate**: ~10 minutes

### Step 1: Install Python (if not already installed)

Download from [python.org](https://python.org). Verify:

```bash
python3 --version
```

You should see `Python 3.10.x` or higher.

### Step 2: Prepare Project Files

Locate the project folder (sent as a ZIP or cloned from GitHub).
Unzip to a convenient location such as your Desktop.

### Step 3: Install Dependencies

Navigate into the project folder:

```bash
cd path/to/voli-pipeline-ranker
```

Tip: You can type `cd` followed by a space, then drag the folder into the terminal to paste the path.

Install the required packages:

```bash
pip3 install -r requirements.txt
```

### Step 4: Set Up Google Sheets Access

Place the Google service account credentials file at `credentials/service_account.json` (Tawo will provide this file).

### Step 5: Launch the Application

Start the local server:

```bash
streamlit run app.py
```

### Step 6: Access the Tool

Once the terminal shows "You can now view your Streamlit app in your browser", open:

**http://localhost:8501**

The app will automatically open in your default browser.

### How to Stop

Go back to the Terminal window and press **Ctrl + C** to shut down the local server.
