"""
WQαLab — WorldQuant BRAIN Alpha Research Tool
Real BRAIN API integration: live settings, real simulations, full record sets.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import json
import time
from urllib.parse import urljoin

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import streamlit as st

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="WQαLab — BRAIN",
    page_icon="⚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

BRAIN_URL = "https://api.worldquantbrain.com"

# ── STYLES ────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@700;800&display=swap');

html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace; }
.stApp { background-color: #080c10; color: #c9d1d9; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; letter-spacing: -0.5px; }

[data-testid="metric-container"] {
    background: #0d1117; border: 1px solid #1e2d3d;
    border-radius: 6px; padding: 12px !important;
}
[data-testid="stMetricValue"] { color: #00e5ff !important; }

.stTabs [data-baseweb="tab-list"] { background: #0d1117; border-bottom: 1px solid #1e2d3d; gap: 2px; }
.stTabs [data-baseweb="tab"] {
    background: transparent; color: #6b7fa0;
    font-family: 'JetBrains Mono', monospace; font-size: 12px;
    border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] {
    color: #00e5ff !important;
    border-bottom-color: #00e5ff !important;
    background: transparent !important;
}
.stButton > button {
    background: #00e5ff; color: #000; border: none;
    font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600;
    border-radius: 6px;
}
.stButton > button:hover { background: #33eeff; }
.stTextArea textarea, .stTextInput input, .stNumberInput input {
    background: #0d1117 !important; border: 1px solid #1e2d3d !important;
    color: #c9d1d9 !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important; border-radius: 6px !important;
}
[data-baseweb="select"] > div { background: #0d1117 !important; border-color: #1e2d3d !important; }
.stDataFrame { border: 1px solid #1e2d3d; border-radius: 6px; }
.streamlit-expanderHeader {
    background: #0d1117 !important; border: 1px solid #1e2d3d !important;
    border-radius: 6px !important; color: #c9d1d9 !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 12px !important;
}
.streamlit-expanderContent {
    background: #0d1117 !important; border: 1px solid #1e2d3d !important;
    border-top: none !important;
}
.stAlert { border-radius: 6px !important; font-family: 'JetBrains Mono', monospace !important; font-size: 12px !important; }
.stSidebar { background: #0d1117 !important; border-right: 1px solid #1e2d3d; }
.section-title {
    font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 700;
    color: #c9d1d9; margin-bottom: 8px;
    border-left: 3px solid #00e5ff; padding-left: 10px;
}
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────

for k, v in {
    "session":           None,
    "authenticated":     False,
    "sim_options":       None,
    "neutralizations":   [],
    "regions":           [],
    "universes":         [],
    "delays":            [],
    "last_alpha_id":     None,
    "last_alpha_result": None,
    "last_pnl":          None,
    "last_yearly":       None,
    "last_checks":       None,
    "last_self_corr":    None,
    "last_prod_corr":    None,
    "datasets_df":       None,
    "datafields_df":     None,
    "operators_df":      None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Guard: server restart wipes session object but may leave authenticated=True
if st.session_state["authenticated"] and st.session_state["session"] is None:
    st.session_state["authenticated"] = False
    st.warning("Session expired — please log in again.")

# ── API HELPERS ───────────────────────────────────────────────────────────────

def get_session() -> requests.Session:
    return st.session_state["session"]

def brain_get(path: str, params: dict = None):
    return get_session().get(BRAIN_URL + path, params=params, timeout=30)

def brain_post(path: str, data):
    return get_session().post(BRAIN_URL + path, json=data, timeout=30)

def brain_options(path: str):
    return get_session().options(BRAIN_URL + path, timeout=30)

def poll_simulation(progress_url: str, status_ph, bar_ph):
    s = get_session()
    steps = [
        "Queueing simulation…", "Loading universe data…",
        "Computing cross-sectional signals…", "Applying neutralization…",
        "Applying truncation & pasteurization…", "Calculating PnL…",
        "Running performance metrics…", "Finalizing alpha…",
    ]
    i = 0
    while True:
        r = s.get(progress_url, timeout=30)
        retry = r.headers.get("Retry-After", 0)
        pct = r.json().get("progress", 0) or min(0.9, i * 0.12)
        bar_ph.progress(float(pct))
        status_ph.markdown(f"`{steps[min(i, len(steps) - 1)]}`")
        if float(retry) == 0:
            break
        i += 1
        time.sleep(float(retry))
    bar_ph.progress(1.0)
    status_ph.markdown("`Simulation complete ✓`")
    return r.json()

def fetch_recordset(alpha_id: str, name: str) -> pd.DataFrame:
    s = get_session()
    while True:
        r = s.get(f"{BRAIN_URL}/alphas/{alpha_id}/recordsets/{name}", timeout=30)
        if "retry-after" in r.headers:
            time.sleep(float(r.headers["retry-after"]))
        else:
            break
    data = r.json()
    if not data.get("records"):
        return pd.DataFrame()
    cols = [p["name"] for p in data["schema"]["properties"]]
    return pd.DataFrame(data["records"], columns=cols)

def load_sim_options():
    r = brain_options("/simulations")
    if r.status_code != 200:
        st.warning(f"OPTIONS returned {r.status_code}: {r.text[:200]}")
        return
    data = r.json()
    st.session_state["sim_options"] = data
    try:
        children    = data["actions"]["POST"]["settings"]["children"]
        inst_choices = children.get("instrumentType", {}).get("choices", [])
        instruments  = [c["value"] for c in inst_choices]

        region_raw = children.get("region",        {}).get("choices", {})
        univ_raw   = children.get("universe",       {}).get("choices", {})
        delay_raw  = children.get("delay",          {}).get("choices", {})
        neut_raw   = children.get("neutralization", {}).get("choices", {})

        region_by_inst = {}
        univ_by        = {}
        delay_by       = {}
        neut_by        = {}

        for inst in instruments:
            region_by_inst[inst] = [
                c["value"]
                for c in region_raw.get("instrumentType", {}).get(inst, [])
            ]
            for reg in region_by_inst[inst]:
                univ_by[(inst, reg)] = [
                    c["value"] for c in
                    univ_raw.get("instrumentType", {}).get(inst, {}).get("region", {}).get(reg, [])
                ]
                delay_by[(inst, reg)] = [
                    c["value"] for c in
                    delay_raw.get("instrumentType", {}).get(inst, {}).get("region", {}).get(reg, [])
                ]
                neut_by[(inst, reg)] = [
                    c["value"] for c in
                    neut_raw.get("instrumentType", {}).get(inst, {}).get("region", {}).get(reg, [])
                ]

        st.session_state["_instruments"]          = instruments
        st.session_state["_region_by_inst"]       = region_by_inst
        st.session_state["_univ_by_inst_region"]  = univ_by
        st.session_state["_delay_by_inst_region"] = delay_by
        st.session_state["_neut_by_inst_region"]  = neut_by
    except Exception as e:
        st.warning(f"Could not fully parse OPTIONS: {e}")

def get_regions(inst="EQUITY"):
    return st.session_state.get("_region_by_inst", {}).get(
        inst, ["USA","EUR","ASI","CHN","JPN","KOR","TWN","IND","BRA"])

def get_universes(inst="EQUITY", region="USA"):
    return st.session_state.get("_univ_by_inst_region", {}).get(
        (inst, region), ["TOP3000","TOP2000","TOP1000","TOP500"])

def get_delays(inst="EQUITY", region="USA"):
    raw = st.session_state.get("_delay_by_inst_region", {}).get((inst, region), [1, 0])
    return [int(d) for d in raw]

def get_neutralizations(inst="EQUITY", region="USA"):
    return st.session_state.get("_neut_by_inst_region", {}).get(
        (inst, region), ["SUBINDUSTRY","INDUSTRY","SECTOR","MARKET","NONE"])

def format_checks(checks_raw) -> pd.DataFrame:
    if not checks_raw:
        return pd.DataFrame()
    return pd.DataFrame([{
        "Check":   c.get("name", c.get("test", "")),
        "Result":  c.get("result", "UNKNOWN"),
        "Value":   c.get("value"),
        "Limit":   c.get("limit"),
        "Message": c.get("message", ""),
    } for c in checks_raw])

def color_result(val):
    colors = {"PASS": "#00e676", "FAIL": "#ff1744", "WARN": "#ffb300"}
    c = colors.get(str(val).upper(), "#6b7fa0")
    return f"color: {c}; font-weight: 700;"

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — THE ONLY AUTH BLOCK IN THIS FILE
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown('<div class="section-title">🔐 BRAIN Login</div>', unsafe_allow_html=True)

    email    = st.text_input("Email",    placeholder="you@example.com", type="default")
    password = st.text_input("Password", placeholder="••••••••••",       type="password")

    if st.button("Connect to BRAIN", use_container_width=True):
        if not email or not password:
            st.error("Enter both email and password.")
        else:
            with st.spinner("Connecting…"):
                try:
                    s = requests.Session()
                    s.auth = (email, password)
                    r = s.post(BRAIN_URL + "/authentication", timeout=20)

                    # Always show raw response so you can see exactly what BRAIN returns
                    st.write(f"**Status:** `{r.status_code}`")
                    st.write(f"**Body:** `{r.text[:400]}`")

                    if r.status_code == 201:
                        st.session_state["session"]       = s
                        st.session_state["authenticated"] = True
                        st.success("✓ Connected!")
                        with st.spinner("Loading simulation options…"):
                            load_sim_options()
                        st.rerun()

                    elif r.status_code == 401:
                        hdr = r.headers.get("WWW-Authenticate", "")
                        if hdr == "persona":
                            biometric_url = urljoin(r.url, r.headers["Location"])
                            st.session_state["session"] = s
                            st.warning(
                                "Biometric auth required on your account.\n\n"
                                f"[Tap here to complete it]({biometric_url})\n\n"
                                "Then tap **Connect to BRAIN** again."
                            )
                        else:
                            st.error(f"Incorrect email or password.")
                    else:
                        st.error(f"Unexpected: {r.status_code} — {r.text[:200]}")

                except requests.exceptions.Timeout:
                    st.error("Timed out — BRAIN API unreachable from Streamlit Cloud.")
                except requests.exceptions.ConnectionError as e:
                    st.error(f"Connection error: {e}")
                except Exception as e:
                    st.error(f"{type(e).__name__}: {e}")

    if st.session_state["authenticated"]:
        st.markdown("---")
        st.success("🟢 Connected")
        try:
            rc = brain_get("/authentication")
            if rc.status_code == 200:
                expiry = rc.json().get("token", {}).get("expiry", "?")
                st.caption(f"Token expires in: {expiry}s")
        except Exception:
            pass
        if st.button("Reload Settings", use_container_width=True):
            with st.spinner("Reloading…"):
                load_sim_options()
            st.success("Refreshed.")

    st.markdown("---")
    st.markdown('<div class="section-title">💡 Quick Refs</div>', unsafe_allow_html=True)
    st.markdown("""
