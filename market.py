"""Live market data (Yahoo Finance via yfinance) and the event-study calculations.

If a file data/prices.csv exists (dates in the first column, one adjusted-close column per ticker),
it is used instead of downloading, which makes the demo independent of a live connection.
"""
import os
import time

import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

MARKET = 'SPY'
SECTOR_ETF = {'Tech': 'XLK', 'Bank': 'KBE'}
WINDOWS = {'Day (0 to +1)': (0, 1), 'Week (0 to +5)': (0, 5), 'Month (0 to +21)': (0, 21)}
LOCAL_PRICES = os.path.join('data', 'prices.csv')


def _download(tickers, start, end):
    import yfinance as yf
    df = yf.download(list(tickers), start=start, end=end, auto_adjust=True, progress=False, threads=False)
    close = pd.DataFrame()
    if df is not None and not df.empty:
        close = df['Close'] if 'Close' in df.columns.get_level_values(0) else df
        if isinstance(close, pd.Series):
            close = close.to_frame(tickers[0])
    # Yahoo sometimes drops a ticker (rate limits): retry each missing one on its own
    for t in tickers:
        if t in close.columns and close[t].notna().sum() > 5:
            continue
        time.sleep(1)
        try:
            h = yf.Ticker(t).history(start=start, end=end, auto_adjust=True)
        except Exception:
            continue
        if h is not None and not h.empty and 'Close' in h:
            s = h['Close']
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            if not close.empty:
                close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
            close = close.drop(columns=[t], errors='ignore').join(s.rename(t), how='outer') if not close.empty else s.rename(t).to_frame()
    if close.empty:
        return close
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close.dropna(how='all')


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _live_prices(tickers, start, end, required):
    """Raises when a required ticker is missing, so a failed download is never cached."""
    close = _download(tickers, start, end)
    missing = [t for t in required if t not in close.columns or close[t].notna().sum() <= 5]
    if missing:
        raise LookupError(', '.join(missing))
    return close


def prices(tickers, start, end, required=None):
    """Adjusted closing prices. Returns (DataFrame or None, message). required: tickers that must be present (default all)."""
    tickers = tuple(sorted(set(tickers)))
    required = tuple(sorted(set(required))) if required else tickers
    if os.path.exists(LOCAL_PRICES):
        local = pd.read_csv(LOCAL_PRICES, index_col=0, parse_dates=True)
        if (all(t in local.columns for t in tickers) and local.index.min() <= pd.Timestamp(start) + pd.Timedelta(days=10)
                and local.index.max() >= pd.Timestamp(end) - pd.Timedelta(days=10)):
            return local[list(tickers)], 'saved price file (data/prices.csv)'
    try:
        return _live_prices(tickers, start, end, required), 'Yahoo Finance (live)'
    except LookupError as e:
        return None, (f'Yahoo Finance returned no prices for {e}. This is usually a temporary limit on requests from the hosting '
                      'server; wait a minute and press R to rerun the page.')
    except Exception as e:
        name = type(e).__name__
        hint = ' Yahoo is limiting requests from this server; wait a minute and press R to rerun.' if 'Rate' in name or 'Too Many' in str(e) else ''
        return None, f'Live price data is unavailable right now ({name}).{hint}'


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _info(ticker):
    import yfinance as yf
    info = yf.Ticker(ticker).info or {}
    if not info.get('sector') and not info.get('longName'):
        raise LookupError(ticker)
    return info


def company_info(ticker):
    try:
        return _info(ticker)
    except Exception:
        return {}


TSX_BENCH = 'XIU.TO'


def ticker_candidates(raw):
    """Yahoo Finance spellings to try for a ticker typed by a user, e.g. RCI.B or RCI/B -> RCI-B.TO (Toronto, class B)."""
    t = raw.strip().upper().replace(' ', '')
    for suffix in ('CN', 'CT'):  # Bloomberg-style Canadian suffixes
        if t.endswith(suffix) and len(t) > len(suffix) + 1 and not t.endswith('.' + suffix):
            t = t[:-len(suffix)] + '.TO'
    t = t.replace('/', '.')
    cands = [t]
    if t.endswith(('.TO', '.V')):
        stem, ex = t.rsplit('.', 1)
        cands.append(stem.replace('.', '-') + '.' + ex)
    else:
        cands += [t.replace('.', '-'), t.replace('.', '-') + '.TO']
    out = []
    for c in cands:
        if c and c not in out:
            out.append(c)
    return out


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _has_prices(symbol):
    import yfinance as yf
    h = yf.Ticker(symbol).history(period='1mo')
    if h is None or h.empty:
        raise LookupError(symbol)
    return True


