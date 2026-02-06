# -------------------------
# Install dependencies only if needed
# -------------------------
# !pip install pandas numpy requests ccxt --quiet

# -------------------------
# Imports
# -------------------------
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime
import ccxt
import os

# -------------------------
# User Settings
# -------------------------
slPercent = 1.5
tpPercent = 3.0
lookback = 5
rsi_period = 14
rsi_lookback = 5
symbol = 'BTC/USDT'
trade_amount = 0.001
simulate_only = True  # Set False to place real trades

# -------------------------
# Pionex API from environment variables
# -------------------------
api_key = os.environ.get('PIONEX_API_KEY')
api_secret = os.environ.get('PIONEX_API_SECRET')

pionex = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
})

# -------------------------
# Track executed signals
# -------------------------
executed_signals = set()

# -------------------------
# RSI function
# -------------------------
def compute_rsi(close, period=rsi_period):
    close = np.array(close)
    deltas = np.diff(close)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(close)
    rsi[:period] = 50
    for i in range(period, len(close)):
        delta = deltas[i - 1]
        upval = max(delta, 0)
        downval = -min(delta, 0)
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100 - 100 / (1 + rs)
    return rsi

# -------------------------
# Main loop: fetch candles, detect signals, execute
# -------------------------
while True:
    try:
        # Fetch latest 30 days candles from CoinGecko
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc"
        params = {"vs_currency": "usd", "days": "30"}
        response = requests.get(url, params=params)
        data = response.json()
        df = pd.DataFrame(data, columns=["Time", "Open", "High", "Low", "Close"])
        df["Time"] = pd.to_datetime(df["Time"], unit='ms')
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = df[col].astype(float)

        # Compute RSI
        df["RSI"] = compute_rsi(df["Close"])

        # Detect pivot lows
        pivot_lows = []
        for i in range(lookback, len(df) - lookback):
            window = df["Low"].iloc[i - lookback:i + lookback + 1]
            if df["Low"].iloc[i] == min(window):
                pivot_lows.append(i)

        # Detect bullish divergence
        signals = []
        for idx in pivot_lows:
            if idx < rsi_lookback:
                continue
            prev_idx = pivot_lows[pivot_lows.index(idx) - 1] if pivot_lows.index(idx) > 0 else None
            if prev_idx is None:
                continue
            price_low_now = df["Low"].iloc[idx]
            price_low_prev = df["Low"].iloc[prev_idx]
            rsi_now = df["RSI"].iloc[idx]
            rsi_prev = df["RSI"].iloc[prev_idx]
            if price_low_now < price_low_prev and rsi_now > rsi_prev and rsi_now < 30:
                entry_price = df["Close"].iloc[idx]
                stop_loss = entry_price * (1 - slPercent / 100)
                take_profit = entry_price * (1 + tpPercent / 100)
                signal_id = df["Time"].iloc[idx]
                signals.append({
                    "id": signal_id,
                    "Time": df["Time"].iloc[idx],
                    "Entry": entry_price,
                    "StopLoss": round(stop_loss, 2),
                    "TakeProfit": round(take_profit, 2),
                    "RSI": round(rsi_now, 2)
                })

        # Execute Signals
        for s in signals:
            if s['id'] not in executed_signals:
                executed_signals.add(s['id'])
                if simulate_only:
                    print(f"Simulated BUY order: Entry={s['Entry']}, SL={s['StopLoss']}, TP={s['TakeProfit']} at {s['Time']}")
                else:
                    order = pionex.create_market_buy_order(symbol, trade_amount)
                    print("Market buy order placed:", order)

        # Wait 1 hour before next check
        print(f"Waiting 1 hour... ({datetime.now()})")
        time.sleep(3600)

    except Exception as e:
        print("Error occurred:", e)
        print("Retrying in 5 minutes...")
        time.sleep(300)
