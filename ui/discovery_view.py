"""View 4: Discovery — hunting briefs and new company intake."""

import streamlit as st
import pandas as pd
from discovery import generate_hunting_brief, format_hunting_brief_text, parse_company_text
from scoring import compute_scores
from state import add_company, save_state
from sheets import add_company_to_sheet
from config import CANONICAL_USE_CASES, STATUS_OPTIONS


def render(df, state):
    st.header("Discovery")

    tab1, tab2 = st.tabs(["Hunting Briefs", "Add New Companies"])

    with tab1:
        _render_briefs(df, state)

    with tab2:
        _render_intake(df, state)


def _render_briefs(df, state):
    st.subheader("Hunting Briefs by Use Case")

    use_cases = sorted([uc for uc in df["use_case"].dropna().unique() if uc])
    if not use_cases:
        use_cases = CANONICAL_USE_CASES

    for uc in use_cases:
        uc_count = len(df[df["use_case"] == uc])
        with st.expander(f"{uc} ({uc_count} companies)"):
            # Check cache
            cached = state.get("hunting_briefs", {}).get(uc)
            if cached and not st.button(f"Regenerate {uc}", key=f"regen_{uc}"):
                brief = cached
            else:
                brief = generate_hunting_brief(df, uc, state)
                if brief:
                    state.setdefault("hunting_briefs", {})[uc] = brief
                    save_state(state)

            if brief:
                # Summary metrics
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Win Rate", f"{brief['win_rate']:.0%}")
                c2.metric("Active", brief["active_count"])
                c3.metric("Signed", brief["signed_count"])
                gap = brief["gap_assessment"]
                gap_color = {"HEALTHY": "normal", "LOW": "off", "EMPTY": "off"}.get(gap, "normal")
                c4.metric("Gap", gap, delta_color=gap_color)

                # Full brief text
                st.code(format_hunting_brief_text(brief), language=None)

                # AI suggestions if available
                if brief.get("ai_suggestions"):
                    st.markdown("**AI-Suggested Companies:**")
                    st.markdown(brief["ai_suggestions"])
            else:
                st.info(f"No companies found for {uc}")


def _render_intake(df, state):
    st.subheader("Add New Companies")
    st.caption("Paste research notes, voice-typed text, or company descriptions below.")

    text_input = st.text_area(
        "Company descriptions",
        height=200,
        key="disc_text",
        placeholder="e.g., 'Guidepoint is an expert network similar to AlphaSights, about 500 employees. Dialectica is in the same space, based in London.'",
    )

    default_uc = st.selectbox(
        "Default use case (for companies where it can't be determined)",
        [""] + CANONICAL_USE_CASES,
        key="disc_default_uc",
    )

    if st.button("Parse Companies", key="disc_parse", type="primary") and text_input.strip():
        parsed = parse_company_text(text_input, default_use_case=default_uc)
        if parsed:
            st.session_state["parsed_companies"] = parsed
        else:
            st.warning("Could not parse any companies from the text. Try more structured input.")

    # Show parsed results in editable table
    if "parsed_companies" in st.session_state and st.session_state["parsed_companies"]:
        parsed = st.session_state["parsed_companies"]
        edit_df = pd.DataFrame(parsed)

        st.markdown("### Parsed Results — edit before confirming")
        edited = st.data_editor(
            edit_df,
            column_config={
                "company": st.column_config.TextColumn("Company", required=True),
                "use_case": st.column_config.SelectboxColumn("Use Case", options=CANONICAL_USE_CASES),
                "tier": st.column_config.SelectboxColumn("Tier", options=["1", "2", "3", "ATS"]),
                "tam": st.column_config.NumberColumn("Est. TAM (M$)"),
                "notes": st.column_config.TextColumn("Notes"),
                "status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="disc_editor",
        )

        c1, c2 = st.columns(2)
        write_to_sheet = c2.checkbox("Also add to Google Sheet", key="disc_write")

        if c1.button("Confirm & Add", key="disc_confirm", type="primary"):
            added = []
            for _, row in edited.iterrows():
                name = row.get("company", "").strip()
                if not name:
                    continue
                # Add to df (in session state)
                new_row = {
                    "company": name,
                    "status": row.get("status", "No outreach yet"),
                    "use_case": row.get("use_case", ""),
                    "tier": str(row.get("tier", "2")),
                    "tam": row.get("tam"),
                    "our_notes": row.get("notes", ""),
                    "owner": "",
                    "outreach": "N",
                }
                add_company(state, name, source="discovery")
                added.append(name)

                if write_to_sheet:
                    ok, msg = add_company_to_sheet(new_row)
                    if not ok:
                        st.warning(f"Could not add {name} to sheet: {msg}")

            save_state(state)
            st.success(f"Added {len(added)} companies: {', '.join(added)}")

            # Store for reloading
            st.session_state["new_companies"] = added
            del st.session_state["parsed_companies"]
            st.rerun()

    # Show recently added
    recent = state.get("added_companies", [])
    if recent:
        st.markdown("---")
        st.subheader("Recently Added")
        for entry in reversed(recent[-10:]):
            st.text(f"[{entry.get('added_date', '?')}] {entry['company']} (via {entry.get('source', '?')})")
