"""VOLI Pipeline Ranker — Streamlit entry point."""

import streamlit as st
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LLM_AVAILABLE, SHEET_TAB
from sheets import load_data
from scoring import compute_scores
from state import load_state, save_state
from ui import stack_rank, log_outcome, reminders_view, discovery_view

st.set_page_config(
    page_title="VOLI Pipeline Ranker",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar navigation ---
st.sidebar.title("VOLI Pipeline Ranker")
st.sidebar.caption("Verified on LinkedIn — BD Pipeline Tool")

# LLM indicator
if LLM_AVAILABLE:
    st.sidebar.success("LLM: Connected", icon="🤖")
else:
    st.sidebar.info("LLM: Off (using rules)", icon="📋")

nav = st.sidebar.radio(
    "Navigate",
    ["Stack Rank", "Log Outcome", "Reminders", "Discovery"],
    key="nav",
)

st.sidebar.markdown("---")

# --- Load data ---
@st.cache_data(ttl=300)
def _load_pipeline():
    return load_data()


def refresh_data():
    _load_pipeline.clear()
    if "scored_df" in st.session_state:
        del st.session_state["scored_df"]


if st.sidebar.button("🔄 Refresh from Sheet"):
    refresh_data()
    st.rerun()

df, source, error = _load_pipeline()

if error:
    st.error(f"Could not load data: {error}")
    st.info("Place your Google credentials at `credentials/service_account.json` or ensure `pipeline_cache.csv` exists.")
    st.stop()

st.sidebar.caption(f"Data source: {source}")
st.sidebar.caption(f"Tab: {SHEET_TAB}")
st.sidebar.caption(f"Companies: {len(df)}")

# --- Load state ---
state = load_state()

# --- Compute scores ---
scored_df, win_rates = compute_scores(df, state)

# Update state with scores
for _, row in scored_df.iterrows():
    company = row.get("company")
    if company:
        state["scores"][company] = {
            "composite_score": row.get("composite_score", 0),
            "use_case_win_rate": row.get("use_case_win_rate", 0),
            "stage_score": row.get("stage_score", 0),
            "tam_score": row.get("tam_score", 0),
            "engagement_score": row.get("engagement_score", 0),
            "tier_score": row.get("tier_score", 0),
            "decay_penalty": row.get("decay_penalty", 0),
            "propagation_penalty": row.get("propagation_penalty", 0),
        }
save_state(state)

# --- Render views ---
if nav == "Stack Rank":
    stack_rank.render(scored_df, win_rates)
elif nav == "Log Outcome":
    log_outcome.render(scored_df, state)
elif nav == "Reminders":
    reminders_view.render(scored_df, state)
elif nav == "Discovery":
    discovery_view.render(scored_df, state)
