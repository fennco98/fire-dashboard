"""Streamlit dashboard for the FIRE simulator.

Run with:  streamlit run app.py
"""

import base64
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from fire_sim import SimConfig, run_comparison, run_portfolio_auto


# ---------- Page setup (must be first Streamlit call) ----------

st.set_page_config(
    page_title="FIRE dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Storage helpers ----------

_DIR = os.path.dirname(os.path.abspath(__file__))
# Streamlit Cloud serves from /mount/src/; that subtree is read-only.
# Fall back to /tmp which is writable (and semi-persistent within a deployment).
_IS_CLOUD = _DIR.startswith("/mount/src/")
_DATA_DIR = "/tmp/fire_dashboard_data" if _IS_CLOUD else os.path.join(_DIR, "data")


def _fernet(user_sub: str) -> Fernet:
    """Derive a Fernet key from the user's stable Google account ID.

    The key is computed at runtime from the sub claim (present only during
    an active authenticated session) and never stored anywhere. Once a
    session ends, the server has no way to reconstruct the key — meaning
    the encrypted files on disk are unreadable without the user signing in.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"fire_dashboard_v1",
        iterations=200_000,
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(user_sub.encode())))


def _load_settings(user_sub: str) -> dict:
    path = os.path.join(_DATA_DIR, f"{user_sub}.enc")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            return json.loads(_fernet(user_sub).decrypt(f.read()))
    except Exception:
        return {}


def _save_settings(user_sub: str, settings: dict):
    os.makedirs(_DATA_DIR, exist_ok=True)
    data = _fernet(user_sub).encrypt(json.dumps(settings).encode())
    with open(os.path.join(_DATA_DIR, f"{user_sub}.enc"), "wb") as f:
        f.write(data)


# ---------- Defaults ----------

_DEFAULTS = {
    "gross_devoted": 25_000,
    "years": 30,
    "growth_rate_pct": 7.0,
    "marginal_now_pct": 24.0,
    "marginal_retire_pct": 22.0,
    "cap_gains_pct": 15.0,
    "starting_trad_401k": 0,
    "starting_roth_401k": 0,
    "starting_trad_ira": 0,
    "starting_roth_ira": 0,
    "starting_taxable": 0,
    "private_stock_value": 0,
    "private_stock_growth_pct": 15.0,
    "fire_target": 2_000_000,
    "limit_401k": 23_500,
    "limit_ira": 7_000,
    "include_hsa": False,
    "starting_hsa": 0,
    "limit_hsa": 4_300,
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ---------- Login gate ----------

_signed_in = st.user.is_logged_in
_guest = st.session_state.get("guest_mode", False)

if not _signed_in and not _guest:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("🔥 FIRE Dashboard")
        st.markdown("Track your path to financial independence.")
        st.divider()

        with st.container(border=True):
            st.markdown("#### 🔒 Your data stays yours")
            st.markdown(
                """
Signing in with Google lets you save and restore your inputs across sessions.
Here's exactly what that means for your privacy:

- **End-to-end encryption.** Your saved inputs are encrypted using a key
  derived from your unique Google account ID — a key that only exists in
  memory while you're actively signed in. Once you sign out, that key is
  gone. The encrypted file on disk is unreadable without you signing back in.
- **We cannot read your data.** Because the encryption key is never stored —
  only derived on demand from your live session — even the operator of this
  app has no way to decrypt your saved inputs.
- **No passwords stored.** Sign-in is handled entirely by Google. We never
  see or store your Google password.
- **Minimal data.** We store nothing except the encrypted blob of inputs you
  explicitly save. No name, no email, no usage logs.

You can also use the app without signing in — your inputs will work fine for
the current session, just won't be remembered next time.
                """
            )

        st.divider()
        st.login("google")
        st.button(
            "Continue without signing in",
            on_click=lambda: st.session_state.update({"guest_mode": True}),
            use_container_width=True,
            type="secondary",
        )
    st.stop()


# ---------- Load saved settings on first sign-in ----------

if _signed_in:
    _sub = st.user.sub
    if _sub != st.session_state.get("_loaded_for"):
        for k, v in _load_settings(_sub).items():
            st.session_state[k] = v
        st.session_state["_loaded_for"] = _sub


# ---------- Sidebar ----------

with st.sidebar:
    if _signed_in:
        st.write(f"👤 **{st.user.name}**")
        st.button("Sign out", on_click=st.logout, use_container_width=True)
    else:
        st.caption("👤 Using as guest — inputs won't be saved.")
        if st.button("Sign in with Google", use_container_width=True):
            st.session_state.pop("guest_mode", None)
            st.rerun()

    st.divider()
    st.header("Your inputs")

    st.subheader("Contributions & timeline")
    gross_devoted = st.number_input(
        "Annual gross income to invest ($)",
        min_value=0, step=1_000, key="gross_devoted",
        help="Pre-tax dollars devoted to retirement per year. Auto-allocated: "
             "401(k) first, then Roth IRA, then taxable overflow.",
    )
    years = st.slider("Years until retirement", 1, 50, key="years")
    growth_rate = st.slider(
        "Annual nominal return (%)", 0.0, 15.0, step=0.5, key="growth_rate_pct",
        help="~10% historical US stock nominal return; ~7% real (inflation-adjusted).",
    ) / 100

    st.subheader("Tax rates")
    marginal_now = st.slider(
        "Marginal rate today (%)", 0.0, 50.0, step=0.5, key="marginal_now_pct") / 100
    marginal_retire = st.slider(
        "Marginal rate at withdrawal (%)", 0.0, 50.0, step=0.5, key="marginal_retire_pct",
        help="Set lower than today if you expect less income in retirement.",
    ) / 100
    cap_gains_rate = st.slider(
        "Long-term capital gains rate (%)", 0.0, 25.0, step=0.5, key="cap_gains_pct",
        help="Applied to taxable brokerage and private stock gains at sale.",
    ) / 100

    st.subheader("Current account balances")
    starting_trad_401k = st.number_input(
        "Traditional 401(k) ($)", min_value=0, step=1_000, key="starting_trad_401k")
    starting_roth_401k = st.number_input(
        "Roth 401(k) ($)", min_value=0, step=1_000, key="starting_roth_401k")
    starting_trad_ira = st.number_input(
        "Traditional IRA ($)", min_value=0, step=1_000, key="starting_trad_ira")
    starting_roth_ira = st.number_input(
        "Roth IRA ($)", min_value=0, step=1_000, key="starting_roth_ira")

    st.subheader("Taxable brokerage")
    starting_taxable = st.number_input(
        "Current balance ($)", min_value=0, step=1_000, key="starting_taxable",
        help="Overflow from the annual gross devoted spills here automatically.",
    )

    st.subheader("Private stock / equity")
    private_stock_value = st.number_input(
        "Current value ($)", min_value=0, step=10_000, key="private_stock_value")
    private_stock_growth = st.slider(
        "Expected annual growth (%)", 0.0, 50.0, step=0.5, key="private_stock_growth_pct",
        help="Your own assumption. Real or nominal — be consistent with the return slider.",
    ) / 100

    st.subheader("FIRE target")
    fire_target = st.number_input(
        "Target retirement portfolio ($)",
        min_value=0, step=100_000, key="fire_target",
        help="Common starting point: 25× annual expenses (4% rule).",
    )

    st.subheader("Account limits")
    limit_401k = st.number_input(
        "401(k) employee limit ($)", step=500, key="limit_401k")
    limit_ira = st.number_input("IRA limit ($)", step=500, key="limit_ira")

    st.subheader("Optional")
    include_hsa = st.checkbox("Include HSA", key="include_hsa",
        help="Triple-tax-free for qualified medical expenses. Requires HDHP.")
    starting_hsa = st.number_input(
        "HSA current balance ($)", min_value=0, step=500, key="starting_hsa",
        disabled=not include_hsa)
    limit_hsa = st.number_input(
        "HSA limit ($)", step=100, key="limit_hsa", disabled=not include_hsa)

    if _signed_in:
        st.divider()
        if st.button("💾 Save my settings", use_container_width=True):
            _save_settings(st.user.sub, {k: st.session_state[k] for k in _DEFAULTS})
            st.success("Settings saved!")


# ---------- Build config & run ----------

cfg = SimConfig(
    gross_devoted=float(gross_devoted),
    annual_growth_rate=growth_rate,
    marginal_tax_now=marginal_now,
    marginal_tax_retirement=marginal_retire,
    capital_gains_rate=cap_gains_rate,
    years=years,
    starting_trad_401k=float(starting_trad_401k),
    starting_roth_401k=float(starting_roth_401k),
    starting_trad_ira=float(starting_trad_ira),
    starting_roth_ira=float(starting_roth_ira),
    starting_hsa=float(starting_hsa),
    starting_taxable=float(starting_taxable),
    private_stock_value=float(private_stock_value),
    private_stock_growth=private_stock_growth,
    limit_401k=float(limit_401k),
    limit_ira=float(limit_ira),
    limit_hsa=float(limit_hsa),
    include_hsa=include_hsa,
)

portfolio, alloc = run_portfolio_auto(cfg)

current_total = sum(r.effective_balance[0] for r in portfolio)
projected_total = sum(r.effective_balance[-1] for r in portfolio)
progress_now = current_total / fire_target if fire_target > 0 else 0.0
progress_proj = projected_total / fire_target if fire_target > 0 else 0.0


# ---------- Progress bar ----------

st.title("FIRE retirement progress")

col_a, col_b, col_c = st.columns(3)
col_a.metric(
    "Portfolio today (effective)",
    f"${current_total:,.0f}",
    help="Sum of current account balances after estimated withdrawal taxes.",
)
col_b.metric(
    f"Projected at year {years}",
    f"${projected_total:,.0f}",
    delta=f"{progress_proj:.1%} of target",
    delta_color="normal",
)
col_c.metric("FIRE target", f"${fire_target:,.0f}")

st.progress(min(progress_now, 1.0), text=f"Today: {progress_now:.1%} of FIRE target")

if progress_proj >= 1.0:
    st.success(
        f"On this path you hit your FIRE target before year {years}. "
        "Consider adjusting the timeline slider to find your exact date."
    )
else:
    gap = fire_target - projected_total
    st.caption(
        f"Projected gap at year {years}: **${gap:,.0f}** "
        f"({1 - progress_proj:.1%} of target remaining)."
    )

with st.expander("Annual contribution breakdown"):
    alloc_rows = [("Traditional 401(k)", alloc["trad_401k"], "Pre-tax")]
    if cfg.include_hsa:
        alloc_rows.append(("HSA", alloc["hsa"], "Pre-tax"))
    alloc_rows.append(("Roth IRA", alloc["roth_ira"], "Post-tax"))
    alloc_rows.append(("Taxable brokerage (overflow)", alloc["taxable"], "Post-tax"))
    df_alloc = pd.DataFrame(alloc_rows, columns=["Account", "Annual amount", "Tax treatment"])
    df_alloc["Annual amount"] = df_alloc["Annual amount"].apply(lambda x: f"${x:,.0f}")
    st.dataframe(df_alloc, hide_index=True, use_container_width=True)
    st.caption(
        "Allocation order: 401(k) to limit → HSA to limit (if enabled) → "
        "Roth IRA to limit → taxable brokerage with any remainder."
    )

st.divider()


# ---------- Tabs ----------

tab_portfolio, tab_comparison = st.tabs(["Your portfolio", "Account type comparison"])

years_axis = list(range(years + 1))

with tab_portfolio:
    st.subheader("Effective balance over time — your portfolio")
    st.caption(
        "Stacked area showing how each piece of your portfolio grows. "
        "Annual gross devoted is auto-allocated: 401(k) first, then Roth IRA, "
        "then taxable brokerage with any overflow. "
        "Balances are after estimated withdrawal / capital-gains taxes."
    )

    fig_stack = go.Figure()
    for r in portfolio:
        fig_stack.add_trace(go.Scatter(
            x=years_axis,
            y=r.effective_balance,
            mode="lines",
            name=r.name,
            stackgroup="one",
            hovertemplate="Year %{x}<br>$%{y:,.0f}<extra>%{fullData.name}</extra>",
        ))
    if fire_target > 0:
        fig_stack.add_hline(
            y=fire_target,
            line_dash="dash",
            line_color="green",
            annotation_text=f"FIRE target ${fire_target:,.0f}",
            annotation_position="top left",
        )
    fig_stack.update_layout(
        xaxis_title="Years",
        yaxis_title="Effective balance ($)",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=20, b=0),
        height=480,
    )
    st.plotly_chart(fig_stack, use_container_width=True)

    df_port = pd.DataFrame([{
        "Account": r.name,
        "Annual contribution": f"${r.annual_contribution:,.0f}",
        "Balance today": f"${r.effective_balance[0]:,.0f}",
        f"Effective balance at year {years}": f"${r.effective_balance[-1]:,.0f}",
    } for r in portfolio])
    total_row = pd.DataFrame([{
        "Account": "Total",
        "Annual contribution": f"${sum(r.annual_contribution for r in portfolio):,.0f}",
        "Balance today": f"${current_total:,.0f}",
        f"Effective balance at year {years}": f"${projected_total:,.0f}",
    }])
    st.dataframe(pd.concat([df_port, total_row], ignore_index=True),
                 hide_index=True, use_container_width=True)


with tab_comparison:
    st.subheader("Tax-advantaged account type comparison")
    st.caption(
        "Projects all four account types independently from the same gross "
        "income devoted — the fair apples-to-apples view of which strategy "
        "yields the most given your tax rates and timeline."
    )

    comparison = run_comparison(cfg)

    fig_cmp = go.Figure()
    for r in comparison:
        fig_cmp.add_trace(go.Scatter(
            x=years_axis,
            y=r.effective_balance,
            mode="lines",
            name=r.name,
            hovertemplate="Year %{x}<br>$%{y:,.0f}<extra>%{fullData.name}</extra>",
        ))
    fig_cmp.update_layout(
        xaxis_title="Years",
        yaxis_title="Effective balance ($)",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=20, b=0),
        height=480,
    )
    st.plotly_chart(fig_cmp, use_container_width=True)

    with st.expander("Show nominal (pre-tax) balances"):
        fig_pretax = go.Figure()
        for r in comparison:
            fig_pretax.add_trace(go.Scatter(
                x=years_axis,
                y=r.pretax_balance,
                mode="lines",
                name=r.name,
                hovertemplate="Year %{x}<br>$%{y:,.0f}<extra>%{fullData.name}</extra>",
            ))
        fig_pretax.update_layout(
            xaxis_title="Years",
            yaxis_title="Nominal balance ($)",
            yaxis_tickformat="$,.0f",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=20, b=0),
            height=400,
        )
        st.plotly_chart(fig_pretax, use_container_width=True)

    best = max(comparison, key=lambda r: r.effective_balance[-1])
    df_cmp = pd.DataFrame([{
        "Account": r.name,
        "Annual contribution": f"${r.annual_contribution:,.0f}",
        f"Nominal balance at year {years}": f"${r.pretax_balance[-1]:,.0f}",
        "Effective (after-tax) balance": f"${r.effective_balance[-1]:,.0f}",
        "vs best": (
            "best" if r.name == best.name
            else f"{r.effective_balance[-1] - best.effective_balance[-1]:+,.0f}"
        ),
    } for r in comparison])
    st.dataframe(df_cmp, hide_index=True, use_container_width=True)


# ---------- Caveats ----------

with st.expander("Assumptions and known limitations"):
    st.markdown(
        """
- **Portfolio view auto-allocates** gross income devoted in tax-efficiency order: 401(k) → HSA (if enabled) → Roth IRA → taxable brokerage overflow. The comparison tab feeds the full gross amount to each account type independently.
- **Returns are constant, nominal, and deterministic.** No inflation adjustment, no volatility, no sequence-of-returns risk. Use ~7% for results in today's dollars.
- **Private stock growth** is your own assumption — real or nominal, just be consistent with the main return slider.
- **Single tax bracket approximation.** Real brackets are progressive; marginal rate is an approximation.
- **Roth IRA income phase-outs not modeled.** Above ~$165k single / ~$246k MFJ (2025).
- **Traditional IRA deductibility not modeled.** May be non-deductible above certain incomes with a workplace plan.
- **Capital gains on taxable brokerage** are modeled as a single liquidation-event tax at year N. No annual tax drag.
- **No RMDs, no early-withdrawal penalties, no Roth conversion ladders, no 72(t).**
        """
    )

st.caption(
    "Personal-project simulator, not financial advice. Verify numbers before making real decisions."
)
