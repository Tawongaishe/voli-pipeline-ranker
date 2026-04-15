"""View 1: Stack Rank — sortable, filterable pipeline table with scores."""

import streamlit as st
import pandas as pd
import plotly.express as px
from config import EXCLUDED_STATUSES, SIGNED_STATUS, CANONICAL_USE_CASES


def _score_color(score):
    if score > 70:
        return "background-color: #c6efce"
    elif score > 40:
        return "background-color: #ffeb9c"
    elif score > 20:
        return "background-color: #fdd49e"
    else:
        return "background-color: #ffc7ce"


def render(scored_df, win_rates):
    st.header("Pipeline Stack Rank")

    # --- Filters in columns ---
    col1, col2, col3, col4 = st.columns(4)

    use_cases = sorted([uc for uc in scored_df["use_case"].dropna().unique() if uc])
    statuses = sorted([s for s in scored_df["status"].dropna().unique() if s])
    tiers = sorted([str(t) for t in scored_df["tier"].dropna().unique() if t])
    owners = sorted([o for o in scored_df["owner"].dropna().unique() if o]) if "owner" in scored_df.columns else []

    with col1:
        sel_uc = st.multiselect("Use Case", use_cases, key="sr_uc")
    with col2:
        sel_status = st.multiselect("Status", statuses, key="sr_status")
    with col3:
        sel_tier = st.multiselect("Tier", tiers, key="sr_tier")
    with col4:
        sel_owner = st.multiselect("Owner", owners, key="sr_owner") if owners else []

    c1, c2 = st.columns(2)
    with c1:
        sort_by = st.selectbox("Sort by", ["Composite Score", "TAM", "Status", "Use Case"], key="sr_sort")
    with c2:
        show_signed = st.checkbox("Show signed partners", key="sr_signed")
        show_depri = st.checkbox("Show deprioritized", key="sr_depri")

    # --- Apply filters ---
    display = scored_df.copy()

    if not show_signed:
        display = display[~display["_status_code"].isin(SIGNED_STATUS)]
    if not show_depri:
        display = display[~display["_status_code"].isin({9, 11})]
    if sel_uc:
        display = display[display["use_case"].isin(sel_uc)]
    if sel_status:
        display = display[display["status"].isin(sel_status)]
    if sel_tier:
        display = display[display["tier"].astype(str).isin(sel_tier)]
    if sel_owner and "owner" in display.columns:
        display = display[display["owner"].isin(sel_owner)]

    # --- Sort ---
    sort_map = {
        "Composite Score": "composite_score",
        "TAM": "tam_score",
        "Status": "_status_code",
        "Use Case": "use_case",
    }
    sort_col = sort_map.get(sort_by, "composite_score")
    ascending = sort_by in ("Status", "Use Case")
    display = display.sort_values(sort_col, ascending=ascending)
    display.insert(0, "Rank", range(1, len(display) + 1))

    # --- Metrics row ---
    m1, m2, m3, m4 = st.columns(4)
    active = scored_df[~scored_df["_status_code"].isin(EXCLUDED_STATUSES)]
    m1.metric("Active Pipeline", len(active))
    m2.metric("Signed", len(scored_df[scored_df["_status_code"] == 1]))
    m3.metric("Avg Score", f"{active['composite_score'].mean():.1f}" if not active.empty else "—")
    m4.metric("Use Cases", len(use_cases))

    # --- Main table ---
    show_cols = ["Rank", "company", "composite_score", "status", "use_case", "tier", "tam_score", "owner"]
    show_cols = [c for c in show_cols if c in display.columns]

    col_config = {
        "Rank": st.column_config.NumberColumn("#", width="small"),
        "company": st.column_config.TextColumn("Company", width="medium"),
        "composite_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f"),
        "status": st.column_config.TextColumn("Status", width="medium"),
        "use_case": st.column_config.TextColumn("Use Case", width="medium"),
        "tier": st.column_config.TextColumn("Tier", width="small"),
        "tam_score": st.column_config.NumberColumn("TAM Score", format="%.1f"),
        "owner": st.column_config.TextColumn("Owner", width="small"),
    }

    st.dataframe(
        display[show_cols],
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
        height=min(600, 40 + len(display) * 35),
    )

    # --- Expandable details ---
    st.subheader("Company Details")
    selected = st.selectbox(
        "Select company to view details",
        display["company"].tolist(),
        key="sr_detail",
    )
    if selected:
        row = display[display["company"] == selected].iloc[0]
        with st.expander(f"{selected} — Score Breakdown", expanded=True):
            sc1, sc2, sc3, sc4, sc5 = st.columns(5)
            sc1.metric("Use Case Win Rate", f"{row.get('use_case_win_rate', 0):.0%}")
            sc2.metric("Stage", f"{row.get('stage_score', 0):.1f}/25")
            sc3.metric("TAM", f"{row.get('tam_score', 0):.1f}/15")
            sc4.metric("Engagement", f"{row.get('engagement_score', 0)}/15")
            sc5.metric("Tier", f"{row.get('tier_score', 0)}/10")

            if row.get("decay_penalty", 0) > 0 or row.get("propagation_penalty", 0) > 0:
                st.warning(f"Penalties: Decay -{row.get('decay_penalty', 0)}, Propagation -{row.get('propagation_penalty', 0)}")

            # Notes
            notes_cols = ["status_notes", "partner_notes", "our_notes", "next_steps"]
            for nc in notes_cols:
                val = row.get(nc)
                if val and str(val).strip():
                    st.text(f"{nc.replace('_', ' ').title()}: {val}")

    # --- Sidebar: Win rate chart ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("Use Case Win Rates")
    if win_rates:
        wr_df = pd.DataFrame([
            {"Use Case": uc, "Win Rate": rate}
            for uc, rate in sorted(win_rates.items(), key=lambda x: x[1], reverse=True)
        ])
        fig = px.bar(
            wr_df, x="Win Rate", y="Use Case", orientation="h",
            color="Win Rate",
            color_continuous_scale=["#ff6b6b", "#ffd93d", "#6bcb77"],
            range_color=[0, 1],
        )
        fig.update_layout(height=max(200, len(wr_df) * 30), margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
        st.sidebar.plotly_chart(fig, use_container_width=True)
