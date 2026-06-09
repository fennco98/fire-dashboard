"""Streamlit dashboard for the FIRE simulator.

Run with:  streamlit run app.py
"""

import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml
import streamlit_authenticator as stauth

from fire_sim import SimConfig, run_comparison, run_portfolio_auto


# ---------- Page setup (must be first Streamlit call) ----------

st.set_page_config(
    page_title="FIRE dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Auth helpers ----------

_DIR = os.path.dirname(os.path.abspath(__file__))
_CREDENTIALS_PATH = os.path.join(_DIR, "auth_config.yaml")

# On Streamlit Cloud the repo is read-only and auth_config.yaml is gitignored,
# so it won't exist. Detect this once and switch to secrets-based config.
_IS_CLOUD = not os.path.exists(_CREDENTIALS_PATH)

# User settings: local → project data/ dir; cloud → /tmp (writable, semi-persistent)
_DATA_DIR = "/tmp/fire_dashboard_data" if _IS_CLOUD else os.path.join(_DIR, "data")


def _load_config() -> dict:
    """Load auth config from st.secrets (Cloud) or local YAML file (local)."""
    if _IS_CLOUD:
        # Credentials and cookie config must be set in the Streamlit Cloud
        # dashboard under App settings → Secrets. See README for the format.
        creds: dict = {"usernames": {}}
        if "credentials" in st.secrets:
            for uname, udata in st.secrets["credentials"]["usernames"].items():
                creds["usernames"][uname] = {
                    "name": udata.get("name", uname),
                    "email": udata.get("email", ""),
                    "password": udata["password"],
                }
        return {
            "credentials": creds,
            "cookie": {
                "name": st.secrets["cookie"]["name"],
                "key": st.secrets["cookie"]["key"],
                "expiry_days": int(st.secrets["cookie"]["expiry_days"]),
            },
        }
    with open(_CREDENTIALS_PATH) as f:
        return yaml.safe_load(f)


def _save_config(config: dict):
    """Persist updated credentials. No-op on Cloud (secrets are read-only)."""
    if _IS_CLOUD:
        return
    with open(_CREDENTIALS_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def _load_user_settings(username: str) -> dict:
    path = os.path.join(_DATA_DIR, f"{username}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _save_user_settings(username: str, settings: dict):
    os.makedirs(_DATA_DIR, exist_ok=True)
    path = os.path.join(_DATA_DIR, f"{username}.json")
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)


# ---------- Auth setup ----------

config = _load_config()
authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    auto_hash=True,
)

# Seed widget defaults on very first load (before any auth)
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

# When a user logs in, load their saved settings (once per login)
_logged_in = st.session_state.get("authentication_status") is True
_active_user = st.session_state.get("username")
if _logged_in and _active_user != st.session_state.get("_settings_loaded_for"):
    saved = _load_user_settings(_active_user)
    for k, v in saved.items():
        st.session_state[k] = v
    st.session_state["_settings_loaded_for"] = _active_user


# ---------- Sidebar ----------

with st.sidebar:
    if _logged_in:
        st.write(f"👤 **{st.session_state['name']}**")
        authenticator.logout(button_name="Log out", location="sidebar")
    else:
        with st.expander("🔐 Log in / Create account"):
            tab_login, tab_register = st.tabs(["Log in", "Create account"])
            with tab_login:
                authenticator.login(location="main", clear_on_submit=True)
                if st.session_state.get("authentication_status") is False:
                    st.error("Incorrect username or password.")
            with tab_register:
                if _IS_CLOUD:
                    st.info(
                        "Self-registration isn't available in the deployed version. "
                        "Add your credentials via the Streamlit Cloud dashboard "
                        "(App settings → Secrets). See the README for the format."
                    )
                else:
                    st.caption("Create an account to save your inputs between sessions.")
                    try:
                        email, reg_username, reg_name = authenticator.register_user(
                            location="main",
                            captcha=False,
                            pre_authorized=None,
                            clear_on_submit=True,
                        )
                        if email:
                            config["credentials"] = authenticator.credentials
                            _save_config(config)
                            st.success(f"Account created for **{reg_name}**. Log in above.")
                    except stauth.RegisterError as e:
                        st.error(e)
                    except Exception as e:
                        st.error(f"Registration error: {e}")

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

    st.divider()
    if _logged_in and st.button("💾 Save my settings", use_container_width=True):
        _save_user_settings(_active_user, {
            "gross_devoted": st.session_state.gross_devoted,
            "years": st.session_state.years,
            "growth_rate_pct": st.session_state.growth_rate_pct,
            "marginal_now_pct": st.session_state.marginal_now_pct,
            "marginal_retire_pct": st.session_state.marginal_retire_pct,
            "cap_gains_pct": st.session_state.cap_gains_pct,
            "starting_trad_401k": st.session_state.starting_trad_401k,
            "starting_roth_401k": st.session_state.starting_roth_401k,
            "starting_trad_ira": st.session_state.starting_trad_ira,
            "starting_roth_ira": st.session_state.starting_roth_ira,
            "starting_taxable": st.session_state.starting_taxable,
            "private_stock_value": st.session_state.private_stock_value,
            "private_stock_growth_pct": st.session_state.private_stock_growth_pct,
            "fire_target": st.session_state.fire_target,
            "limit_401k": st.session_state.limit_401k,
            "limit_ira": st.session_state.limit_ira,
            "include_hsa": st.session_state.include_hsa,
            "starting_hsa": st.session_state.starting_hsa,
            "limit_hsa": st.session_state.limit_hsa,
        })
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
