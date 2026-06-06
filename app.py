# =============================================================================
# Marketing Manager v3 — AI Campaign Builder for Meta Ads
# =============================================================================
# pip install streamlit anthropic google-genai pillow requests pandas
#
# Run:  streamlit run app.py
#
# Claude Max: Use your API key from console.anthropic.com (Max plan includes
# API access). Select "Claude Opus 4" in the model picker.
#
# NOTE: marketing_accounts.json stores Meta tokens locally — keep secure.
# =============================================================================

import streamlit as st
import anthropic
import google.genai as genai
from google.genai import types as genai_types
import json
import base64
import io
import os
import re
import time
import tempfile
import requests
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore

# ── Paths ────────────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent.resolve()
# Account data stored in Firestore (persists across deploys)
LOGOS_DIR = APP_DIR / "assets" / "logos"
LOGOS_DIR.mkdir(parents=True, exist_ok=True)

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Marketing Manager",
    page_icon=":material/campaign:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ────────────────────────────────────────────────────────────

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap" rel="stylesheet">
<style>
    /* ── Animations ───────────────────────────────── */
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

    /* ── Typography ────────────────────────────────── */
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif !important; }

    .mm-logo {
        font-size: 1.35rem; font-weight: 800; letter-spacing: -0.3px;
        background: linear-gradient(135deg, #fff, #a5b4fc);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 2px; line-height: 1.2;
    }
    .mm-logo-sub {
        font-size: 0.72rem; font-weight: 500; letter-spacing: 0.5px;
        text-transform: uppercase; opacity: 0.35; margin-bottom: 1rem;
    }
    .mm-hero {
        font-size: 1.75rem; font-weight: 800; letter-spacing: -0.5px;
        background: linear-gradient(135deg, #fff 30%, #a5b4fc 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 2px; animation: fadeIn 0.5s ease;
    }
    .mm-hero-sub {
        font-size: 0.88rem; opacity: 0.45; font-weight: 400;
        margin-bottom: 1.5rem; animation: fadeIn 0.6s ease 0.1s both;
    }

    /* ── Material icons inline ─────────────────────── */
    .mi {
        font-family: 'Material Symbols Rounded';
        font-size: 18px; vertical-align: middle;
        margin-right: 6px; font-weight: 400;
        font-style: normal; display: inline-block;
        line-height: 1; letter-spacing: normal;
        -webkit-font-smoothing: antialiased;
    }
    .mi-sm { font-size: 14px; }
    .mi-lg { font-size: 22px; }

    /* ── Status pills ──────────────────────────────── */
    .pill {
        display: inline-block; padding: 3px 12px; border-radius: 100px;
        font-size: 0.72rem; font-weight: 600; letter-spacing: 0.3px;
        vertical-align: middle; transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .pill-ok { background: rgba(34,197,94,0.15); color: #4ade80; box-shadow: 0 0 8px rgba(34,197,94,0.1); }
    .pill-warn { background: rgba(251,191,36,0.15); color: #fbbf24; box-shadow: 0 0 8px rgba(251,191,36,0.1); }
    .pill-err { background: rgba(248,113,113,0.15); color: #f87171; box-shadow: 0 0 8px rgba(248,113,113,0.1); }

    /* ── Sidebar ───────────────────────────────────── */
    section[data-testid="stSidebar"] > div:first-child { padding-top: 1.5rem; }
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    div[data-testid="InputInstructions"] { display: none; }
    .sidebar-section {
        font-size: 0.68rem; font-weight: 600; letter-spacing: 0.8px;
        text-transform: uppercase; opacity: 0.35;
        margin: 1.25rem 0 0.6rem 0; padding-bottom: 0.4rem;
        border-bottom: 1px solid rgba(255,255,255,0.04);
    }

    /* ── Cards / expanders ─────────────────────────── */
    div[data-testid="stExpander"] {
        border: 1px solid rgba(255,255,255,0.08); border-radius: 12px;
        margin-bottom: 0.75rem; background: rgba(255,255,255,0.03);
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
    }
    div[data-testid="stExpander"]:hover {
        border-color: rgba(99,102,241,0.2);
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        background: rgba(255,255,255,0.04);
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600; font-size: 0.88rem;
        padding: 0.75rem 1rem; transition: color 0.2s ease;
    }
    div[data-testid="stExpander"] summary:hover { color: #a5b4fc; }
    div[data-testid="stExpander"] [data-testid="stExpanderDetails"] { animation: slideUp 0.3s ease; }

    /* ── Bordered containers (account cards, etc.) ── */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 12px !important; background: rgba(255,255,255,0.02) !important;
        backdrop-filter: blur(12px);
        transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
        margin-bottom: 0.5rem;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(99,102,241,0.15) !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        background: rgba(255,255,255,0.03) !important;
    }

    /* ── Tabs ──────────────────────────────────────── */
    button[data-baseweb="tab"] {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important; font-size: 0.82rem !important;
        letter-spacing: 0.2px;
        transition: background 0.2s ease, color 0.2s ease !important;
        border-radius: 8px 8px 0 0 !important;
    }
    button[data-baseweb="tab"]:hover {
        background: rgba(99,102,241,0.08) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #a5b4fc !important;
    }
    div[data-baseweb="tab-highlight"] {
        background: linear-gradient(90deg, #6366f1, #8b5cf6) !important;
    }
    div[data-baseweb="tab-border"] {
        background: rgba(255,255,255,0.06) !important;
    }

    /* ── Buttons ───────────────────────────────────── */
    .stButton > button {
        border-radius: 8px !important; font-family: 'Inter', sans-serif !important;
        transition: all 0.25s ease !important; font-weight: 500 !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .stButton > button:active {
        transform: translateY(0) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        border: none !important; font-weight: 600 !important;
        letter-spacing: 0.3px; box-shadow: 0 2px 8px rgba(99,102,241,0.3);
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        box-shadow: 0 4px 20px rgba(99,102,241,0.4);
    }
    .stButton > button[kind="primary"]:active {
        box-shadow: 0 1px 4px rgba(99,102,241,0.3);
    }
    .stButton > button:not([kind="primary"]) {
        border: 1px solid rgba(255,255,255,0.1) !important;
        background: rgba(255,255,255,0.04) !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        border-color: rgba(99,102,241,0.3) !important;
        background: rgba(99,102,241,0.08) !important;
    }

    /* ── Form inputs ──────────────────────────────── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 8px !important; background: rgba(255,255,255,0.03) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
        font-family: 'Inter', sans-serif !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: rgba(99,102,241,0.5) !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important;
        background: rgba(255,255,255,0.05) !important;
    }
    [data-baseweb="select"] > div {
        border-radius: 8px !important; border: 1px solid rgba(255,255,255,0.1) !important;
        background: rgba(255,255,255,0.03) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    [data-baseweb="select"] > div:hover {
        border-color: rgba(99,102,241,0.3) !important;
    }

    /* ── File uploader ────────────────────────────── */
    [data-testid="stFileUploader"] {
        border: 2px dashed rgba(255,255,255,0.1); border-radius: 12px;
        padding: 1rem; transition: border-color 0.25s ease, background 0.25s ease;
        background: rgba(255,255,255,0.02);
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(99,102,241,0.3); background: rgba(99,102,241,0.03);
    }
    [data-testid="stFileUploader"] button {
        border-radius: 8px !important;
        border: 1px solid rgba(99,102,241,0.3) !important;
        background: rgba(99,102,241,0.08) !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stFileUploader"] button:hover {
        background: rgba(99,102,241,0.15) !important;
        border-color: rgba(99,102,241,0.5) !important;
    }
    [data-testid="stFileUploader"] small { opacity: 0.4; }

    /* ── Progress bar ──────────────────────────────── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #6366f1, #8b5cf6, #a78bfa);
        border-radius: 100px; transition: width 0.4s ease;
    }
    .stProgress > div > div > div {
        background: rgba(255,255,255,0.06) !important; border-radius: 100px;
    }

    /* ── Metrics ───────────────────────────────────── */
    [data-testid="stMetricValue"] {
        font-weight: 700; font-size: 1.5rem !important;
        background: linear-gradient(135deg, #fff, #a5b4fc);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.72rem !important; text-transform: uppercase;
        letter-spacing: 0.5px; opacity: 0.5; font-weight: 600;
    }
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px; padding: 1rem 1.25rem !important;
        transition: border-color 0.25s ease, background 0.25s ease;
    }
    [data-testid="stMetric"]:hover {
        border-color: rgba(99,102,241,0.15); background: rgba(255,255,255,0.04);
    }

    /* ── Forms ─────────────────────────────────────── */
    [data-testid="stForm"] {
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 12px !important; background: rgba(255,255,255,0.02) !important;
        backdrop-filter: blur(12px); padding: 1.5rem !important;
    }

    /* ── Alerts ────────────────────────────────────── */
    .stAlert {
        border-radius: 10px !important; border: 1px solid rgba(255,255,255,0.06) !important;
        backdrop-filter: blur(8px); animation: slideUp 0.3s ease;
    }

    /* ── Images ────────────────────────────────────── */
    [data-testid="stImage"] {
        border-radius: 10px; overflow: hidden;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    [data-testid="stImage"]:hover {
        transform: scale(1.02); box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }

    /* ── Dividers ──────────────────────────────────── */
    hr { border: none !important; border-top: 1px solid rgba(255,255,255,0.05) !important; margin: 1.25rem 0 !important; }

    /* ── Hide Streamlit cruft ──────────────────────── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] { background: transparent; }

    /* ── Footer ────────────────────────────────────── */
    .mm-footer {
        text-align: center; opacity: 0.25; font-size: 0.72rem;
        padding: 2rem 0 1rem 0; letter-spacing: 0.3px;
    }

    /* ── Content fade-in ──────────────────────────── */
    [data-testid="stTabs"] { animation: fadeIn 0.4s ease; }
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────────────────

def _load_secret(secret_name: str) -> str:
    """Load a secret from Streamlit secrets or environment variables."""
    try:
        return st.secrets.get(secret_name, "")
    except Exception:
        return os.environ.get(secret_name, "")

DEFAULTS = {
    "anthropic_key": _load_secret("ANTHROPIC_API_KEY"),
    "google_key": _load_secret("GOOGLE_GENAI_API_KEY"),
    "campaign_data": None,
    "generated_images": [],
    "branded_images": [],
    "uploaded_media": [],
    "publish_log": [],
    "dry_run": True,
    "campaign_prompt": "",
    "active_account_idx": 0,
    "claude_model": "claude-opus-4-6-20260320",
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Firebase init ────────────────────────────────────────────────────────────

if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app(credentials.ApplicationDefault())
    except Exception:
        firebase_admin.initialize_app()

_db = firestore.client()
_ACCOUNTS_COLLECTION = "marketing_accounts"

# ── Account persistence (Firestore) ─────────────────────────────────────────

def _sanitize(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", name.lower().replace(" ", "_"))[:60]

@st.cache_data(ttl=10)
def load_accounts() -> list[dict]:
    docs = _db.collection(_ACCOUNTS_COLLECTION).order_by("created").stream()
    return [{"_id": d.id, **d.to_dict()} for d in docs]

def save_account(data: dict, doc_id: str | None = None):
    if doc_id:
        _db.collection(_ACCOUNTS_COLLECTION).document(doc_id).set(data)
    else:
        _db.collection(_ACCOUNTS_COLLECTION).add(data)
    load_accounts.clear()

def delete_account(doc_id: str):
    _db.collection(_ACCOUNTS_COLLECTION).document(doc_id).delete()
    load_accounts.clear()

def save_accounts(accounts: list[dict]):
    """Bulk save — used by legacy code paths."""
    for a in accounts:
        doc_id = a.pop("_id", None)
        if doc_id:
            _db.collection(_ACCOUNTS_COLLECTION).document(doc_id).set(a)
    load_accounts.clear()

def get_active_account() -> dict | None:
    accounts = load_accounts()
    if not accounts: return None
    idx = st.session_state.get("active_account_idx", 0)
    return accounts[min(idx, len(accounts) - 1)]

def _token() -> str:
    a = get_active_account(); return a["access_token"] if a else ""
def _ad_account() -> str:
    a = get_active_account(); return a["ad_account_id"] if a else ""
def _business_id() -> str:
    a = get_active_account(); return a.get("business_id", "") if a else ""
def _logo_bytes() -> bytes | None:
    a = get_active_account()
    if not a: return None
    p = LOGOS_DIR / f"{_sanitize(a['name'])}.png"
    return p.read_bytes() if p.exists() else None

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown('<div class="mm-logo">Marketing Manager</div>', unsafe_allow_html=True)
    st.markdown('<div class="mm-logo-sub">Campaign Builder</div>', unsafe_allow_html=True)

    # ── Account selector ─────────────────────────────────────────────────────
    accounts = load_accounts()
    if accounts:
        st.markdown('<div class="sidebar-section">Active Account</div>', unsafe_allow_html=True)
        chosen = st.selectbox(
            "Account", options=range(len(accounts)),
            format_func=lambda i: accounts[i]["name"],
            index=min(st.session_state.active_account_idx, len(accounts) - 1),
            key="account_selector", label_visibility="collapsed",
        )
        st.session_state.active_account_idx = chosen
        acct = accounts[chosen]
        logo_path = LOGOS_DIR / f"{_sanitize(acct['name'])}.png"
        if logo_path.exists():
            st.image(str(logo_path), width=48)
        st.caption(f"`{acct.get('ad_account_id', '')}`")

    # ── Model + keys ─────────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">AI Configuration</div>', unsafe_allow_html=True)

    MODEL_OPTIONS = {
        "Claude Opus 4.6 (Max)": "claude-opus-4-6-20260320",
        "Claude Sonnet 4.6": "claude-sonnet-4-6-20260320",
    }
    selected_model = st.selectbox(
        "Model", options=list(MODEL_OPTIONS.keys()),
        index=0 if "opus" in st.session_state.claude_model else 1,
        help="Claude Max subscribers get Opus 4.6 included.",
    )
    st.session_state.claude_model = MODEL_OPTIONS[selected_model]

    # ── Status ───────────────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">Status</div>', unsafe_allow_html=True)
    keys_ok = bool(st.session_state.anthropic_key)
    acct = get_active_account()
    meta_ok = bool(acct and acct.get("access_token") and acct.get("ad_account_id"))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'AI <span class="pill {"pill-ok" if keys_ok else "pill-err"}">{"ready" if keys_ok else "missing"}</span>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'Meta <span class="pill {"pill-ok" if meta_ok else "pill-warn"}">{"linked" if meta_ok else "none"}</span>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">Safety</div>', unsafe_allow_html=True)
    st.session_state.dry_run = st.toggle("Dry-run mode", value=st.session_state.dry_run, help="Campaigns publish as PAUSED — nothing spends money.")

# ═════════════════════════════════════════════════════════════════════════════
# CLAUDE SYSTEM PROMPT
# ═════════════════════════════════════════════════════════════════════════════

CLAUDE_SYSTEM_PROMPT = """You are the world's most elite performance marketing strategist and creative director, specializing in Meta (Facebook & Instagram) advertising in 2026. You combine deep data-driven media-buying expertise with world-class creative copywriting.

## YOUR TASK
The user will provide a campaign goal/prompt and may include uploaded images or videos. They will ALWAYS include their business profile picture / logo as the FIRST image. You must produce a COMPLETE, READY-TO-PUBLISH Meta advertising campaign.

## ANALYSIS PHASE — Do all of this internally before producing output:

1. **Profile Picture / Logo Analysis** (FIRST image is always the business logo):
   - Describe the logo in exhaustive detail: colors (exact hex if you can estimate), shapes, typography style, icon elements, overall brand feel
   - Identify the brand personality conveyed by the logo
   - This logo MUST appear consistently across all generated ad creatives

2. **Uploaded Media Analysis**: For every additional image or video:
   - Describe what you see in detail
   - Rate its ad-worthiness (1-10)
   - Suggest crops, overlays, or text placements
   - Identify best Meta placement for each asset

3. **Audience Research**: Define primary/secondary audiences, Meta interest targeting, behavior targeting, lookalike sources, exclusion audiences, audience size estimates.

4. **Competitive & Market Analysis**: Competitive landscape, Meta trends 2026, positioning angles.

5. **Campaign Architecture**: Objective, budget, schedule, bid strategy, placements, optimization goal.

## OUTPUT — Return JSON with this EXACT structure:

```json
{
  "logo_analysis": {
    "description": "string",
    "brand_colors_hex": ["#hex1", "#hex2"],
    "brand_personality": "string"
  },
  "campaign": {
    "name": "string",
    "objective": "AWARENESS|TRAFFIC|ENGAGEMENT|LEADS|APP_PROMOTION|SALES",
    "special_ad_categories": [],
    "budget_type": "daily|lifetime",
    "budget_amount_cents": 2000,
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "status": "PAUSED"
  },
  "ad_sets": [
    {
      "name": "string",
      "optimization_goal": "string",
      "billing_event": "IMPRESSIONS",
      "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
      "daily_budget_cents": 1000,
      "targeting": {
        "age_min": 25, "age_max": 45,
        "genders": [1, 2],
        "geo_locations": {"countries": ["US"], "regions": [], "cities": []},
        "interests": [{"id": "6003139266461", "name": "Coffee"}],
        "behaviors": [], "excluded_interests": [],
        "custom_audiences": [], "lookalike_spec": null,
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed", "story", "reel"],
        "instagram_positions": ["stream", "story", "reels"]
      },
      "start_time": "YYYY-MM-DDTHH:MM:SS+0000",
      "end_time": "YYYY-MM-DDTHH:MM:SS+0000"
    }
  ],
  "ad_creatives": [
    {
      "variant_name": "string",
      "format": "SINGLE_IMAGE|SINGLE_VIDEO|CAROUSEL",
      "primary_text": "string",
      "headline": "string",
      "description": "string",
      "call_to_action": "SHOP_NOW|LEARN_MORE|SIGN_UP|BOOK_NOW|CONTACT_US|GET_OFFER|SEND_MESSAGE",
      "link_url": "string",
      "display_link": "string",
      "media_source": "uploaded|generate|logo_translate",
      "uploaded_media_index": null,
      "image_generation_prompt": null,
      "placement_asset_customization": {"feed_headline": "string", "story_headline": "string"}
    }
  ],
  "image_generation_requests": [
    {
      "prompt": "string — VERY detailed photorealistic prompt",
      "aspect_ratio": "1:1|9:16|16:9|4:5",
      "for_creative_index": 0,
      "negative_prompt": "cartoon, illustration, 3d render, anime, painting"
    }
  ],
  "logo_translation_requests": [
    {
      "prompt": "string — how to place the logo into a photorealistic ad scene",
      "aspect_ratio": "1:1|9:16|4:5",
      "for_creative_index": 0,
      "style_note": "string"
    }
  ],
  "ab_test_plan": {
    "test_variable": "string",
    "control": "string",
    "variants": ["string"],
    "success_metric": "string",
    "minimum_budget_per_variant_cents": 1500,
    "recommended_test_duration_days": 7
  },
  "compliance_checklist": [
    {"item": "string", "status": "pass|warning|needs_review", "note": "string"}
  ],
  "strategy_report": {
    "executive_summary": "string",
    "audience_rationale": "string",
    "creative_strategy": "string",
    "budget_rationale": "string",
    "optimization_plan": "string",
    "expected_performance": {
      "estimated_cpm_range": "string",
      "estimated_cpc_range": "string",
      "estimated_ctr_range": "string",
      "estimated_daily_reach": "string"
    }
  }
}
```

## RULES:
- Every field populated. No placeholders.
- First image is ALWAYS the business logo. Describe it in logo_analysis.
- At least 5 ad creative variants with different hooks/angles.
- At least 2-3 creatives with media_source "logo_translate".
- Budget amounts in CENTS.
- Dates realistic (starting tomorrow+).
- Return ONLY JSON — no markdown fences, no extra text."""

# ═════════════════════════════════════════════════════════════════════════════
# HELPERS — Media encoding
# ═════════════════════════════════════════════════════════════════════════════

def encode_image_bytes_for_claude(img_bytes: bytes, mime: str = "image/png") -> dict:
    b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}

def encode_media_for_claude(uploaded_file) -> dict:
    data = uploaded_file.getvalue()
    b64 = base64.standard_b64encode(data).decode("utf-8")
    mime = uploaded_file.type or "image/jpeg"
    if mime.startswith("video/"):
        return _video_to_image_block(data, uploaded_file.name)
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}

def _video_to_image_block(video_bytes: bytes, name: str) -> dict:
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=Path(name).suffix, delete=False)
        tmp.write(video_bytes); tmp.close()
        from moviepy.video.io.VideoFileClip import VideoFileClip
        clip = VideoFileClip(tmp.name); frame = clip.get_frame(0); clip.close()
        os.unlink(tmp.name)
        img = Image.fromarray(frame); buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}
    except Exception:
        return {"type": "text", "text": f"[Video: {name} — frame extraction unavailable]"}

# ═════════════════════════════════════════════════════════════════════════════
# HELPERS — Claude
# ═════════════════════════════════════════════════════════════════════════════

def call_claude(prompt: str, media_blocks: list[dict]) -> dict:
    client = anthropic.Anthropic(api_key=st.session_state.anthropic_key)
    user_content = media_blocks + [{"type": "text", "text": prompt}]
    with st.spinner("Analyzing media and building campaign strategy..."):
        response = client.messages.create(
            model=st.session_state.claude_model,
            max_tokens=16000,
            system=CLAUDE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
    raw = response.content[0].text.strip()
    if raw.startswith("```"): raw = raw.split("\n", 1)[1]
    if raw.endswith("```"): raw = raw.rsplit("```", 1)[0]
    if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw)

# ═════════════════════════════════════════════════════════════════════════════
# HELPERS — Gemini image generation + logo translation
# ═════════════════════════════════════════════════════════════════════════════

def generate_images_gemini(requests_list: list[dict]) -> list[dict]:
    client = genai.Client(api_key=st.session_state.google_key)
    results = []
    progress = st.progress(0, text="Generating assets...")
    for i, req in enumerate(requests_list):
        progress.progress(i / max(len(requests_list), 1), text=f"Image {i+1} of {len(requests_list)}")
        try:
            response = client.models.generate_images(
                model="imagen-3.0-generate-002", prompt=req["prompt"],
                config=genai_types.GenerateImagesConfig(
                    number_of_images=1, aspect_ratio=req.get("aspect_ratio", "1:1"),
                    safety_filter_level="BLOCK_ONLY_HIGH",
                ),
            )
            if response.generated_images:
                results.append({"index": req.get("for_creative_index", i), "bytes": response.generated_images[0].image.image_bytes, "prompt": req["prompt"], "aspect_ratio": req.get("aspect_ratio", "1:1")})
            else:
                results.append({"index": req.get("for_creative_index", i), "bytes": None, "prompt": req["prompt"], "error": "Filtered or empty response"})
        except Exception as e:
            results.append({"index": req.get("for_creative_index", i), "bytes": None, "prompt": req["prompt"], "error": str(e)})
        time.sleep(1)
    progress.progress(1.0, text="Done"); time.sleep(0.3); progress.empty()
    return results

def translate_logo_gemini(logo_requests: list[dict], logo_bytes: bytes) -> list[dict]:
    client = genai.Client(api_key=st.session_state.google_key)
    results = []; logo_img = Image.open(io.BytesIO(logo_bytes))
    progress = st.progress(0, text="Creating branded creatives...")
    for i, req in enumerate(logo_requests):
        progress.progress(i / max(len(logo_requests), 1), text=f"Branded asset {i+1} of {len(logo_requests)}")
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[
                    genai_types.Part.from_image(logo_img),
                    genai_types.Part.from_text(
                        f"Using the logo/brand image as reference, generate a photorealistic ad image. "
                        f"{req['prompt']} Brand identity must be clearly visible. "
                        f"Style: {req.get('style_note', 'professional advertising')}. "
                        f"Aspect ratio: {req.get('aspect_ratio', '1:1')}. Output ONLY the image."
                    ),
                ],
                config=genai_types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
            )
            img_bytes = None
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        img_bytes = part.inline_data.data; break
            if img_bytes:
                results.append({"index": req.get("for_creative_index", i), "bytes": img_bytes, "prompt": req["prompt"], "aspect_ratio": req.get("aspect_ratio", "1:1"), "type": "logo_translate"})
            else:
                fb = client.models.generate_images(model="imagen-3.0-generate-002", prompt=req["prompt"],
                    config=genai_types.GenerateImagesConfig(number_of_images=1, aspect_ratio=req.get("aspect_ratio", "1:1"), safety_filter_level="BLOCK_ONLY_HIGH"))
                if fb.generated_images:
                    results.append({"index": req.get("for_creative_index", i), "bytes": fb.generated_images[0].image.image_bytes, "prompt": req["prompt"], "aspect_ratio": req.get("aspect_ratio", "1:1"), "type": "logo_fallback"})
                else:
                    results.append({"index": req.get("for_creative_index", i), "bytes": None, "prompt": req["prompt"], "error": "No image generated", "type": "logo_translate"})
        except Exception as e:
            results.append({"index": req.get("for_creative_index", i), "bytes": None, "prompt": req["prompt"], "error": str(e), "type": "logo_translate"})
        time.sleep(2)
    progress.progress(1.0, text="Done"); time.sleep(0.3); progress.empty()
    return results

# ═════════════════════════════════════════════════════════════════════════════
# HELPERS — Meta Graph API
# ═════════════════════════════════════════════════════════════════════════════

META_API_VERSION = "v21.0"
META_BASE = f"https://graph.facebook.com/{META_API_VERSION}"

def meta_api(endpoint, method="GET", **kwargs):
    url = f"{META_BASE}/{endpoint}"
    params = kwargs.pop("params", {}); params["access_token"] = _token()
    r = (requests.get if method == "GET" else requests.post)(url, params=params, **kwargs)
    r.raise_for_status(); return r.json()

def upload_image_to_meta(image_bytes, name="ad_image.jpg"):
    act = _ad_account(); b64 = base64.standard_b64encode(image_bytes).decode()
    r = requests.post(f"{META_BASE}/{act}/adimages", params={"access_token": _token()}, data={"bytes": b64, "name": name})
    r.raise_for_status(); data = r.json()
    for key in data.get("images", {}): return data["images"][key].get("hash", "")
    return ""

def upload_video_to_meta(video_bytes, name="ad_video.mp4"):
    act = _ad_account()
    r = requests.post(f"{META_BASE}/{act}/advideos", params={"access_token": _token()}, files={"source": (name, io.BytesIO(video_bytes), "video/mp4")})
    r.raise_for_status(); return r.json().get("id", "")

def publish_campaign_to_meta(campaign_data, image_hashes, video_ids):
    log = []; act = _ad_account(); cd = campaign_data; camp = cd["campaign"]
    camp_params = {"name": camp["name"], "objective": camp["objective"],
        "status": "PAUSED" if st.session_state.dry_run else camp.get("status", "PAUSED"),
        "special_ad_categories": json.dumps(camp.get("special_ad_categories", []))}
    if camp.get("budget_type") == "daily": camp_params["daily_budget"] = camp["budget_amount_cents"]
    else: camp_params["lifetime_budget"] = camp["budget_amount_cents"]
    resp = meta_api(f"{act}/campaigns", method="POST", data=camp_params)
    campaign_id = resp["id"]; log.append(f"Campaign created: {campaign_id}")

    ad_set_ids = []
    for adset in cd["ad_sets"]:
        tgt = adset["targeting"]
        spec = {"age_min": tgt.get("age_min",18), "age_max": tgt.get("age_max",65), "genders": tgt.get("genders",[]),
            "geo_locations": tgt.get("geo_locations",{"countries":["US"]}),
            "publisher_platforms": tgt.get("publisher_platforms",["facebook","instagram"]),
            "facebook_positions": tgt.get("facebook_positions",["feed"]),
            "instagram_positions": tgt.get("instagram_positions",["stream"])}
        if tgt.get("interests"): spec["flexible_spec"] = [{"interests": tgt["interests"]}]
        params = {"name": adset["name"], "campaign_id": campaign_id,
            "optimization_goal": adset.get("optimization_goal","LINK_CLICKS"),
            "billing_event": adset.get("billing_event","IMPRESSIONS"),
            "bid_strategy": adset.get("bid_strategy","LOWEST_COST_WITHOUT_CAP"),
            "daily_budget": adset.get("daily_budget_cents",1000),
            "targeting": json.dumps(spec), "status": "PAUSED",
            "start_time": adset.get("start_time",(datetime.utcnow()+timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+0000"))}
        if adset.get("end_time"): params["end_time"] = adset["end_time"]
        resp = meta_api(f"{act}/adsets", method="POST", data=params)
        ad_set_ids.append(resp["id"]); log.append(f"Ad Set created: {resp['id']}")

    page_id = None
    try:
        bid = _business_id()
        pr = meta_api(f"{bid}/owned_pages" if bid else "me/accounts")
        if pr.get("data"): page_id = pr["data"][0]["id"]
    except Exception: pass

    for j, cr in enumerate(cd["ad_creatives"]):
        ih = image_hashes.get(j) or (list(image_hashes.values())[0] if image_hashes else None)
        oss = {"page_id": page_id or "me", "link_data": {
            "message": cr.get("primary_text",""), "link": cr.get("link_url","https://example.com"),
            "name": cr.get("headline",""), "description": cr.get("description",""),
            "call_to_action": {"type": cr.get("call_to_action","LEARN_MORE")}}}
        if ih: oss["link_data"]["image_hash"] = ih
        try:
            resp = meta_api(f"{act}/adcreatives", method="POST", data={"name": cr.get("variant_name",f"Creative {j+1}"), "object_story_spec": json.dumps(oss)})
            cid = resp["id"]; log.append(f"Creative created: {cid}")
            asid = ad_set_ids[min(j, len(ad_set_ids)-1)]
            resp = meta_api(f"{act}/ads", method="POST", data={"name": f"Ad {j+1}", "adset_id": asid, "creative": json.dumps({"creative_id": cid}), "status": "PAUSED"})
            log.append(f"Ad created: {resp['id']}")
        except Exception as e: log.append(f"Error on creative {j+1}: {e}")
    log.append(f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={act.replace('act_','')}&campaign_id={campaign_id}")
    return log

# ═════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="mm-hero">Marketing Manager</div>', unsafe_allow_html=True)
st.markdown('<div class="mm-hero-sub">AI-powered Meta Ads campaigns — from idea to live in minutes</div>', unsafe_allow_html=True)

tab_dash, tab_creatives, tab_strategy, tab_publish, tab_reports, tab_accounts = st.tabs([
    "Dashboard", "Creatives", "Strategy", "Publish", "Reports", "Accounts"
])

# ── Dashboard ────────────────────────────────────────────────────────────────

with tab_dash:
    accounts = load_accounts()
    if not accounts:
        st.info("Add a business account in the **Accounts** tab to get started.")
    else:
        account_names = [a["name"] for a in accounts] + ["+ Add new account"]
        dash_choice = st.selectbox(
            "Business account", options=range(len(account_names)),
            format_func=lambda i: account_names[i],
            index=min(st.session_state.active_account_idx, len(accounts) - 1),
            key="dash_account_selector",
        )
        if dash_choice == len(accounts):
            st.switch_page_not = True  # flag handled below
            st.info("Switch to the **Accounts** tab to add a new account.")
        else:
            st.session_state.active_account_idx = dash_choice

    acct = get_active_account()

    st.session_state.campaign_prompt = st.text_area(
        "Campaign goal", value=st.session_state.campaign_prompt, height=120,
        placeholder="Promote my Boone, NC salon's spring hair color specials to 25-45 women who love beauty, wellness, and outdoor lifestyle.",
    )

    uploaded_files = st.file_uploader(
        "Media assets", type=["jpg","jpeg","png","webp","mp4","mov"],
        accept_multiple_files=True, help="Product photos, lifestyle images, or video clips.",
    )
    if uploaded_files:
        st.session_state.uploaded_media = uploaded_files
        cols = st.columns(min(len(uploaded_files), 4))
        for i, f in enumerate(uploaded_files):
            with cols[i % len(cols)]:
                if f.type and f.type.startswith("image"): st.image(f, caption=f.name, use_container_width=True)
                else: st.video(f); st.caption(f.name)

    st.divider()
    build_clicked = st.button("Analyze & Build Full Campaign", type="primary",
        disabled=not (st.session_state.anthropic_key and st.session_state.campaign_prompt), icon=":material/auto_awesome:")

    if build_clicked:
        media_blocks, media_descriptions = [], []
        logo_bytes = _logo_bytes()
        if logo_bytes:
            media_blocks.append(encode_image_bytes_for_claude(logo_bytes, "image/png"))
            media_descriptions.append("BUSINESS LOGO (first image)")
        for f in (uploaded_files or []):
            media_blocks.append(encode_media_for_claude(f)); media_descriptions.append(f.name)
        media_note = f"\n\nUploaded media: {', '.join(media_descriptions)}. First image is the business logo." if media_descriptions else ""
        biz_name = acct["name"] if acct else "the business"
        full_prompt = f'Campaign for "{biz_name}": {st.session_state.campaign_prompt}{media_note}\n\nToday is {datetime.now().strftime("%Y-%m-%d")}. Start date tomorrow+. Return complete JSON with logo_translation_requests.'
        try:
            cd = call_claude(full_prompt, media_blocks); st.session_state.campaign_data = cd
            st.success("Campaign strategy complete.")
            gen = cd.get("image_generation_requests", [])
            if gen and st.session_state.google_key:
                st.session_state.generated_images = generate_images_gemini(gen)
            logo_req = cd.get("logo_translation_requests", [])
            if logo_req and st.session_state.google_key and logo_bytes:
                st.session_state.branded_images = translate_logo_gemini(logo_req, logo_bytes)
            st.rerun()
        except json.JSONDecodeError as e: st.error(f"JSON parse error: {e}")
        except anthropic.APIError as e: st.error(f"Claude API error: {e}")
        except Exception as e: st.error(f"Error: {e}")

    if st.session_state.campaign_data:
        cd = st.session_state.campaign_data; camp = cd.get("campaign", {})
        creatives = cd.get("ad_creatives", []); ad_sets = cd.get("ad_sets", [])
        perf = cd.get("strategy_report", {}).get("expected_performance", {})
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Budget", f"${camp.get('budget_amount_cents',0)/100:.0f}/{camp.get('budget_type','day')}")
        with m2: st.metric("Variants", len(creatives))
        with m3: st.metric("Ad Sets", len(ad_sets))
        with m4: st.metric("Objective", camp.get("objective","—").replace("_"," ").title())
        m5, m6, m7, m8 = st.columns(4)
        with m5: st.metric("Est. CPM", perf.get("estimated_cpm_range","—"))
        with m6: st.metric("Est. CPC", perf.get("estimated_cpc_range","—"))
        with m7: st.metric("Est. CTR", perf.get("estimated_ctr_range","—"))
        with m8: st.metric("Daily Reach", perf.get("estimated_daily_reach","—"))

# ── Creatives ────────────────────────────────────────────────────────────────

with tab_creatives:
    if not st.session_state.campaign_data:
        st.info("Build a campaign first from the Dashboard tab.")
    else:
        cd = st.session_state.campaign_data
        creatives = cd.get("ad_creatives", [])
        branded = st.session_state.branded_images
        generated = st.session_state.generated_images

        if branded:
            st.markdown("#### Branded creatives")
            bcols = st.columns(min(len(branded), 3))
            for i, d in enumerate(branded):
                with bcols[i % len(bcols)]:
                    if d.get("bytes"): st.image(d["bytes"], caption=f"Branded {i+1} ({d.get('aspect_ratio','1:1')})", use_container_width=True)
                    elif d.get("error"): st.warning(f"#{i+1}: {d['error']}")
                    with st.expander("Prompt"): st.code(d.get("prompt",""), language=None)
            st.divider()

        if generated:
            st.markdown("#### Generated assets")
            gcols = st.columns(min(len(generated), 3))
            for i, d in enumerate(generated):
                with gcols[i % len(gcols)]:
                    if d.get("bytes"): st.image(d["bytes"], caption=f"Generated {i+1}", use_container_width=True)
                    elif d.get("error"): st.warning(f"#{i+1}: {d['error']}")
                    with st.expander("Prompt"): st.code(d.get("prompt",""), language=None)
            st.divider()

        la = cd.get("logo_analysis", {})
        if la:
            with st.expander("Brand analysis"):
                st.markdown(f"**Description:** {la.get('description','')}")
                colors = la.get("brand_colors_hex", [])
                if colors:
                    st.markdown("**Colors:** " + " ".join(f'`{c}`' for c in colors))
                st.markdown(f"**Personality:** {la.get('brand_personality','')}")

        st.markdown("#### Ad copy variants")
        for i, cr in enumerate(creatives):
            with st.expander(f"{cr.get('variant_name', f'Variant {i+1}')} — {cr.get('format','')} / {cr.get('call_to_action','')}", expanded=(i==0)):
                c1, c2 = st.columns([2,1])
                with c1:
                    st.markdown(f"**Primary text**\n\n{cr.get('primary_text','')}")
                    st.markdown(f"**Headline:** {cr.get('headline','')}")
                    st.markdown(f"**Description:** {cr.get('description','')}")
                with c2:
                    src = cr.get('media_source','')
                    label = {"logo_translate": "Logo branded", "generate": "AI generated", "uploaded": "Uploaded"}.get(src, src)
                    st.markdown(f"**Media:** {label}")
                    st.markdown(f"**Format:** {cr.get('format','')}")
                    if cr.get("link_url"): st.markdown(f"**Link:** `{cr['link_url']}`")

# ── Strategy ─────────────────────────────────────────────────────────────────

with tab_strategy:
    if not st.session_state.campaign_data:
        st.info("Build a campaign first from the Dashboard tab.")
    else:
        cd = st.session_state.campaign_data; report = cd.get("strategy_report",{})
        camp = cd.get("campaign",{}); ad_sets = cd.get("ad_sets",[])
        ab = cd.get("ab_test_plan",{}); compliance = cd.get("compliance_checklist",[])

        with st.expander("Executive summary", expanded=True):
            st.markdown(report.get("executive_summary",""))
        with st.expander("Audience & targeting"):
            st.markdown(report.get("audience_rationale",""))
            for adset in ad_sets:
                tgt = adset.get("targeting",{})
                st.markdown(f"**{adset.get('name','')}** — Ages {tgt.get('age_min',18)}-{tgt.get('age_max',65)}, "
                    f"Platforms: {', '.join(tgt.get('publisher_platforms',[]))}")
                interests = tgt.get("interests",[])
                if interests: st.markdown("Interests: " + ", ".join(i.get("name",str(i)) if isinstance(i,dict) else str(i) for i in interests))
        with st.expander("Creative strategy"): st.markdown(report.get("creative_strategy",""))
        with st.expander("Budget & bidding"):
            st.markdown(report.get("budget_rationale",""))
            st.markdown(f"{camp.get('budget_type','daily')} — ${camp.get('budget_amount_cents',0)/100:.2f} | {camp.get('start_date','')} to {camp.get('end_date','')}")
        with st.expander("A/B testing"):
            if ab: st.markdown(f"**Variable:** {ab.get('test_variable','')}\n\n**Control:** {ab.get('control','')}\n\n**Metric:** {ab.get('success_metric','')}")
        with st.expander("Optimization plan"): st.markdown(report.get("optimization_plan",""))
        with st.expander("Compliance"):
            for item in compliance:
                icon = {"pass": "check_circle", "warning": "warning", "needs_review": "search"}.get(item.get("status",""),"help")
                st.markdown(f'<span class="mi mi-sm">{icon}</span> **{item.get("item","")}** — {item.get("note","")}', unsafe_allow_html=True)
        with st.expander("Raw JSON"): st.json(cd)

# ── Publish ──────────────────────────────────────────────────────────────────

with tab_publish:
    if not st.session_state.campaign_data:
        st.info("Build a campaign first from the Dashboard tab.")
    else:
        cd = st.session_state.campaign_data; camp = cd.get("campaign",{})
        creatives = cd.get("ad_creatives",[]); acct = get_active_account()
        if acct: st.markdown(f"Publishing as **{acct['name']}** to `{acct.get('ad_account_id','')}`")

        checks = {"Account selected": bool(acct), "Access token": bool(_token()),
            "Ad account ID": bool(_ad_account()), "Campaign data": True, "Creatives": len(creatives)>0}
        for name, ok in checks.items(): st.markdown(f":material/{'check_circle' if ok else 'cancel'}: {name}")
        all_ok = all(checks.values())

        st.divider()
        budget_daily = camp.get("budget_amount_cents",0)/100
        try: days = (datetime.strptime(camp.get("end_date",""), "%Y-%m-%d") - datetime.strptime(camp.get("start_date",""), "%Y-%m-%d")).days
        except: days = 14
        total = budget_daily * max(days,1) if camp.get("budget_type")=="daily" else budget_daily
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Daily", f"${budget_daily:.2f}")
        with c2: st.metric("Duration", f"{days}d")
        with c3: st.metric("Max spend", f"${total:.2f}")

        if st.session_state.dry_run: st.warning("Dry-run mode — campaign will be created as PAUSED.")
        else: st.error("Live mode — campaign can start spending immediately.")

        if all_ok and st.button("Publish to Meta" + (" (dry run)" if st.session_state.dry_run else ""), type="primary", icon=":material/rocket_launch:"):
            with st.spinner("Publishing..."):
                try:
                    ih, vi = {}, {}
                    for d in st.session_state.generated_images + st.session_state.branded_images:
                        if d.get("bytes"):
                            h = upload_image_to_meta(d["bytes"], f"c_{d['index']}.jpg")
                            if h: ih[d["index"]] = h
                    for i, f in enumerate(st.session_state.uploaded_media or []):
                        if f.type and f.type.startswith("image"):
                            h = upload_image_to_meta(f.getvalue(), f.name)
                            if h: ih[f"up_{i}"] = h
                        elif f.type and f.type.startswith("video"):
                            v = upload_video_to_meta(f.getvalue(), f.name)
                            if v: vi[f"up_{i}"] = v
                    log = publish_campaign_to_meta(cd, ih, vi); st.session_state.publish_log = log
                    for msg in log:
                        if "Error" in msg: st.error(msg)
                        elif "http" in msg: st.markdown(f":material/open_in_new: [{msg}]({msg})")
                        else: st.success(msg)
                except requests.HTTPError as e:
                    st.error(f"Meta API error: {e}")
                    try: st.json(e.response.json())
                    except: pass
                except Exception as e: st.error(f"Error: {e}")

# ── Reports ──────────────────────────────────────────────────────────────────

with tab_reports:
    if st.session_state.publish_log:
        st.markdown("#### Publish log")
        for msg in st.session_state.publish_log: st.markdown(msg)
        st.divider()
    if st.session_state.campaign_data:
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download campaign JSON", icon=":material/download:",
                data=json.dumps(st.session_state.campaign_data, indent=2),
                file_name=f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json", use_container_width=True)
        with c2:
            r = st.session_state.campaign_data.get("strategy_report",{})
            c = st.session_state.campaign_data.get("campaign",{})
            md = f"# {c.get('name','')} — Strategy\n\n{r.get('executive_summary','')}\n\n## Audience\n{r.get('audience_rationale','')}\n\n## Creative\n{r.get('creative_strategy','')}\n\n## Budget\n{r.get('budget_rationale','')}\n\n## Optimization\n{r.get('optimization_plan','')}"
            st.download_button("Download strategy report", icon=":material/description:",
                data=md, file_name=f"strategy_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown", use_container_width=True)
        if _token() and _ad_account():
            st.divider()
            if st.button("Fetch live insights", icon=":material/refresh:"):
                try:
                    resp = meta_api(f"{_ad_account()}/insights", params={"date_preset":"last_7d","fields":"campaign_name,impressions,clicks,spend,cpc,cpm,ctr,reach","level":"campaign"})
                    if resp.get("data"):
                        import pandas as pd; st.dataframe(pd.DataFrame(resp["data"]), use_container_width=True)
                    else: st.info("No data yet.")
                except Exception as e: st.warning(f"Could not fetch: {e}")
    else: st.info("No campaign data yet.")

# ── Accounts ─────────────────────────────────────────────────────────────────

with tab_accounts:
    accounts = load_accounts()
    if not accounts:
        st.markdown("#### Add your first business account")
        st.markdown("You need at least one Meta Business account to build and publish campaigns.")

    edit_idx = st.session_state.get("editing_account_idx", None)
    edit_acct = accounts[edit_idx] if edit_idx is not None and edit_idx < len(accounts) else None
    title = f"Edit: {edit_acct['name']}" if edit_acct else "Add new account"

    exp_icon = ":material/edit:" if edit_acct else ":material/add_circle:"
    with st.expander(title, expanded=(not accounts or edit_acct is not None), icon=exp_icon):
        with st.form("account_form", clear_on_submit=True):
            biz_name = st.text_input("Business name", value=edit_acct["name"] if edit_acct else "", placeholder="Shop Grasshopper")
            access_token = st.text_input("Meta access token (long-lived)", value=edit_acct["access_token"] if edit_acct else "", type="password")
            ad_account_id = st.text_input("Ad account ID", value=edit_acct["ad_account_id"] if edit_acct else "", placeholder="act_123456789")
            c1, c2 = st.columns(2)
            with c1: business_id = st.text_input("Business manager ID", value=edit_acct.get("business_id","") if edit_acct else "")
            with c2: app_id = st.text_input("App ID", value=edit_acct.get("app_id","") if edit_acct else "")
            logo_file = st.file_uploader("Profile picture / logo", type=["jpg","jpeg","png"], key="logo_uploader")
            if st.form_submit_button("Save account", type="primary", icon=":material/save:"):
                if not biz_name or not access_token or not ad_account_id:
                    st.error("Name, token, and ad account ID are required.")
                else:
                    data = {"name": biz_name.strip(), "access_token": access_token.strip(), "ad_account_id": ad_account_id.strip(),
                        "business_id": business_id.strip(), "app_id": app_id.strip(),
                        "created": edit_acct.get("created", datetime.now().isoformat()) if edit_acct else datetime.now().isoformat(),
                        "updated": datetime.now().isoformat()}
                    if logo_file:
                        img = Image.open(logo_file); img.thumbnail((512,512))
                        img.save(str(LOGOS_DIR / f"{_sanitize(biz_name)}.png"), "PNG"); data["has_logo"] = True
                    else: data["has_logo"] = edit_acct.get("has_logo", False) if edit_acct else False
                    doc_id = edit_acct.get("_id") if edit_acct else None
                    save_account(data, doc_id=doc_id)
                    st.session_state.pop("editing_account_idx", None)
                    st.success(f"Saved: {biz_name}"); st.rerun()

    if accounts:
        st.markdown("#### Your accounts")
        for i, a in enumerate(accounts):
            with st.container(border=True):
                c1, c2, c3 = st.columns([1,6,2])
                with c1:
                    lp = LOGOS_DIR / f"{_sanitize(a['name'])}.png"
                    if lp.exists(): st.image(str(lp), width=40)
                with c2:
                    active = " — **active**" if i == st.session_state.active_account_idx else ""
                    st.markdown(f"**{a['name']}**{active}")
                    st.caption(f"`{a.get('ad_account_id','')}` · {a.get('updated','')[:10]}")
                with c3:
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button("Edit", key=f"e_{i}", icon=":material/edit:"):
                            st.session_state.editing_account_idx = i; st.rerun()
                    with bc2:
                        if st.button("Delete", key=f"d_{i}", icon=":material/delete:"):
                            lp = LOGOS_DIR / f"{_sanitize(a['name'])}.png"
                            if lp.exists(): lp.unlink()
                            delete_account(a["_id"])
                            st.session_state.active_account_idx = max(0, st.session_state.active_account_idx - 1)
                            st.rerun()

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown('<div class="mm-footer">Marketing Manager v3 · Powered by Claude + Gemini + Meta Marketing API</div>', unsafe_allow_html=True)