def resolve_ticker(raw):
    """First Yahoo Finance symbol with price data for what the user typed; None if none works."""
    if os.path.exists(LOCAL_PRICES):
        cols = set(pd.read_csv(LOCAL_PRICES, nrows=0).columns)
        for c in ticker_candidates(raw):
            if c in cols:
                return c
    for c in ticker_candidates(raw):
        try:
            if _has_prices(c):
                return c
        except Exception:
            continue
    return None


def benchmark_for(symbol):
    """Market benchmark in the stock's home market: S&P/TSX 60 (XIU) for Toronto listings, S&P 500 (SPY) otherwise."""
    if str(symbol).upper().endswith(('.TO', '.V')):
        return TSX_BENCH, 'S&P/TSX 60'
    return MARKET, 'S&P 500'


def yahoo_sector(ticker):
    """Map Yahoo Finance's sector and industry to our sector groups (Bank, Tech) or return Yahoo's sector name."""
    info = company_info(ticker) if ticker else {}
    sector, industry = info.get('sector') or '', info.get('industry') or ''
    if 'bank' in industry.lower():
        return 'Bank'
    if sector == 'Technology' or industry.startswith('Internet') or 'software' in industry.lower() or 'semiconductor' in industry.lower():
        return 'Tech'
    return sector or None


def event_window(px, ticker, call_date, benchmark=MARKET, window=21):
    """Daily returns, abnormal returns and their running total from -window to +window trading days."""
    if px is None or ticker not in px.columns or benchmark not in px.columns:
        return None
    rets = px[[ticker, benchmark]].pct_change()
    days = rets.index
    t0 = days.searchsorted(pd.Timestamp(call_date))
    rows = []
    for k in range(-window, window + 1):
        i = t0 + k
        if 0 < i < len(days) and pd.notna(rets[ticker].iloc[i]) and pd.notna(rets[benchmark].iloc[i]):
            rows.append({'day': k, 'date': days[i], 'ret': rets[ticker].iloc[i], 'bench_ret': rets[benchmark].iloc[i]})
    if not rows:
        return None
    ev = pd.DataFrame(rows)
    ev['abn_ret'] = ev['ret'] - ev['bench_ret']
    pre = ev[ev['day'] < 0].copy()
    post = ev[ev['day'] >= 0].copy()
    pre['car'] = -(pre['abn_ret'][::-1].cumsum()[::-1] - pre['abn_ret'])
    post['car'] = post['abn_ret'].cumsum()
    return pd.concat([pre, post]).sort_values('day')


def estimation_sd(px, ticker, call_date, benchmark=MARKET, first=-120, last=-22, min_obs=60):
    """Standard deviation of daily abnormal returns in an estimation window before the event (MacKinlay 1997).
    Returns (sd, number of days, window label). Falls back to days -21 to -1 when there is not enough history."""
    if px is None or ticker not in px.columns or benchmark not in px.columns:
        return np.nan, 0, ''
    rets = px[[ticker, benchmark]].pct_change().dropna()
    if rets.empty:
        return np.nan, 0, ''
    t0 = rets.index.searchsorted(pd.Timestamp(call_date))
    for a, b in ((first, last), (-21, -1)):
        lo, hi = max(t0 + a, 0), t0 + b + 1
        w = rets.iloc[lo:hi] if hi > lo else rets.iloc[0:0]
        if len(w) >= (min_obs if a == first else 15):
            abn = w[ticker] - w[benchmark]
            return float(abn.std()), int(len(w)), f'days {a} to {b}'
    return np.nan, 0, ''


def car(ev, first, last):
    if ev is None:
        return np.nan
    w = ev[(ev['day'] >= first) & (ev['day'] <= last)]
    if w.empty or w['day'].max() < last:
        return np.nan
    return w['abn_ret'].sum()


def _saved_event_study(calls, benchmark):
    """Event study precomputed by pipeline/run_pipeline.py, if it covers these calls."""
    ret_file, path_file = os.path.join('data', 'event_returns.csv'), os.path.join('data', 'event_paths.csv')
    if not (os.path.exists(ret_file) and os.path.exists(path_file)):
        return None
    label = 'SPY' if benchmark == MARKET else 'sector'
    cars = pd.read_csv(ret_file)
    cars = cars[(cars['benchmark'] == label) & ((label == 'SPY') | (cars['etf'] == benchmark)) & cars['call_id'].isin(calls['call_id'])]
    if cars['call_id'].nunique() < 0.8 * calls['call_id'].nunique():
        return None
    paths = pd.read_csv(path_file)
    paths = paths[(paths['benchmark'] == label) & paths['call_id'].isin(cars['call_id'])]
    return cars.drop(columns=['benchmark', 'etf']), paths[['call_id', 'day', 'abn_ret']]


