# config/settings.py

# --- Zerodha API Credentials ---
# IMPORTANT: Replace these with your actual Kite Connect API key and secret.
# It is strongly recommended to use environment variables or a secure vault in production.
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
# After the first successful login, the request token will be exchanged for an access token.
# The access token will be stored here to be used for subsequent API calls.
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"  # This will be generated automatically

# --- Portfolio & Capital Allocation ---
TOTAL_CAPITAL = 2500000  # ₹25 Lakhs

# Capital allocation percentages for each strategy
CAPITAL_ALLOCATION = {
    "SHORT_STRANGLE_HEDGE": 0.35,  # 35% = ₹8.75L
    "DEBIT_SPREAD": 0.20,          # 20% = ₹5L
    "IRON_CONDOR": 0.20,           # 20% = ₹5L
    "EVENT_STRADDLE": 0.10,        # 10% = ₹2.5L
    "BUFFER": 0.15                 # 15% = ₹3.75L
}

# --- Global Risk Management ---
PORTFOLIO_MAX_DD_MONTHLY = 100000  # ₹1,00,000

# Per-strategy stop-loss limits
STRATEGY_MAX_LOSS = {
    "SHORT_STRANGLE_HEDGE": 70000,
    "DEBIT_SPREAD": 50000,
    "IRON_CONDOR": 30000,
    "EVENT_STRADDLE": 30000
}

# --- Telegram Alerts ---
TELEGRAM_API_TOKEN = "YOUR_TELEGRAM_API_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# --- Database ---
DATABASE_URL = "sqlite:///trading_app.db"

# --- Other Settings ---
NIFTY_SYMBOL = "NIFTY 50"
LOT_SIZE = 25
