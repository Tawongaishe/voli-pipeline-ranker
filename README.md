# 🔵 VOLI Pipeline Ranker

Interactive pipeline management tool for LinkedIn's "Verified on LinkedIn" (VOLI) partnerships program. Ranks prospective partner companies using a composite scoring algorithm, suggests where to find new partners, and generates follow-up reminders for the BD team.

## ✨ Features

- 📊 **Stack Rank** — Score-sorted pipeline with filters by use case, status, tier, and owner. Expandable score breakdowns per company.
- 📝 **Log Outcome** — Record status changes with auto-classified win/loss reasons. See propagation effects across the pipeline before confirming.
- ⏰ **Reminders** — Auto-generated follow-up cadences. Overdue, this week, coming up, parked, and needs-decision sections. Smart nudges for social proof, stale pipelines, and batch outreach.
- 🔍 **Discovery** — Hunting briefs per use case with win rate analysis, gap assessment, and Sales Navigator search terms. Paste unstructured text to add new companies.

## 🧮 Scoring Engine

Each company gets a composite score (0–100) based on:

| Component | Weight | Description |
|---|---|---|
| 🏆 Use Case Win Rate | 35% | How well this use case converts, with Bayesian smoothing |
| 📈 Stage Momentum | 25% | Pipeline stage score with staleness decay |
| 💰 TAM | 15% | Log-scaled total addressable market |
| 🤝 Engagement Signals | 15% | Outreach, response, meeting, contract signals |
| 🏅 Tier Bonus | 10% | Tier 1/2/ATS scoring |
| ⚠️ Penalties | negative | Decay for non-responsive, propagation from losses |

## 🚀 Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app loads from a local CSV cache (`pipeline_cache.csv`) by default. No credentials needed to get started.

## 📄 Google Sheets Integration (Optional)

To connect to the live Google Sheet:

1. Create a Google Cloud service account with Sheets API enabled
2. Share the sheet with the service account email
3. Place the JSON key at `credentials/service_account.json`
4. Set environment variables (or use `.env`):
   ```
   GOOGLE_SHEETS_ID=1NeBFnOax3GwMQXP8MFoZbA7q5rUfZ-jmobLH1S_8Ewo
   GOOGLE_CREDENTIALS_PATH=./credentials/service_account.json
   ```

## 🤖 LLM Enhancement (Optional)

Set `ANTHROPIC_API_KEY` in your environment to enable smarter classification, date parsing, hunting brief suggestions, and company intake parsing. Everything works fully without it using keyword/regex fallbacks.

## 🛠️ Tech Stack

- **Streamlit** — UI framework
- **Pandas** — Data manipulation
- **Plotly** — Charts
- **gspread** — Google Sheets API (optional)
- **Anthropic SDK** — LLM features (optional)
