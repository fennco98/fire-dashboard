# FIRE Dashboard

An interactive retirement account comparison dashboard. Compare Traditional and Roth 401(k)/IRA strategies, track a taxable brokerage, model private stock growth, and watch a progress bar tick toward your FIRE number.

## Requirements

- Python 3.9+
- pip

## Setup & run

1. **Clone the repo**
   ```bash
   git clone https://github.com/fennco98/fire-dashboard.git
   cd fire-dashboard
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the app**
   ```bash
   streamlit run app.py
   ```

4. **Open your browser** to http://localhost:8501 (Streamlit usually opens it automatically)

Hit `Ctrl+C` in the terminal to stop the app.

---

## What it does

- **Progress bar** — shows your current effective portfolio value vs your FIRE target, and where you'll land at retirement
- **Your portfolio tab** — stacked area chart of your primary tax-advantaged account, taxable brokerage, and private stock over time, with your FIRE target marked
- **Account comparison tab** — side-by-side projection of Traditional 401(k), Roth 401(k), Traditional IRA, and Roth IRA given the same gross income devoted to retirement

All inputs are in the sidebar: contribution amounts, current account balances, tax rates, timeline, FIRE target, and more.

---

## Notes

- Returns are nominal and deterministic — no inflation adjustment or Monte Carlo simulation
- Private stock growth is your own assumption; input it as real or nominal, just be consistent with the main return slider
- Capital gains on the taxable brokerage and private stock are modeled as a single liquidation-event tax on all accrued gains
- Not financial advice — verify numbers before making real decisions
