import streamlit as st


st.set_page_config(page_title="Billing Optimizer Demo", layout="wide")


def _format_currency(value) -> str:
    amount = 0.0 if value is None else float(value)
    return f"${amount:,.2f}"


@st.cache_resource
def _load_pipeline_modules():
    from optimizer import find_highest_reimbursing_code_and_subset
    from parser import CPT_JSON_FILE, load_cpt_code_dict, process_single_note

    valid_codes_dict = load_cpt_code_dict(CPT_JSON_FILE)
    return process_single_note, find_highest_reimbursing_code_and_subset, valid_codes_dict


def _format_subset_lines(subset: dict | None) -> list[str]:
    if not subset:
        return []

    lines = []
    for code_status in subset.get("code_statuses", []):
        code = str(code_status.get("cpt_code", "")).strip()
        status = str(code_status.get("status", "")).strip()
        suffix = " (modifier required)" if status == "valid_with_modifier" else ""
        lines.append(f"{code}{suffix}")
    return lines


def main() -> None:
    st.title("Billing Optimizer Demo")
    st.write("Paste a patient note, run the parser pipeline, and review the highest-reimbursing code versus the best valid subset.")

    note_text = st.text_area(
        "Patient note",
        height=320,
        placeholder="Paste the full clinical note here...",
    )

    if st.button("Run pipeline", type="primary"):
        if not note_text.strip():
            st.warning("Enter a patient note before running the pipeline.")
            return

        try:
            process_single_note, optimize_note, valid_codes_dict = _load_pipeline_modules()
        except Exception as exc:
            st.error(f"Unable to load the parser/optimizer pipeline: {exc}")
            return

        with st.spinner("Running parser and optimizer..."):
            try:
                parsed_items = process_single_note(note_text, valid_codes_dict=valid_codes_dict)
                optimization_result = optimize_note(parsed_items)
            except Exception as exc:
                st.error(f"Pipeline execution failed: {exc}")
                return

        highest_code = optimization_result.get("highest_reimbursing_code")
        highest_subset = optimization_result.get("highest_reimbursing_subset")
        delta = optimization_result.get("delta", 0.0)

        st.subheader("Output")

        code_col, subset_col, delta_col = st.columns(3)

        with code_col:
            st.markdown("**`highest_reimbursing_code`**")
            if highest_code:
                st.write(f"Code: `{highest_code.get('cpt_code', '')}`")
                st.write(f"Reimbursement: {_format_currency(highest_code.get('total_reimbursement'))}")
            else:
                st.write("No billable code found.")

        with subset_col:
            st.markdown("**`highest_reimbursing_subset`**")
            if highest_subset:
                st.write(f"Total reimbursement: {_format_currency(highest_subset.get('total_reimbursement'))}")
                for line in _format_subset_lines(highest_subset):
                    st.markdown(f"- `{line}`")
            else:
                st.write("No valid subset found.")

        with delta_col:
            st.markdown("**`delta`**")
            st.metric("Subset minus best single code", _format_currency(delta))

        with st.expander("Parsed items"):
            st.json(parsed_items)

        with st.expander("Full optimizer output"):
            st.json(optimization_result)


if __name__ == "__main__":
    main()
