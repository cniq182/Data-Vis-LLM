"""Provisional demo app: the full pipeline in the browser (not the final UI)."""
from __future__ import annotations

import streamlit as st

from data.loader import DataLoadError, extract_schema, load_csv
from llm.interaction_log import log_result
from llm.pipeline import ask
from render.spec import summarize


# =============================================================================
# VISUAL LAYER (presentation only — no business logic lives here)
# =============================================================================

# --- Palette: change these values to re-theme the whole app ------------------
PALETTE = {
    "bg":          "#FAF8F5",  # main background (warm cream)
    "surface":     "#FFFEFC",  # cards / chat bubbles (soft off-white)
    "surface_alt": "#F2EEE7",  # sidebar, user bubbles, inputs (sand)
    "border":      "#E8E3DA",  # hairline borders
    "text":        "#2D2D2A",  # body text (warm charcoal)
    "muted":       "#7A766E",  # captions, helper text
    "accent":      "#7A9E7E",  # primary accent (sage green)
    "accent_dark": "#66896A",  # accent on hover
    "accent_soft": "#E6EEE5",  # accent tint (focus halos, badges)
    "warm":        "#D48C70",  # secondary accent (soft terracotta)
    "slate":       "#6B8E9B",  # tertiary accent (muted slate blue)
}

FONT_FAMILY = "'Plus Jakarta Sans', 'Inter', system-ui, -apple-system, sans-serif"
RADIUS = "14px"
SHADOW = "0 4px 12px rgba(45, 45, 42, 0.04)"
SHADOW_HOVER = "0 8px 20px rgba(45, 45, 42, 0.07)"