def benchmark_event_study(calls, benchmark=MARKET, window=21):
    """CARs for every benchmark call. calls: DataFrame with call_id, ticker, call_date."""
    saved = _saved_event_study(calls, benchmark)
    if saved is not None:
        return saved[0], saved[1], 'event study saved by the automated pipeline'
    tickers = list(calls['ticker'].unique()) + [benchmark]
    start = (calls['call_date'].min() - pd.Timedelta(days=60)).strftime('%Y-%m-%d')
    end = (calls['call_date'].max() + pd.Timedelta(days=60)).strftime('%Y-%m-%d')
    px, source = prices(tuple(tickers), start, end, required=(benchmark,))
    if px is None:
        return None, None, source
    lost = sorted(t for t in calls['ticker'].unique() if t not in px.columns or px[t].notna().sum() <= 5)
    if lost:
        source += f' · no prices for {", ".join(lost)}'
    rows, paths = [], []
    for _, c in calls.iterrows():
        ev = event_window(px, c['ticker'], c['call_date'], benchmark, window)
        if ev is None:
            continue
        rows.append({'call_id': c['call_id'], 'car_pre': car(ev, -window, -1), 'car_day': car(ev, 0, 1),
                     'car_week': car(ev, 0, 5), 'car_month': car(ev, 0, window), 'hold_week': car(ev, 2, 5), 'car_drift': car(ev, 2, window)})
        paths.append(ev.assign(call_id=c['call_id']))
    if not rows:
        return None, None, 'No price data matched the benchmark calls.'
    return pd.DataFrame(rows), pd.concat(paths), source


def correlations(data, measures, windows):
    out = []
    for m in measures:
        for w in windows:
            d = data[[m, w]].dropna()
            if len(d) < 5:
                continue
            rho, p = stats.spearmanr(d[m], d[w])
            out.append({'measure': m, 'window': w, 'rho': rho, 'p': p, 'n': len(d)})
    return pd.DataFrame(out)


def long_short(data, signal_col, ret_col):
    d = data[[signal_col, ret_col]].dropna()
    long, short = d.loc[d[signal_col] == 'Positive', ret_col], d.loc[d[signal_col] == 'Negative', ret_col]
    if len(long) < 2 or len(short) < 2:
        return None
    t, p = stats.ttest_ind(long, short, equal_var=False)
    return {'n_long': len(long), 'n_short': len(short), 'long': long.mean(), 'short': short.mean(),
            'spread': long.mean() - short.mean(), 'hit_long': (long > 0).mean(), 'hit_short': (short < 0).mean(), 'p': p}


def stock_stats(px, ticker, benchmark=MARKET):
    p = px[ticker].dropna().iloc[-252:]
    m = px[benchmark].reindex(p.index)
    r, mr = p.pct_change().dropna(), m.pct_change().dropna()
    r, mr = r.align(mr, join='inner')
    return {'price': p.iloc[-1], 'as_of': p.index[-1], 'ret_1y': p.iloc[-1] / p.iloc[0] - 1, 'mkt_1y': m.iloc[-1] / m.iloc[0] - 1,
            'vol_1y': r.std() * np.sqrt(252), 'vol_30d': r.iloc[-21:].std() * np.sqrt(252),
            'max_dd': (p / p.cummax() - 1).min(), 'beta': r.cov(mr) / mr.var(), 'high': p.max(), 'low': p.min()}


def call_reaction(ticker, call_date, sector=None):
    """Market-adjusted reaction around one call, as plain numbers (same method as the Analyze page).

    Returns a dict, or {'error': message} when prices cannot be used. Nothing is rendered here.
    """
    if not ticker or not call_date:
        return {'error': 'Enter the ticker and call date in the left panel to see how the stock reacted.'}
    pt = resolve_ticker(ticker) or ticker
    mkt, mkt_label = benchmark_for(pt)
    start = (pd.Timestamp(call_date) - pd.Timedelta(days=220)).strftime('%Y-%m-%d')
    end = min(pd.Timestamp(call_date) + pd.Timedelta(days=50), pd.Timestamp.today()).strftime('%Y-%m-%d')
    px, source = prices((pt, mkt), start, end)
    ev = event_window(px, pt, call_date, mkt) if px is not None else None
    if ev is None:
        return {'error': f'Price data for {ticker} could not be loaded ({source or "no source"}).'}
    day = car(ev, 0, 1)
    sd, n, _ = estimation_sd(px, pt, call_date, mkt)
    t = day / (sd * np.sqrt(2)) if np.isfinite(day) and sd and sd > 0 else np.nan
    return {'symbol': pt, 'market': mkt, 'market_label': mkt_label, 'source': source,
            'pre': car(ev, -21, -1), 'day': day, 'week': car(ev, 0, 5), 'month': car(ev, 0, 21),
            't': t, 'size': abs(t) if np.isfinite(t) else np.nan}
