import os

# Coins to track (CoinGecko IDs)
COINS = [
    "bitcoin",       # BTC
    "ethereum",      # ETH
    "ripple",        # XRP
    "binancecoin",   # BNB
    "solana",        # SOL
    "cardano",       # ADA
    "dogecoin",      # DOGE
    "tron",          # TRX
    "avalanche-2",   # AVAX
    "chainlink",     # LINK
]

# Fetch interval in seconds
INTERVAL = 60

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "crypto.db")

# Model path
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
