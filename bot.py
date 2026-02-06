# =============================================
# BTC/USDT 1H RSI Divergence Bot (Railway-ready)
# Futures Version with 15x Leverage
# =============================================

import ccxt
import os
import time
import pandas as pd
from datetime import datetime

# -----------------------------
# Configuration
# -----------------------------
simulate_only = True       # True = only simulate, False = live trades
market_type = 'futures'    # 'spot' or 'futures'
symbol = 'BTC/USDT'
trade_amount = 100         # USD per trade
desired_leverage = 15      # 15x leverage
sl_percent = 1.5           # stop loss %
tp_percent = 3.0           # take profit %
rsi_length = 14
rsi_oversold = 30
lookback_period = 5

# -----------------------------
# Connect to Pionex via CCXT
# -----------------------------
api_key = os.environ.get('PIONEX_API_KEY')
api_secret = os.environ.get('PIONEX_API_SECRET')

pionex = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True
})

# -----------------------------
# Check max leverage if futures
# -----------------------------
if market_type == 'futures':
    leverage = desired_leverage  # 15x
    print(f"[INFO] Futures trading mode. Using leverage: {leverage}")
else:
    leverage = 1
    print("[INFO] Spot trading mode. Leverage ignored.")
# -----------------------------
# Store open trades
# -----------------------------
open_trades = []

# -----------------------------
# Function to fetch last 5 1H candles
# -----------------------------
def fetch_candles():
    timeframe = '1h'
    limit = 180
    if market_type == 'spot':
        ohlcv = pionex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    else:  # futures
        ohlcv = pionex.fapiPublic_get_klines({'symbol': symbol.replace('/', ''), 'interval': timeframe, 'limit': limit})
    data = pd.DataFrame(ohlcv, columns=['Time','Open','High','Low','Close','Volume'])
    data['Time'] = pd.to_datetime(data['Time'], unit='ms')
    return data

# -----------------------------
# Function to calculate RSI
# -----------------------------
def compute_rsi(series, period):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# -----------------------------
# Main bot loop
# -----------------------------
while True:
    try:
        candles = fetch_candles()
        candles['RSI'] = compute_rsi(candles['Close'], rsi_length)

        # Check for signals (Bullish RSI Divergence)
        last_pivot_low_price = candles['Low'].rolling(lookback_period*2+1, center=True).min()
        last_pivot_low_rsi = candles['RSI'].rolling(lookback_period*2+1, center=True).min()
        
        # Simplified: check last candle only
        latest = candles.iloc[-1]
        prev = candles.iloc[-(lookback_period+1)]

        bullish_divergence = False
        if prev['Low'] < last_pivot_low_price.iloc[-(lookback_period+1)] and prev['RSI'] > last_pivot_low_rsi.iloc[-(lookback_period+1)]:
            bullish_divergence = True

        # Entry condition
        if bullish_divergence and latest['RSI'] < rsi_oversold:
            entry_price = latest['Close']
            stop_loss = entry_price * (1 - sl_percent/100)
            take_profit = entry_price * (1 + tp_percent/100)
            trade = {
                'type': 'BUY',
                'Entry': entry_price,
                'SL': stop_loss,
                'TP': take_profit,
                'Time': latest['Time']
            }
            open_trades.append(trade)

            if simulate_only:
                print(f"Simulated BUY order: Entry={entry_price}, SL={stop_loss}, TP={take_profit} at {latest['Time']}")
            else:
                # Real Pionex order
                quantity = trade_amount / entry_price  # USD -> contracts
                pionex.create_market_buy_order(symbol, quantity)
                print(f"[LIVE] BUY order sent: Entry={entry_price}, SL={stop_loss}, TP={take_profit} at {latest['Time']}")

        # -----------------------------
        # Check open trades for TP/SL hit
        # -----------------------------
        to_remove = []
        for t in open_trades:
            if t['type'] == 'BUY':
                if latest['High'] >= t['TP']:
                    print(f"Result: BUY WIN! Entry={t['Entry']}, TP hit={t['TP']}, Time={latest['Time']}")
                    to_remove.append(t)
                elif latest['Low'] <= t['SL']:
                    print(f"Result: BUY LOSS! Entry={t['Entry']}, SL hit={t['SL']}, Time={latest['Time']}")
                    to_remove.append(t)
        for t in to_remove:
            open_trades.remove(t)

        # Wait until next 1H candle
        print(f"Waiting 1 hour... ({datetime.now()})")
        time.sleep(3600)

    except Exception as e:
        print(f"[ERROR] {e}")
        time.sleep(60)


