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

## Deploying to Streamlit Community Cloud

The app runs on Streamlit Cloud with one setup step: adding secrets via the dashboard.

1. Deploy the repo at [share.streamlit.io](https://share.streamlit.io) pointing at `app.py`
2. Open **App settings → Secrets** and paste the following, filling in your values:

```toml
[cookie]
name = "fire_dashboard"
key = "your-random-secret-key"   # generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
expiry_days = 30

[credentials.usernames.yourname]
name = "Your Name"
email = ""
password = "$2b$12$..."   # bcrypt hash — see below
```

To hash your password, run locally:
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

3. Save and reboot the app — done.

> **Self-registration** works locally but is disabled on Cloud (Streamlit Secrets are read-only from app code). Add new users by editing the Secrets in the dashboard.

> **Saved settings** on Cloud persist as long as the app container is running. They'll reset if the app restarts or redeploys — this is a Streamlit Cloud limitation.

---

## Notes

- Returns are nominal and deterministic — no inflation adjustment or Monte Carlo simulation
- Private stock growth is your own assumption; input it as real or nominal, just be consistent with the main return slider
- Capital gains on the taxable brokerage and private stock are modeled as a single liquidation-event tax on all accrued gains
- Not financial advice — verify numbers before making real decisions
