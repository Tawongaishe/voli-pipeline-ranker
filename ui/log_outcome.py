"""View 2: Log Outcome — record status changes with classification."""

import streamlit as st
from datetime import datetime
from config import STATUS_OPTIONS, get_status_info, SIGNED_STATUS
from classifier import (
    classify_failure, classify_win,
    FAILURE_LABELS, WIN_LABELS,
)
from scoring import apply_propagation, compute_scores
from state import log_event, save_state
from sheets import write_status_to_sheet


def render(df, state):
    st.header("Log Outcome")

    companies = sorted(df["company"].dropna().unique().tolist())

    # Pre-select from query params if available
    company = st.selectbox("Company", companies, key="lo_company")
    new_status = st.selectbox("New Status", STATUS_OPTIONS, key="lo_status")
    what_happened = st.text_area(
        "What happened? (free-text, voice-typing welcome)",
        height=150,
        key="lo_text",
        placeholder="e.g., 'Had a great call, they're reviewing the contract with legal. CEO seemed excited about reducing fraud.'",
    )
    interaction_date = st.date_input("Date of interaction", value=datetime.now(), key="lo_date")

    if st.button("Preview Impact", key="lo_preview", type="primary"):
        if not company:
            st.error("Select a company")
            return

        # Current status
        current_row = df[df["company"] == company]
        if current_row.empty:
            st.error("Company not found")
            return

        old_status = current_row.iloc[0].get("status", "Unknown")
        old_code = get_status_info(old_status)["code"]
        new_code = get_status_info(new_status)["code"]

        # Build combined text for classification
        notes_text = what_happened
        for field in ["status_notes", "partner_notes", "our_notes"]:
            val = current_row.iloc[0].get(field, "")
            if val and str(val).strip():
                notes_text += f" {val}"

        # Classify
        is_loss = new_code in (7, 9)
        is_win = new_code in (1, 2)

        st.markdown("### Preview")
        st.info(f"**Status change**: {old_status} → {new_status}")

        # Auto-classify
        if is_loss:
            category, explanation, confidence = classify_failure(
                notes_text,
                company_name=company,
                use_case=current_row.iloc[0].get("use_case", ""),
            )
            st.warning(f"**Auto-classified reason**: {explanation} (confidence: {confidence})")

            # Override dropdown
            override = st.selectbox(
                "Override classification if needed",
                list(FAILURE_LABELS.keys()),
                index=list(FAILURE_LABELS.keys()).index(category),
                format_func=lambda x: FAILURE_LABELS[x],
                key="lo_override",
            )
            category = override

            # Propagation preview
            prop_actions = apply_propagation(df, company, category, state)
            if prop_actions:
                st.markdown("**Propagation effects:**")
                for action in prop_actions[:10]:
                    st.text(f"  • {action}")

        elif is_win:
            category, explanation, confidence = classify_win(
                notes_text,
                company_name=company,
                use_case=current_row.iloc[0].get("use_case", ""),
            )
            st.success(f"**Win classified as**: {explanation} (confidence: {confidence})")

            override = st.selectbox(
                "Override classification if needed",
                list(WIN_LABELS.keys()),
                index=list(WIN_LABELS.keys()).index(category),
                format_func=lambda x: WIN_LABELS[x],
                key="lo_win_override",
            )
            category = override
        else:
            category = ""

        # Score impact estimate
        old_score = current_row.iloc[0].get("composite_score", 0)
        st.metric("Current score", f"{old_score:.1f}")

        # Store in session for confirm
        st.session_state["pending_outcome"] = {
            "company": company,
            "old_status": old_status,
            "new_status": new_status,
            "reason_text": what_happened,
            "reason_category": category,
            "date": str(interaction_date),
        }

    # Confirm button
    if "pending_outcome" in st.session_state:
        pending = st.session_state["pending_outcome"]
        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Confirm & Save", key="lo_confirm", type="primary"):
                # Log event
                event = log_event(
                    state,
                    pending["company"],
                    pending["old_status"],
                    pending["new_status"],
                    pending["reason_text"],
                    pending["reason_category"],
                )
                save_state(state)
                st.success(f"Logged: {pending['company']} → {pending['new_status']}")
                del st.session_state["pending_outcome"]
                st.rerun()

        with col2:
            write_back = st.checkbox("Also update Google Sheet", key="lo_writeback")
            if write_back and st.button("Write to Sheet", key="lo_write"):
                ok, msg = write_status_to_sheet(pending["company"], pending["new_status"])
                if ok:
                    st.success("Sheet updated")
                else:
                    st.warning(f"Could not update sheet: {msg}")

        with col3:
            if st.button("Cancel", key="lo_cancel"):
                del st.session_state["pending_outcome"]
                st.rerun()

    # Recent events
    events = state.get("event_log", [])
    if events:
        st.markdown("---")
        st.subheader("Recent Events")
        for ev in reversed(events[-10:]):
            st.text(f"[{ev.get('timestamp', '?')[:16]}] {ev['company']}: {ev.get('old_status', '?')} → {ev['new_status']} | {ev.get('reason_category', '')}")
