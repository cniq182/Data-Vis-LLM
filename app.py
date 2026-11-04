"""Provisional demo app: the full pipeline in the browser (not the final UI)."""
from __future__ import annotations

import streamlit as st

from data.loader import DataLoadError, extract_schema, load_csv
from llm.interaction_log import log_result
from llm.pipeline import ask
from render.spec import summarize

st.set_page_config(page_title="autochart (demo)", layout="wide")
st.title("autochart (demo)")

uploaded = st.file_uploader("Upload a CSV file", type=["csv"])
if uploaded is None:
    st.info("Upload a CSV to start.")
    st.stop()

# A new file resets the conversation.
if st.session_state.get("file_id") != uploaded.file_id:
    try:
        df = load_csv(uploaded.getvalue())
    except DataLoadError as exc:
        st.error(str(exc))
        st.stop()
    st.session_state.update(
        file_id=uploaded.file_id,
        df=df,
        schema=extract_schema(df),
        messages=[],
        current_spec=None,
    )

df = st.session_state.df
schema = st.session_state.schema

with st.sidebar:
    session_id = st.text_input("Session ID", value="demo")
    with st.expander("Schema sent to the model"):
        st.json(schema.to_prompt_dict())

# Show the conversation so far.
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])
        if msg.get("spec"):
            st.vega_lite_chart(df, msg["spec"], key=f"chart_{i}")
            st.caption(msg["summary"])

question = st.chat_input("Ask a question about your data")
if question:
    st.session_state.messages.append({"role": "user", "text": question})
    with st.chat_message("user"):
        st.markdown(question)

    current = st.session_state.current_spec
    with st.spinner("Generating chart..."):
        result = ask(schema, question, current)
    log_result(question, result, session_id=session_id, had_current_spec=current is not None)

    if result.ok:
        st.session_state.current_spec = result.spec
        reply = {
            "role": "assistant",
            "text": f"Done in {result.total_latency_s:.1f} s ({len(result.attempts)} attempt(s)).",
            "spec": result.spec,
            "summary": summarize(result.spec),
        }
    elif result.clarification:
        reply = {"role": "assistant", "text": result.clarification}
    else:
        reply = {"role": "assistant", "text": f"⚠️ {result.error}"}

    st.session_state.messages.append(reply)
    st.rerun()