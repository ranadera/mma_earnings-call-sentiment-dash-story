"""Save a backup price file so the app's market pages work even if Yahoo Finance is unavailable.

Run from the repository folder:   python scripts/make_prices.py AMZN JPM
(optional extra tickers after the script name), then commit data/prices.csv.
"""
import sys
import time

import pandas as pd
import yfinance as yf

tickers = sorted(set(pd.read_csv('data/sector_map.csv')['ticker']) | {'SPY', 'XLK', 'KBE'} | set(a.upper() for a in sys.argv[1:]))
start = '2023-06-01'
frames = []
for t in tickers:
    h = yf.Ticker(t).history(start=start, auto_adjust=True)
    if h.empty:
        print('no data for', t)
        continue
    s = h['Close'].rename(t)
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    frames.append(s)
    time.sleep(0.5)
prices = pd.concat(frames, axis=1).sort_index()
prices.round(4).to_csv('data/prices.csv')
print(f'Saved data/prices.csv: {prices.shape[1]} tickers, {prices.index.min():%Y-%m-%d} to {prices.index.max():%Y-%m-%d}')
