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

Sign-in uses Google OAuth via Streamlit's native `st.login()`. One-time setup:

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials → **Create OAuth 2.0 Client ID** (Web app type)
   - Add your app URL as an authorised redirect URI: `https://your-app.streamlit.app/oauth2callback`
   - Also add `http://localhost:8501/oauth2callback` for local dev

2. Deploy the repo at [share.streamlit.io](https://share.streamlit.io) pointing at `app.py`

3. Open **App settings → Secrets** and paste:

```toml
[auth]
redirect_uri = "https://your-app.streamlit.app/oauth2callback"
cookie_secret = "your-random-secret"   # python3 -c "import secrets; print(secrets.token_hex(32))"

[auth.google]
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

4. Save and reboot — done. Anyone with a Google account can now sign in; no passwords to manage.

For local development, copy the same block into `.streamlit/secrets.toml` (gitignored) with `redirect_uri = "http://localhost:8501/oauth2callback"`.

> **Saved settings** persist as long as the Cloud container is running and reset on redeploy — a Streamlit Cloud limitation. Sign-in is always optional; the app works fully without it.

---

## Notes

- Returns are nominal and deterministic — no inflation adjustment or Monte Carlo simulation
- Private stock growth is your own assumption; input it as real or nominal, just be consistent with the main return slider
- Capital gains on the taxable brokerage and private stock are modeled as a single liquidation-event tax on all accrued gains
- Not financial advice — verify numbers before making real decisions
