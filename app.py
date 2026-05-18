"""Streamlit dashboard for the FIRE simulator.

Run with:  streamlit run app.py
"""

import dataclasses

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fire_sim import ACCOUNT_NAMES, SimConfig, run_comparison, run_portfolio


# ---------- Page setup ----------

st.set_page_config(
    page_title="FIRE dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Sidebar ----------

with st.sidebar:
    st.header("Your inputs")

    st.subheader("Contributions & timeline")
    primary_account = st.selectbox(
        "Primary tax-advantaged account",
        ACCOUNT_NAMES,
        help="Which account type you're actively contributing to. "
             "Used for the progress bar and portfolio chart.",
    )
    gross_devoted = st.number_input(
        "Annual gross income to invest ($)",
        min_value=0, value=25_000, step=1_000,
        help="Pre-tax dollars devoted to retirement per year. The simulator "
             "handles tax timing for each account type.",
    )
    years = st.slider("Years until retirement", 1, 50, 30)
    growth_rate = st.slider(
        "Annual nominal return (%)", 0.0, 15.0, 7.0, 0.5,
        help="~10% historical US stock nominal return; ~7% if you want results "
             "in today's dollars (real return).",
    ) / 100

    st.subheader("Tax rates")
    marginal_now = st.slider("Marginal rate today (%)", 0.0, 50.0, 24.0, 0.5) / 100
    marginal_retire = st.slider(
        "Marginal rate at withdrawal (%)", 0.0, 50.0, 22.0, 0.5,
        help="Set lower than today if you expect less income in retirement.",
    ) / 100
    cap_gains_rate = st.slider(
        "Long-term capital gains rate (%)", 0.0, 25.0, 15.0, 0.5,
        help="Applied to gains in the taxable brokerage and private stock "
             "at the point of withdrawal/sale.",
    ) / 100

    st.subheader("Current account balances")
    starting_trad_401k = st.number_input(
        "Traditional 401(k) balance ($)", min_value=0, value=0, step=1_000)
    starting_roth_401k = st.number_input(
        "Roth 401(k) balance ($)", min_value=0, value=0, step=1_000)
    starting_trad_ira = st.number_input(
        "Traditional IRA balance ($)", min_value=0, value=0, step=1_000)
    starting_roth_ira = st.number_input(
        "Roth IRA balance ($)", min_value=0, value=0, step=1_000)

    st.subheader("Taxable brokerage")
    starting_taxable = st.number_input(
        "Current balance ($)", min_value=0, value=0, step=1_000,
        key="taxable_start")
    taxable_annual = st.number_input(
        "Annual contribution ($)", min_value=0, value=0, step=1_000,
        help="Post-tax dollars added to the taxable account each year.",
        key="taxable_annual")

    st.subheader("Private stock / equity")
    private_stock_value = st.number_input(
        "Current value ($)", min_value=0, value=0, step=10_000)
    private_stock_growth = st.slider(
        "Expected annual growth (%)", 0.0, 50.0, 15.0, 0.5,
        help="Your own assumption for this holding. "
             "Input as real or nominal — just be consistent with the "
             "nominal return slider above.",
    ) / 100

    st.subheader("FIRE target")
    fire_target = st.number_input(
        "Target retirement portfolio ($)",
        min_value=0, value=2_000_000, step=100_000,
        help="Common starting point: 25× your annual expenses (4% rule). "
             "Adjust to your situation.",
    )

    st.subheader("Account limits")
    limit_401k = st.number_input("401(k) employee limit ($)", value=23_500, step=500)
    limit_ira = st.number_input("IRA limit ($)", value=7_000, step=500)

    st.subheader("Optional")
    include_hsa = st.checkbox(
        "Include HSA",
        value=False,
        help="Triple-tax-free if spent on qualified medical expenses. "
             "Requires a high-deductible health plan.",
    )
    starting_hsa = st.number_input(
        "HSA current balance ($)", min_value=0, value=0, step=500,
        disabled=not include_hsa)
    limit_hsa = st.number_input(
        "HSA limit ($)", value=4_300, step=100, disabled=not include_hsa)


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
    taxable_annual=float(taxable_annual),
    private_stock_value=float(private_stock_value),
    private_stock_growth=private_stock_growth,
    limit_401k=float(limit_401k),
    limit_ira=float(limit_ira),
    limit_hsa=float(limit_hsa),
    include_hsa=include_hsa,
)

portfolio = run_portfolio(cfg, primary_account)

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

st.divider()


# ---------- Tabs: portfolio chart vs comparison ----------

tab_portfolio, tab_comparison = st.tabs(["Your portfolio", "Account type comparison"])

years_axis = list(range(years + 1))

with tab_portfolio:
    st.subheader(f"Effective balance over time — your portfolio")
    st.caption(
        "Stacked area showing how each piece of your portfolio grows. "
        "Balances shown are after estimated withdrawal / capital-gains taxes."
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

    # Portfolio table
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
        "Compares the four account types using your inputs, including current "
        "balances. All are fed the same pre-tax gross income; the simulator "
        "handles tax timing per account."
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
- **Gross income devoted is held constant** across all comparison account types; the simulator handles tax timing.
- **Returns are constant, nominal, and deterministic.** No inflation adjustment, no volatility, no sequence-of-returns risk. Use ~7% if you want results in today's dollars.
- **Private stock growth** is your own assumption and may be real or nominal — be consistent with the main return slider.
- **Single tax bracket approximation.** Real brackets are progressive; marginal rate is an approximation.
- **Roth IRA income phase-outs not modeled.** Above ~$165k single / ~$246k MFJ (2025) you can't contribute directly.
- **Traditional IRA deductibility not modeled.** If you have a workplace plan and earn above the phase-out, your contributions may be non-deductible.
- **Capital gains on the taxable brokerage** are modeled as a single liquidation-event tax on all accrued gains at year N. No annual tax drag on dividends or short-term gains.
- **Private stock effective balance** assumes LTCG applied to all appreciation over current value at a future liquidity event.
- **No RMDs, no early-withdrawal penalties, no Roth conversion ladders, no 72(t).**
        """
    )

st.caption(
    "Personal-project simulator, not financial advice. Verify numbers before making real decisions."
)