**Submission thresholds:**
- Sharpe ≥ 1.25
- Fitness ≥ 1.0
- Turnover 1–70%
- Self-corr < 0.7
- Prod-corr < 0.7

**Delay 1** = next-day open
**Delay 0** = same-day (rare)
""")

# ── UNAUTHENTICATED LANDING ───────────────────────────────────────────────────

if not st.session_state["authenticated"]:
    st.markdown('<h1 style="color:#00e5ff;font-family:Syne,sans-serif;">WQαLab</h1>',
                unsafe_allow_html=True)
    st.markdown("**Enter your WorldQuant BRAIN credentials in the sidebar to get started.**")
    st.info("All simulations run on the real BRAIN platform. Credentials are stored in this session only.")
    st.stop()

# ── MAIN TABS ─────────────────────────────────────────────────────────────────

t_sim, t_result, t_data, t_batch, t_api = st.tabs([
    "⚗  Simulate",
    "📊  Results",
    "🗄  Data Explorer",
    "⚡  Batch Simulate",
    "⌥  API Builder",
])

# ════════════════════════════════════════════════════════════════════
# TAB 1 — SIMULATE
# ════════════════════════════════════════════════════════════════════
with t_sim:
    st.markdown('<div class="section-title">Alpha Simulator</div>', unsafe_allow_html=True)
    st.caption("Settings loaded live from BRAIN. All values reflect what the API actually accepts.")

    col_l, col_r = st.columns([5, 4])

    with col_l:
        expr = st.text_area(
            "Alpha Expression (FASTEXPR)",
            value=st.session_state.get("carry_expr", "-group_rank(ebit / capex, subindustry)"),
            height=120,
        )
        alpha_type = st.radio("Alpha Type", ["REGULAR", "SUPER"], horizontal=True)
        if alpha_type == "SUPER":
            combo_expr     = st.text_area("Combo Expression",     height=70, placeholder="combo expression")
            selection_expr = st.text_area("Selection Expression", height=70, placeholder="selection expression")

    with col_r:
        inst = "EQUITY"
        c1, c2 = st.columns(2)
        regions  = get_regions(inst)
        region   = c1.selectbox("Region",   regions,
                                 index=regions.index("USA") if "USA" in regions else 0)
        univs    = get_universes(inst, region)
        universe = c2.selectbox("Universe", univs,
                                 index=univs.index("TOP3000") if "TOP3000" in univs else 0)
        delays   = get_delays(inst, region)
        delay    = c1.selectbox("Delay",    delays, index=0)
        decay    = c2.number_input("Decay", 0, 20, 0)

        neuts          = get_neutralizations(inst, region)
        neutralization = st.selectbox(
            "Neutralization", neuts,
            index=neuts.index("SUBINDUSTRY") if "SUBINDUSTRY" in neuts else 0,
            help="Fetched live from BRAIN OPTIONS /simulations",
        )

        c3, c4 = st.columns(2)
        truncation  = c3.number_input("Truncation", 0.01, 0.20, 0.08, step=0.01)
        test_period = c4.selectbox("Test Period",
            ["P4Y","P1Y","P2Y","P3Y","P5Y","P1Y6M"],
            format_func=lambda x: {"P4Y":"4Y","P1Y":"1Y","P2Y":"2Y","P3Y":"3Y","P5Y":"5Y","P1Y6M":"18M"}[x])

        c5, c6 = st.columns(2)
        pasteurization = c5.selectbox("Pasteurization", ["ON","OFF"])
        nan_handling   = c6.selectbox("NaN Handling",   ["OFF","ON"])
        max_trade      = c5.selectbox("Max Trade",      ["ON","OFF"])
        unit_handling  = c6.selectbox("Unit Handling",  ["VERIFY"])

        if alpha_type == "SUPER":
            c7, c8 = st.columns(2)
            sel_handling = c7.selectbox("Selection Handling", ["POSITIVE","NEGATIVE"])
            sel_limit    = c8.number_input("Selection Limit", 10, 1000, 100)

    settings = {
        "instrumentType": inst,
        "region":         region,
        "universe":       universe,
        "delay":          int(delay),
        "decay":          int(decay),
        "neutralization": neutralization,
        "truncation":     float(truncation),
        "pasteurization": pasteurization,
        "testPeriod":     test_period,
        "unitHandling":   unit_handling,
        "nanHandling":    nan_handling,
        "maxTrade":       max_trade,
        "language":       "FASTEXPR",
        "visualization":  False,
    }
    if alpha_type == "REGULAR":
        payload = {"type": "REGULAR", "settings": settings, "regular": expr}
    else:
        payload = {
            "type": "SUPER",
            "settings": {**settings, "selectionHandling": sel_handling, "selectionLimit": int(sel_limit)},
            "combo": combo_expr, "selection": selection_expr,
        }

    with st.expander("📋 View JSON Payload"):
        st.code(json.dumps(payload, indent=2), language="json")

    run_col, opt_col = st.columns([2, 3])
    run_sim      = run_col.button("▶  Run Simulation", use_container_width=True)
    fetch_checks = opt_col.checkbox("Fetch submission checks", value=True)
    fetch_corr   = opt_col.checkbox("Fetch correlations",      value=False)
    fetch_pnl_cb = opt_col.checkbox("Fetch PnL record set",    value=True)
    fetch_yearly = opt_col.checkbox("Fetch yearly stats",      value=True)

    if run_sim:
        status_ph = st.empty()
        bar_ph    = st.empty()
        status_ph.markdown("`Submitting to BRAIN…`")
        bar_ph.progress(0.0)

        resp = brain_post("/simulations", payload)

        if resp.status_code not in (200, 201):
            st.error(f"Simulation rejected {resp.status_code}: {resp.text}")
        else:
            progress_url = BRAIN_URL + resp.headers.get("Location", "")
            sim_result   = poll_simulation(progress_url, status_ph, bar_ph)

            if sim_result.get("status") == "ERROR":
                st.error(f"Simulation error: {sim_result.get('message', 'unknown')}")
                if "location" in sim_result:
                    loc = sim_result["location"]
                    st.code(f"Error at line {loc.get('line')}, col {loc.get('start')}")
            else:
                alpha_id = sim_result.get("alpha")
                st.session_state["last_alpha_id"] = alpha_id

                result = brain_get(f"/alphas/{alpha_id}").json()
                st.session_state["last_alpha_result"] = result

                for k in ["last_pnl","last_yearly","last_checks","last_self_corr","last_prod_corr"]:
                    st.session_state[k] = None

                if fetch_pnl_cb:
                    with st.spinner("Fetching PnL…"):
                        st.session_state["last_pnl"] = fetch_recordset(alpha_id, "pnl")

                if fetch_yearly:
                    with st.spinner("Fetching yearly stats…"):
                        st.session_state["last_yearly"] = fetch_recordset(alpha_id, "yearly-stats")

                if fetch_checks:
                    with st.spinner("Fetching checks…"):
                        ck = brain_get(f"/alphas/{alpha_id}/check")
                        if ck.status_code == 200:
                            st.session_state["last_checks"] = format_checks(
                                ck.json().get("is", {}).get("checks", []))

                if fetch_corr:
                    with st.spinner("Fetching self-correlation…"):
                        sc = brain_get(f"/alphas/{alpha_id}/correlations/self")
                        if sc.status_code == 200 and sc.json().get("records"):
                            cols = [p["name"] for p in sc.json()["schema"]["properties"]]
                            st.session_state["last_self_corr"] = pd.DataFrame(
                                sc.json()["records"], columns=cols)
                    with st.spinner("Fetching prod-correlation…"):
                        pc = brain_get(f"/alphas/{alpha_id}/correlations/prod")
                        if pc.status_code == 200 and pc.json().get("records"):
                            cols = [p["name"] for p in pc.json()["schema"]["properties"]]
                            st.session_state["last_prod_corr"] = pd.DataFrame(
                                pc.json()["records"], columns=cols)

                st.success(f"✓ Done — Alpha ID: `{alpha_id}` — see **Results** tab.")

# ════════════════════════════════════════════════════════════════════
# TAB 2 — RESULTS
# ════════════════════════════════════════════════════════════════════
with t_result:
    st.markdown('<div class="section-title">Alpha Results</div>', unsafe_allow_html=True)

    result   = st.session_state.get("last_alpha_result")
    alpha_id = st.session_state.get("last_alpha_id")

    manual_id = st.text_input("Load any Alpha ID", value=alpha_id or "", placeholder="paste alpha id")
    if st.button("Load Alpha", key="load_alpha_btn") and manual_id:
        with st.spinner("Fetching…"):
            r = brain_get(f"/alphas/{manual_id}")
            if r.status_code == 200:
                st.session_state["last_alpha_result"] = r.json()
                st.session_state["last_alpha_id"]     = manual_id
                result   = r.json()
                alpha_id = manual_id
            else:
                st.error(f"Could not fetch alpha: {r.status_code}")

    if not result:
        st.info("Run a simulation first, or paste an alpha ID above.")
        st.stop()

    is_data  = result.get("is", {})
    sharpe   = is_data.get("sharpe",   0)
    fitness  = is_data.get("fitness",  0)
    turnover = is_data.get("turnover", 0)
    returns  = is_data.get("returns",  0)
    margin   = is_data.get("margin",   0)
    draw     = is_data.get("drawdown", 0)

    st.markdown(f"#### Alpha `{alpha_id}`")
    st.caption(f"Expression: `{result.get('regular', {}).get('code', '')}`")

    m = st.columns(6)
    m[0].metric("Sharpe",   f"{sharpe:.3f}",       delta="≥ 1.25")
    m[1].metric("Fitness",  f"{fitness:.3f}",       delta="≥ 1.0")
    m[2].metric("Turnover", f"{turnover*100:.1f}%", delta="1–70%")
    m[3].metric("Returns",  f"{returns*100:.2f}%")
    m[4].metric("Margin",   f"{margin*100:.2f}%")
    m[5].metric("Drawdown", f"{draw*100:.2f}%")

    train = result.get("train")
    test  = result.get("test")
    if train or test:
        st.markdown("##### In-Sample vs Out-of-Sample")
        rows = []
        for period, label in [(is_data, "In-Sample"), (train, "Train"), (test, "Test")]:
            if period:
                rows.append({
                    "Period":   label,
                    "Sharpe":   round(period.get("sharpe",   0), 3),
                    "Fitness":  round(period.get("fitness",  0), 3),
                    "Turnover": f"{period.get('turnover', 0)*100:.1f}%",
                    "Returns":  f"{period.get('returns',  0)*100:.2f}%",
                    "Drawdown": f"{period.get('drawdown', 0)*100:.2f}%",
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    checks_df = st.session_state.get("last_checks")
    raw_checks = result.get("is", {}).get("checks", [])
    if checks_df is None and raw_checks:
        checks_df = format_checks(raw_checks)
    if checks_df is not None and not checks_df.empty:
        st.markdown("##### Submission Checks")
        st.dataframe(
            checks_df.style.applymap(color_result, subset=["Result"]),
            use_container_width=True, hide_index=True,
        )

    pnl_df = st.session_state.get("last_pnl")
    if (pnl_df is None or pnl_df.empty) and st.button("📈 Fetch PnL", key="fetch_pnl_btn"):
        with st.spinner("Fetching PnL…"):
            st.session_state["last_pnl"] = fetch_recordset(alpha_id, "pnl")
            pnl_df = st.session_state["last_pnl"]

    if pnl_df is not None and not pnl_df.empty:
        st.markdown("##### Cumulative PnL")
        date_col = pnl_df.columns[0]
        pnl_col  = "pnl" if "pnl" in pnl_df.columns else pnl_df.columns[1]
        final    = pnl_df[pnl_col].iloc[-1]
        color    = "#00e676" if final > 0 else "#ff1744"
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pnl_df[date_col], y=pnl_df[pnl_col],
            fill="tozeroy",
            fillcolor=f"rgba({'0,230,118' if final > 0 else '255,23,68'},0.08)",
            line=dict(color=color, width=1.8),
            hovertemplate="%{x}: %{y:.4f}<extra></extra>",
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="#1e2d3d", line_width=1)
        fig.update_layout(
            height=260, margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor="#080c10", plot_bgcolor="#080c10",
            font=dict(family="JetBrains Mono", size=10, color="#6b7fa0"),
            xaxis=dict(showgrid=False, color="#3a4a60"),
            yaxis=dict(showgrid=True, gridcolor="#131a22", color="#3a4a60"),
            title=dict(
                text=f"Cumulative PnL  {'▲' if final > 0 else '▼'} {final:.4f}",
                font=dict(size=11, color=color), x=0,
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

    yearly_df = st.session_state.get("last_yearly")
    if (yearly_df is None or yearly_df.empty) and st.button("📅 Fetch Yearly Stats", key="fetch_yearly_btn"):
        with st.spinner("Fetching…"):
            st.session_state["last_yearly"] = fetch_recordset(alpha_id, "yearly-stats")
            yearly_df = st.session_state["last_yearly"]

    if yearly_df is not None and not yearly_df.empty:
        st.markdown("##### Yearly Statistics")
        st.dataframe(yearly_df, use_container_width=True, hide_index=True)
        if "year" in yearly_df.columns and "sharpe" in yearly_df.columns:
            fig2 = px.bar(yearly_df, x="year", y="sharpe",
                          color_discrete_sequence=["#00e5ff"])
            fig2.add_hline(y=1.25, line_dash="dash", line_color="#ffb300",
                           annotation_text="1.25 threshold",
                           annotation_font_color="#ffb300")
            fig2.update_layout(
                height=220, margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="#080c10", plot_bgcolor="#080c10",
                font=dict(family="JetBrains Mono", size=10, color="#6b7fa0"),
                xaxis=dict(showgrid=False, color="#3a4a60"),
                yaxis=dict(showgrid=True, gridcolor="#131a22", color="#3a4a60"),
                title=dict(text="Sharpe by Year", font=dict(size=11, color="#6b7fa0"), x=0),
            )
            st.plotly_chart(fig2, use_container_width=True)

    col_sc, col_pc = st.columns(2)
    with col_sc:
        self_corr = st.session_state.get("last_self_corr")
        if self_corr is not None and not self_corr.empty:
            st.markdown("##### Self-Correlation")
            st.dataframe(self_corr.head(10), use_container_width=True, hide_index=True)
        elif st.button("Fetch Self-Correlation", key="sc_btn"):
            with st.spinner():
                r = brain_get(f"/alphas/{alpha_id}/correlations/self")
                if r.status_code == 200 and r.json().get("records"):
                    cols = [p["name"] for p in r.json()["schema"]["properties"]]
                    st.session_state["last_self_corr"] = pd.DataFrame(r.json()["records"], columns=cols)
                    st.rerun()
                else:
                    st.info("No self-correlation data yet.")

    with col_pc:
        prod_corr = st.session_state.get("last_prod_corr")
        if prod_corr is not None and not prod_corr.empty:
            st.markdown("##### Prod-Correlation")
            st.dataframe(prod_corr.head(10), use_container_width=True, hide_index=True)
        elif st.button("Fetch Prod-Correlation", key="pc_btn"):
            with st.spinner():
                r = brain_get(f"/alphas/{alpha_id}/correlations/prod")
                if r.status_code == 200 and r.json().get("records"):
                    cols = [p["name"] for p in r.json()["schema"]["properties"]]
                    st.session_state["last_prod_corr"] = pd.DataFrame(r.json()["records"], columns=cols)
                    st.rerun()
                else:
                    st.info("No production correlation data.")

    st.markdown("##### Additional Record Sets")
    extra_sets = [
        "daily-pnl","turnover","coverage","coverage-by-sector","coverage-by-industry",
        "pnl-by-sector","pnl-by-industry","pnl-by-capitalization",
        "sharpe-by-sector","sharpe-by-industry","sharpe-by-capitalization",
        "average-size-by-sector","average-size-by-industry","average-size-by-capitalization",
    ]
    chosen_rs = st.selectbox("Choose record set", extra_sets)
    if st.button("Fetch Record Set", key="extra_rs"):
        with st.spinner(f"Fetching {chosen_rs}…"):
            df = fetch_recordset(alpha_id, chosen_rs)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("Empty or unavailable for this alpha.")

    with st.expander("📄 Raw Alpha JSON"):
        st.json(result)

# ════════════════════════════════════════════════════════════════════
# TAB 3 — DATA EXPLORER
# ════════════════════════════════════════════════════════════════════
with t_data:
    st.markdown('<div class="section-title">Data Explorer</div>', unsafe_allow_html=True)
    st.caption("Live datasets, data fields, and operators from BRAIN.")

    d1, d2, d3, d4 = st.columns(4)
    de_inst   = d1.selectbox("Instrument", ["EQUITY"],                   key="de_inst")
    de_region = d2.selectbox("Region",     get_regions(),                key="de_region")
    de_univ   = d3.selectbox("Universe",   get_universes(region=de_region), key="de_univ")
    de_delay  = d4.selectbox("Delay",      get_delays(region=de_region), key="de_delay")

    c_ds, c_df, c_op = st.columns(3)

    if c_ds.button("Load Datasets", use_container_width=True):
        with st.spinner("Fetching datasets…"):
            r = brain_get("/data-sets", {
                "instrumentType": de_inst, "region": de_region,
                "delay": int(de_delay), "universe": de_univ,
            })
            if r.status_code == 200:
                results = r.json().get("results", [])
                st.session_state["datasets_df"] = pd.json_normalize(results) if results else pd.DataFrame()
            else:
                st.error(f"Error {r.status_code}")

    if c_df.button("Load Data Fields", use_container_width=True):
        with st.spinner("Fetching data fields…"):
            r = brain_get("/data-fields", {
                "instrumentType": de_inst, "region": de_region,
                "delay": int(de_delay), "universe": de_univ, "limit": 100,
            })
            if r.status_code == 200:
                results = r.json().get("results", [])
                st.session_state["datafields_df"] = pd.json_normalize(results) if results else pd.DataFrame()
            else:
                st.error(f"Error {r.status_code}")

    if c_op.button("Load Operators", use_container_width=True):
        with st.spinner("Fetching operators…"):
            r = brain_get("/operators")
            if r.status_code == 200:
                df = pd.DataFrame(r.json())
                if "scope" in df.columns:
                    df = df.explode("scope").reset_index(drop=True)
                st.session_state["operators_df"] = df
            else:
                st.error(f"Error {r.status_code}")

    for key, label, show_cols in [
        ("datasets_df",   "Datasets",    ["id","name","description","category.name","alphaCount","userCount"]),
        ("datafields_df", "Data Fields", ["id","name","description","type","dataset.name","category"]),
        ("operators_df",  "Operators",   ["name","description","scope","type","syntax"]),
    ]:
        df = st.session_state.get(key)
        if df is not None and not df.empty:
            st.markdown(f"##### {label} ({len(df)})")
            search = st.text_input(f"Search {label.lower()}", "", key=f"search_{key}")
            if search:
                mask = df.apply(lambda c: c.astype(str).str.contains(search, case=False)).any(axis=1)
                df = df[mask]
            visible = [c for c in show_cols if c in df.columns] or list(df.columns)
            st.dataframe(df[visible], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("##### Live Neutralization Options per Region")
    if st.button("Show All Neutralizations"):
        neut_data = st.session_state.get("_neut_by_inst_region", {})
        if neut_data:
            rows = [
                {"Instrument": inst, "Region": reg,
                 "Neutralizations": ", ".join(str(n) for n in neuts)}
                for (inst, reg), neuts in neut_data.items()
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.warning("Click 'Reload Settings' in the sidebar first.")

# ════════════════════════════════════════════════════════════════════
# TAB 4 — BATCH SIMULATE
# ════════════════════════════════════════════════════════════════════
with t_batch:
    st.markdown('<div class="section-title">Batch Simulator</div>', unsafe_allow_html=True)
    st.caption("Run up to 10 alphas at once via BRAIN's multi-simulation endpoint.")
    st.info("One expression per line. All alphas share the same settings.")

    batch_exprs = st.text_area(
        "Alpha Expressions (one per line)",
        value="-group_rank(ebit / capex, subindustry)\n-rank(ts_sum(returns, 5))\nrank(adv5 / adv20)",
        height=150,
    )

    bc1, bc2, bc3, bc4 = st.columns(4)
    b_region = bc1.selectbox("Region",        get_regions(),                        key="b_region")
    b_univ   = bc2.selectbox("Universe",       get_universes(region=b_region),       key="b_univ")
    b_delay  = bc3.selectbox("Delay",          get_delays(region=b_region),          key="b_delay")
    b_neut   = bc4.selectbox("Neutralization", get_neutralizations(region=b_region), key="b_neut")

    bc5, bc6 = st.columns(2)
    b_decay  = bc5.number_input("Decay",      0, 20, 0,    key="b_decay")
    b_trunc  = bc6.number_input("Truncation", 0.01, 0.20, 0.08, step=0.01, key="b_trunc")
    b_period = st.selectbox("Test Period", ["P4Y","P1Y","P2Y","P5Y"], key="b_period")

    if st.button("⚡ Run Batch Simulation"):
        lines = [l.strip() for l in batch_exprs.strip().split("\n") if l.strip()]
        if not lines:
            st.error("Enter at least one expression.")
        elif len(lines) > 10:
            st.error("Maximum 10 expressions per batch.")
        else:
            batch_settings = {
                "instrumentType": "EQUITY", "region": b_region, "universe": b_univ,
                "delay": int(b_delay), "decay": int(b_decay), "neutralization": b_neut,
                "truncation": float(b_trunc), "pasteurization": "ON",
                "testPeriod": b_period, "unitHandling": "VERIFY",
                "nanHandling": "OFF", "maxTrade": "ON",
                "language": "FASTEXPR", "visualization": False,
            }
            payloads = [{"type": "REGULAR", "settings": batch_settings, "regular": e} for e in lines]
            batch_status = st.empty()
            batch_bar    = st.empty()
            resp = brain_post("/simulations", payloads[0] if len(payloads) == 1 else payloads)

            if resp.status_code not in (200, 201):
                st.error(f"Batch rejected {resp.status_code}: {resp.text}")
            else:
                progress_url = BRAIN_URL + resp.headers.get("Location", "")
                poll_result  = poll_simulation(progress_url, batch_status, batch_bar)
                children     = poll_result.get("children", [])
                if poll_result.get("alpha"):
                    children = [poll_result["alpha"]]

                if not children:
                    st.error("No results returned. Check the BRAIN platform directly.")
                else:
                    batch_rows = []
                    prog = st.progress(0)
                    for i, child_id in enumerate(children):
                        cr   = brain_get(f"/simulations/{child_id}")
                        a_id = cr.json().get("alpha") if cr.status_code == 200 else child_id
                        if a_id:
                            ar = brain_get(f"/alphas/{a_id}")
                            if ar.status_code == 200:
                                is_d = ar.json().get("is", {})
                                batch_rows.append({
                                    "Expression": lines[i] if i < len(lines) else a_id,
                                    "Alpha ID":   a_id,
                                    "Sharpe":     round(is_d.get("sharpe",   0), 3),
                                    "Fitness":    round(is_d.get("fitness",  0), 3),
                                    "Turnover":   f"{is_d.get('turnover', 0)*100:.1f}%",
                                    "Returns":    f"{is_d.get('returns',  0)*100:.2f}%",
                                    "Drawdown":   f"{is_d.get('drawdown', 0)*100:.2f}%",
                                })
                        prog.progress((i + 1) / len(children))

                    if batch_rows:
                        st.markdown("#### Batch Results")
                        st.dataframe(pd.DataFrame(batch_rows), use_container_width=True, hide_index=True)
                    else:
                        st.warning("Could not retrieve results. Check the Results tab manually.")

# ════════════════════════════════════════════════════════════════════
# TAB 5 — API BUILDER
# ════════════════════════════════════════════════════════════════════
with t_api:
    st.markdown('<div class="section-title">API Builder</div>', unsafe_allow_html=True)
    st.caption("Execute raw API calls and generate copy-ready Python scripts.")

    endpoint = st.selectbox("Endpoint", [
        "OPTIONS /simulations",
        "GET /alphas/<id>",
        "GET /alphas/<id>/check",
        "GET /alphas/<id>/correlations/self",
        "GET /alphas/<id>/correlations/prod",
        "GET /alphas/<id>/recordsets",
        "GET /alphas/<id>/recordsets/<n>",
        "GET /data-sets",
        "GET /data-fields",
        "GET /operators",
        "GET /authentication",
        "GET /users/self/activities/diversity",
    ])

    api_alpha_id = st.text_input("Alpha ID", st.session_state.get("last_alpha_id", ""))
    api_rs_name  = st.text_input("Record set name", "pnl")
    api_region   = st.selectbox("Region (data endpoints)",   get_regions(),                    key="api_region")
    api_univ     = st.selectbox("Universe (data endpoints)", get_universes(region=api_region), key="api_univ")

    if st.button("▶ Execute Request"):
        with st.spinner("Calling BRAIN…"):
            ep = endpoint
            if "OPTIONS"           in ep: r = brain_options("/simulations")
            elif "recordsets/<n>"  in ep: r = brain_get(f"/alphas/{api_alpha_id}/recordsets/{api_rs_name}")
            elif "recordsets"      in ep: r = brain_get(f"/alphas/{api_alpha_id}/recordsets")
            elif "check"           in ep: r = brain_get(f"/alphas/{api_alpha_id}/check")
            elif "correlations/self" in ep: r = brain_get(f"/alphas/{api_alpha_id}/correlations/self")
            elif "correlations/prod" in ep: r = brain_get(f"/alphas/{api_alpha_id}/correlations/prod")
            elif "<id>"            in ep: r = brain_get(f"/alphas/{api_alpha_id}")
            elif "data-sets"       in ep: r = brain_get("/data-sets",   {"instrumentType":"EQUITY","region":api_region,"universe":api_univ,"delay":1})
            elif "data-fields"     in ep: r = brain_get("/data-fields", {"instrumentType":"EQUITY","region":api_region,"universe":api_univ,"delay":1,"limit":50})
            elif "operators"       in ep: r = brain_get("/operators")
            elif "diversity"       in ep: r = brain_get("/users/self/activities/diversity", {"grouping":"region,delay,dataCategory"})
            else:                         r = brain_get("/authentication")

            st.markdown(f"**Status:** `{r.status_code}`")
            try:    st.json(r.json())
            except: st.code(r.text)

    st.markdown("---")
    st.markdown("##### Python Script Generator")
    sc_expr   = st.text_input("Expression",    "-group_rank(ebit / capex, subindustry)")
    sc_region = st.selectbox("Region",         get_regions(),                        key="sc_region")
    sc_univ   = st.selectbox("Universe",        get_universes(region=sc_region),       key="sc_univ")
    sc_neut   = st.selectbox("Neutralization",  get_neutralizations(region=sc_region), key="sc_neut")

    st.code(f'''import requests, time

BRAIN_URL = "https://api.worldquantbrain.com"
s = requests.Session()
s.auth = ("your@email.com", "your_password")
assert s.post(BRAIN_URL + "/authentication").status_code == 201

# Fetch live settings (neutralizations, regions, universes)
opts  = s.options(BRAIN_URL + "/simulations").json()
neuts = opts["actions"]["POST"]["settings"]["children"]["neutralization"]["choices"]
print("Neutralizations:", neuts)

payload = {{
    "type": "REGULAR",
    "settings": {{
        "instrumentType": "EQUITY", "region": "{sc_region}",
        "universe": "{sc_univ}", "delay": 1, "decay": 0,
        "neutralization": "{sc_neut}", "truncation": 0.08,
        "pasteurization": "ON", "testPeriod": "P4Y",
        "unitHandling": "VERIFY", "nanHandling": "OFF",
        "maxTrade": "ON", "language": "FASTEXPR", "visualization": False,
    }},
    "regular": "{sc_expr}",
}}

resp = s.post(BRAIN_URL + "/simulations", json=payload)
url  = BRAIN_URL + resp.headers["Location"]

while True:
    r = s.get(url)
    if float(r.headers.get("Retry-After", 0)) == 0:
        break
    time.sleep(float(r.headers["Retry-After"]))

alpha_id = r.json()["alpha"]
result   = s.get(BRAIN_URL + f"/alphas/{{alpha_id}}").json()
is_data  = result["is"]
print(f"Sharpe:   {{is_data['sharpe']:.3f}}")
print(f"Fitness:  {{is_data['fitness']:.3f}}")
print(f"Turnover: {{is_data['turnover']*100:.1f}}%")

for c in s.get(BRAIN_URL + f"/alphas/{{alpha_id}}/check").json()["is"]["checks"]:
    print(f"  {{c['name']}}: {{c['result']}}")
''', language="python")
