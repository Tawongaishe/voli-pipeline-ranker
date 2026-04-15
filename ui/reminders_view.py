"""View 3: Reminders — overdue, this week, coming up, parked, needs decision."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from reminders import compute_reminders, generate_nudges
from state import save_state


def render(df, state):
    st.header("Reminders & Follow-ups")

    # Compute reminders
    reminders = compute_reminders(df, state)
    state["reminders"] = reminders
    save_state(state)

    now = datetime.now()
    today = now.date()

    # Categorize
    overdue = []
    this_week = []
    coming_up = []
    parked = []
    needs_decision = []

    for company, rem in reminders.items():
        if rem.get("parked_until"):
            parked.append((company, rem))
            continue
        if rem.get("needs_decision"):
            needs_decision.append((company, rem))
            continue

        try:
            followup = datetime.strptime(rem["next_followup"], "%Y-%m-%d").date()
        except (ValueError, TypeError, KeyError):
            continue

        days_until = (followup - today).days
        if days_until < 0:
            overdue.append((company, rem, -days_until))
        elif days_until <= 7:
            this_week.append((company, rem, days_until))
        elif days_until <= 21:
            coming_up.append((company, rem, days_until))

    overdue.sort(key=lambda x: x[2], reverse=True)

    # --- Smart Nudges ---
    nudges = generate_nudges(df, state)
    if nudges:
        st.subheader("Smart Nudges")
        for nudge in nudges[:5]:
            st.info(f"{nudge['icon']} {nudge['message']}")

    # --- OVERDUE ---
    st.markdown("### :red[OVERDUE]")
    if overdue:
        for company, rem, days_over in overdue:
            with st.container():
                c1, c2, c3, c4 = st.columns([3, 2, 2, 3])
                c1.markdown(f"**{company}**")
                c2.text(rem.get("status", ""))
                c3.text(f"{days_over}d overdue")
                c4.text(rem.get("owner", ""))
                st.caption(rem.get("suggested_action", ""))

                bc1, bc2, bc3, bc4 = st.columns(4)
                if bc1.button("Done", key=f"od_{company}"):
                    _mark_done(state, company, reminders)
                    st.rerun()
                if bc2.button("+7d", key=f"os_{company}"):
                    _snooze(state, company, 7, reminders)
                    st.rerun()
                if bc3.button("Park", key=f"op_{company}"):
                    st.session_state[f"park_{company}"] = True
                if bc4.button("Log →", key=f"ol_{company}"):
                    st.session_state["nav"] = "Log Outcome"
                    st.session_state["lo_company_pre"] = company
                    st.rerun()
                st.markdown("---")
    else:
        st.success("No overdue reminders!")

    # --- THIS WEEK ---
    st.markdown("### :orange[THIS WEEK]")
    if this_week:
        for company, rem, days_until in this_week:
            c1, c2, c3 = st.columns([4, 3, 3])
            c1.markdown(f"**{company}** — due in {days_until}d")
            c2.text(rem.get("status", ""))
            c3.text(rem.get("owner", ""))
            st.caption(rem.get("suggested_action", ""))
            st.markdown("---")
    else:
        st.info("Nothing due this week")

    # --- COMING UP ---
    st.markdown("### :blue[COMING UP]")
    if coming_up:
        for company, rem, days_until in coming_up:
            c1, c2 = st.columns([6, 4])
            c1.markdown(f"**{company}** — due in {days_until}d")
            c2.text(rem.get("owner", ""))
    else:
        st.info("Nothing in the next 2-3 weeks")

    # --- PARKED ---
    st.markdown("### PARKED")
    if parked:
        for company, rem in parked:
            c1, c2, c3 = st.columns([4, 3, 3])
            c1.markdown(f"**{company}**")
            c2.text(f"Until: {rem.get('parked_until', '?')}")
            c3.text(rem.get("park_reason", ""))
    else:
        st.info("No parked companies")

    # --- NEEDS DECISION ---
    if needs_decision:
        st.markdown("### :orange[NEEDS DECISION]")
        st.warning(f"{len(needs_decision)} companies have exceeded max follow-up attempts")
        for company, rem in needs_decision:
            c1, c2 = st.columns([5, 5])
            c1.markdown(f"**{company}** — {rem.get('followup_count', 0)} attempts")
            with c2:
                action = st.radio(
                    f"Action for {company}",
                    ["Deprioritize", "Escalate", "Reset cadence"],
                    key=f"nd_{company}",
                    horizontal=True,
                    label_visibility="collapsed",
                )
                if st.button("Apply", key=f"nda_{company}"):
                    if action == "Reset cadence":
                        rem["followup_count"] = 0
                        rem["needs_decision"] = False
                    st.success(f"Applied: {action} for {company}")


def _mark_done(state, company, reminders):
    """Mark a follow-up as done."""
    rem = reminders.get(company, {})
    rem["followup_count"] = rem.get("followup_count", 0) + 1
    cadence = rem.get("cadence_days", 14)
    rem["next_followup"] = (datetime.now() + timedelta(days=cadence)).strftime("%Y-%m-%d")
    state["reminders"][company] = rem
    save_state(state)


def _snooze(state, company, days, reminders):
    """Snooze a reminder by N days."""
    rem = reminders.get(company, {})
    rem["next_followup"] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    state["reminders"][company] = rem
    save_state(state)