def _inject_styles() -> None:
    """Inject the custom CSS. Pure presentation: safe to edit or remove."""
    p = PALETTE
    st.markdown(
        f"""
<style>
/* ---------- 1. Font ------------------------------------------------------ */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

/* Apply the font to text elements only (not to generic spans, so that
   Streamlit's Material icons keep rendering as icons). */
html, body, .stApp, p, li, label, input, textarea, button,
h1, h2, h3, h4, h5, h6, .stMarkdown, [data-testid="stCaptionContainer"] {{
    font-family: {FONT_FAMILY} !important;
}}

/* ---------- 2. Base canvas ---------------------------------------------- */
.stApp {{
    background: {p["bg"]};
    color: {p["text"]};
}}
.block-container {{
    padding-top: 2.5rem !important;
    padding-bottom: 6rem !important;
    max-width: 1100px;
}}

/* ---------- 3. Hide Streamlit chrome ------------------------------------ */
#MainMenu, footer, [data-testid="stDecoration"],
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"] {{
    display: none !important;
}}
/* The header is kept (it hosts the sidebar toggle) but made invisible. */
header[data-testid="stHeader"] {{
    background: transparent !important;
}}

/* ---------- 4. Hero / page header --------------------------------------- */
.ac-hero {{
    display: flex;
    align-items: center;
    gap: 0.9rem;
    margin-bottom: 1.75rem;
}}
.ac-hero-icon {{
    width: 48px; height: 48px;
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    background: {p["accent_soft"]};
    font-size: 1.5rem;
}}
.ac-hero h1 {{
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
    color: {p["text"]} !important;
    margin: 0 !important;
    padding: 0 !important;
}}
.ac-hero p {{
    margin: 0.15rem 0 0 0;
    color: {p["muted"]};
    font-size: 0.95rem;
}}
.ac-badge {{
    display: inline-block;
    margin-left: 0.5rem;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    background: #F6E6DE;
    color: {p["warm"]};
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    vertical-align: middle;
}}

/* ---------- 5 + 6. Upload card ---------------------------------------- */
/* The uploader itself is styled as a card (robust across Streamlit versions). */
[data-testid="stFileUploader"] {{
    background: {p["surface"]};
    border: 1px solid {p["border"]};
    border-radius: 16px;
    padding: 1.1rem 1.25rem 1.25rem 1.25rem;
    box-shadow: {SHADOW};
    margin-bottom: 1.5rem;
    transition: all 0.2s ease-in-out;
}}
[data-testid="stFileUploader"]:hover {{
    box-shadow: {SHADOW_HOVER};
}}
[data-testid="stFileUploader"] label p {{
    font-weight: 600;
    color: {p["text"]};
}}
[data-testid="stFileUploaderDropzone"] {{
    background: {p["bg"]};
    border: 1.5px dashed {p["border"]};
    border-radius: {RADIUS};
    padding: 1.5rem;
    transition: all 0.2s ease-in-out;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
    border-color: {p["accent"]};
    background: {p["accent_soft"]};
}}

/* ---------- 7. Buttons -------------------------------------------------- */
.stButton > button, [data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] {{
    border-radius: 12px !important;
    padding: 0.55rem 1.1rem !important;
    font-weight: 600 !important;
    border: 1px solid {p["border"]} !important;
    box-shadow: {SHADOW};
    transition: all 0.2s ease-in-out !important;
}}
.stButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: {SHADOW_HOVER};
    border-color: {p["accent"]} !important;
    color: {p["accent_dark"]} !important;
}}
.stButton > button:active {{ transform: translateY(0); }}
[data-testid="stBaseButton-primary"] {{
    background: {p["accent"]} !important;
    border-color: {p["accent"]} !important;
    color: #FFFEFC !important;
}}
[data-testid="stBaseButton-primary"]:hover {{
    background: {p["accent_dark"]} !important;
    color: #FFFEFC !important;
}}

/* ---------- 8. Text inputs --------------------------------------------- */
[data-testid="stTextInput"] div[data-baseweb="input"] {{
    border-radius: 12px !important;
    border: 1px solid {p["border"]} !important;
    background: {p["surface"]} !important;
    transition: all 0.2s ease-in-out;
}}
[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {{
    border-color: {p["accent"]} !important;
    box-shadow: 0 0 0 3px {p["accent_soft"]};
}}

/* ---------- 9. Sidebar -------------------------------------------------- */
section[data-testid="stSidebar"] {{
    background: {p["surface_alt"]};
    border-right: 1px solid {p["border"]};
}}
section[data-testid="stSidebar"] .block-container,
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
    padding-top: 2rem;
}}
section[data-testid="stSidebar"] .stButton > button {{
    width: 100%;
}}
.ac-side-title {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {p["muted"]};
    margin: 1.25rem 0 0.5rem 0;
}}
.ac-side-brand {{
    font-weight: 700;
    font-size: 1.05rem;
    color: {p["text"]};
    margin-bottom: 0.25rem;
}}

/* ---------- 10. Expanders ---------------------------------------------- */
[data-testid="stExpander"] details {{
    border-radius: 12px !important;
    border: 1px solid {p["border"]} !important;
    background: {p["surface"]};
}}

/* ---------- 11. Chat messages ------------------------------------------ */
[data-testid="stChatMessage"] {{
    background: {p["surface"]};
    border: 1px solid {p["border"]};
    border-radius: 16px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    box-shadow: {SHADOW};
    transition: box-shadow 0.2s ease-in-out;
}}
[data-testid="stChatMessage"]:hover {{
    box-shadow: {SHADOW_HOVER};
}}
/* User turns get the sand tone so the conversation reads at a glance. */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
    background: {p["surface_alt"]};
    box-shadow: none;
}}
[data-testid="stChatMessageAvatarAssistant"],
[data-testid="chatAvatarIcon-assistant"] {{
    background: {p["accent"]} !important;
}}
[data-testid="stChatMessageAvatarUser"],
[data-testid="chatAvatarIcon-user"] {{
    background: {p["warm"]} !important;
}}
/* Chart inside a message: a little breathing room. */
[data-testid="stChatMessage"] [data-testid="stVegaLiteChart"],
[data-testid="stChatMessage"] .stVegaLiteChart {{
    margin: 0.75rem 0 0.25rem 0;
}}
[data-testid="stChatMessage"] [data-testid="stCaptionContainer"] {{
    color: {p["muted"]};
    font-size: 0.85rem;
}}

/* ---------- 12. Chat input (bottom bar) -------------------------------- */
[data-testid="stBottom"], [data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {{
    background: {p["bg"]} !important;
}}
[data-testid="stChatInput"] {{
    border-radius: 16px !important;
    border: 1px solid {p["border"]} !important;
    background: {p["surface"]} !important;
    box-shadow: {SHADOW_HOVER};
    transition: all 0.2s ease-in-out;
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: {p["accent"]} !important;
    box-shadow: 0 0 0 3px {p["accent_soft"]}, {SHADOW_HOVER};
}}
[data-testid="stChatInputSubmitButton"] {{
    border-radius: 10px !important;
}}

/* ---------- 13. Alerts (info / warning / error) ------------------------ */
[data-testid="stAlert"], [data-testid="stAlertContainer"] {{
    border-radius: {RADIUS} !important;
    border: none !important;
}}
[data-testid="stAlertContentInfo"]    {{ color: #3F5F6B; }}
[data-testid="stAlertContentWarning"] {{ color: #8A5A3C; }}
[data-testid="stAlertContentError"]   {{ color: #8C4A3A; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]),
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {{
    background: #E9F0F2 !important;
}}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
    background: #F8EDE4 !important;
}}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]),
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
    background: #F6E3DD !important;
}}

/* ---------- 14. Spinner ----------------------------------------------- */
[data-testid="stSpinner"] {{
    color: {p["muted"]};
    font-weight: 500;
}}
[data-testid="stSpinner"] i, [data-testid="stSpinner"] > div > div {{
    border-top-color: {p["accent"]} !important;
}}

/* ---------- 15. JSON viewer ------------------------------------------- */
[data-testid="stJson"] {{
    border-radius: 12px;
    background: {p["bg"]} !important;
    padding: 0.5rem;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _hero() -> None:
    """Page header (replaces the plain st.title, same title text)."""
    st.markdown(
        """
<div class="ac-hero">
  <div class="ac-hero-icon">📊</div>
  <div>
    <h1>autochart <span class="ac-badge">demo</span></h1>
    <p>Upload a dataset and ask questions about it in plain language.</p>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _side_title(text: str) -> None:
    st.markdown(f'<div class="ac-side-title">{text}</div>', unsafe_allow_html=True)


# =============================================================================
# APP (logic unchanged from the original)
# =============================================================================

st.set_page_config(page_title="autochart (demo)", page_icon="📊", layout="wide")
_inject_styles()
_hero()

uploaded = st.file_uploader("Upload a CSV file", type=["csv"])
if uploaded is None:
    st.info("Upload a CSV to start.", icon="📄")
    st.stop()

# A new file resets the conversation.
if st.session_state.get("file_id") != uploaded.file_id:
    try:
        df = load_csv(uploaded.getvalue())
    except DataLoadError as exc:
        st.error(str(exc), icon="🧺")
        st.stop()
    st.session_state.update(
        file_id=uploaded.file_id,
        df=df,
        schema=extract_schema(df),
        messages=[],
        current_spec=None,
        pending_clarification=None,
    )

df = st.session_state.df
schema = st.session_state.schema

with st.sidebar:
    st.markdown('<div class="ac-side-brand">📊 autochart</div>', unsafe_allow_html=True)

    _side_title("Session")
    session_id = st.text_input(
        "Session ID (participant code)", value="", placeholder="e.g. P07",
    ).strip()

    _side_title("Chart")
    if st.button("New chart", type="primary"):
        # Start the next task from scratch: forget the current chart and conversation.
        st.session_state.update(messages=[], current_spec=None,
                                pending_clarification=None, pending_question=None)
        st.rerun()

    _side_title("Debug")
    with st.expander("Schema sent to the model"):
        st.json(schema.to_prompt_dict())

# Show the conversation so far.
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])
        if msg.get("spec"):
            st.vega_lite_chart(df, msg["spec"], key=f"chart_{i}")
            st.caption(msg["summary"])
if not session_id:
    st.warning("Enter a Session ID in the sidebar before asking questions.", icon="🔑")
    st.stop()
question = st.chat_input("Ask a question about your data")
if question:
    st.session_state.messages.append({"role": "user", "text": question})
    with st.chat_message("user"):
        st.markdown(question)

    current = st.session_state.current_spec
    pending = st.session_state.get("pending_clarification")
    original = st.session_state.get("pending_question")
    with st.spinner("Generating chart..."):
        result = ask(
            schema, question, current,
            previous_clarification=pending,
            previous_question=original,
        )
    log_result(question, result, session_id=session_id, had_current_spec=current is not None)

    # Remember the original question while clarifications go back and forth.
    if result.clarification:
        st.session_state.pending_question = original if pending else question
    else:
        st.session_state.pending_question = None
    st.session_state.pending_clarification = result.clarification
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
