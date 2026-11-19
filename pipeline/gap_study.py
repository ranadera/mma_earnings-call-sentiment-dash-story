"""First reaction vs. readjustment around each earnings call (version 2 add-on).

Splits the market-adjusted reaction into two parts using DAILY open and close prices (no intraday data needed):
  gap      = previous close -> open of the first trading session after the results (the fast, first reaction:
             after-hours and pre-market trading, much of it algorithmic, on the release and the call)
  session  = that open -> that session's close (the readjustment once people have digested the call)
Both are the stock's return minus the S&P 500 ETF (SPY) return over the same span.

Which session comes "after the results" depends on when the company reports (data/report_timing.csv):
  before_open  (US banks): the call day itself
  after_close  (big tech): the next trading day
Companies not in that table: the session whose opening gap is larger (marked 'estimated from prices').

Limit: with daily data the gap contains the release AND, for most companies, the call (both happen before the next open),
so this separates the first reaction from the readjustment, not the release from the call.

Usage: python pipeline/gap_study.py [--data data]   (downloads daily prices from Yahoo Finance; writes data/gap_study.csv)
"""
import argparse
import os

import numpy as np
import pandas as pd

MARKET = 'SPY'


def reaction_session(dates, call_date, timing):
    """Index of the first trading session after the results, or None."""
    call_date = pd.Timestamp(call_date).normalize()
    pos = dates.searchsorted(call_date)                      # first trading day >= call date
    if timing == 'after_close':
        if pos < len(dates) and dates[pos] == call_date:
            pos += 1
    return pos if 0 < pos < len(dates) else None


def split(ohlc, ticker, call_date, timing):
    """Market-adjusted gap and session for one call. ohlc: {ticker: DataFrame with Open, Close (date index)}."""
    s, m = ohlc.get(ticker), ohlc.get(MARKET)
    if s is None or m is None:
        return None
    both = pd.concat({'so': s['Open'], 'sc': s['Close'], 'mo': m['Open'], 'mc': m['Close']}, axis=1).dropna()
    if len(both) < 3:
        return None

    def at(pos):
        prev, cur = both.iloc[pos - 1], both.iloc[pos]
        gap = (cur.so / prev.sc - 1) - (cur.mo / prev.mc - 1)
        ses = (cur.sc / cur.so - 1) - (cur.mc / cur.mo - 1)
        return gap, ses, both.index[pos]

    source = 'report_timing.csv'
    if timing not in ('before_open', 'after_close'):
        cands = [(t, reaction_session(both.index, call_date, t)) for t in ('before_open', 'after_close')]
        cands = [(t, p) for t, p in cands if p is not None]
        if not cands:
            return None
        timing, _ = max(cands, key=lambda tp: abs(at(tp[1])[0]))
        source = 'estimated from prices'
    pos = reaction_session(both.index, call_date, timing)
    if pos is None:
        return None
    gap, ses, day = at(pos)
    return {'timing': timing, 'timing_source': source, 'reaction_date': day.strftime('%Y-%m-%d'),
            'gap': gap, 'session': ses, 'total': gap + ses}


def build(calls, timing, ohlc):
    rows = []
    for _, c in calls.iterrows():
        r = split(ohlc, c['ticker'], c['call_date'], timing.get(c['ticker']))
        if r:
            rows.append({'call_id': c['call_id'], 'ticker': c['ticker'], 'call_date': c['call_date'], 'signal': c['signal'], **r})
    return pd.DataFrame(rows)


def download(tickers, start, end):
    import yfinance as yf
    out = {}
    for t in sorted(set(tickers) | {MARKET}):
        try:
            h = yf.Ticker(t).history(start=start, end=end, auto_adjust=True)
            if h is not None and not h.empty:
                h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
                out[t] = h[['Open', 'Close']]
        except Exception as e:  # one failed ticker never stops the rest
            print(f'  {t}: {e}')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    a = ap.parse_args()
    calls = pd.read_csv(os.path.join(a.data, 'call_sentiment.csv'), parse_dates=['call_date'])
    calls = calls.dropna(subset=['ticker', 'call_date'])
    tpath = os.path.join(a.data, 'report_timing.csv')
    timing = dict(pd.read_csv(tpath)[['ticker', 'timing']].values) if os.path.exists(tpath) else {}
    start = (calls['call_date'].min() - pd.Timedelta(days=10)).strftime('%Y-%m-%d')
    end = (calls['call_date'].max() + pd.Timedelta(days=10)).strftime('%Y-%m-%d')
    ohlc = download(calls['ticker'].unique(), start, end)
    out = build(calls, timing, ohlc)
    out['call_date'] = pd.to_datetime(out['call_date']).dt.strftime('%Y-%m-%d')
    out.round(6).to_csv(os.path.join(a.data, 'gap_study.csv'), index=False)
    print(f'gap_study.csv: {len(out)} of {len(calls)} calls')


if __name__ == '__main__':
    main()
