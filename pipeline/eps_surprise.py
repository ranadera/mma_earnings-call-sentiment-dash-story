"""Earnings surprise for each call, and the test: does tone add anything beyond the numbers?

Run after run_pipeline.py (it reads data/call_sentiment.csv and data/event_returns.csv):

    python pipeline/eps_surprise.py --data data [--manual eps_manual.csv]

1. EPS surprise. For each call, the analysts' consensus EPS estimate and the reported EPS
   come from Yahoo Finance (earnings dates within a day of the call). An optional CSV
   (columns: ticker, call_date, eps_estimate, eps_actual[, source]), e.g. from Bloomberg,
   fills gaps or overrides Yahoo. Surprise = (reported - estimate) / |estimate|, in percent.

2. The test. Regressions of the stock's move against the market on the surprise, then on the
   surprise plus tone, with heteroskedasticity-robust (HC1) standard errors:
       move = a + b1 * surprise + e
       move = a + b1 * surprise + b2 * tone + e
   for the 2-day reaction (days 0 to +1) and the drift after it (days +2 to +21), with tone
   measured two ways: the overall score, and tone vs. the company's own earlier calls.
   Surprise and tone are standardised (z-scores) so their coefficients compare directly;
   the surprise is capped at +/-50% first so one huge beat cannot dominate.

Writes data/eps_surprise.csv and data/surprise_test.json. Never fails the update: if the
estimates cannot be fetched, it writes what it has and says so.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

CAP = 50.0          # surprise cap, percent
MIN_CALLS = 20      # fewer usable calls than this: no test


def fetch_yahoo(tickers):
    """Earnings dates with EPS estimate and reported EPS, per ticker, from Yahoo Finance."""
    import yfinance as yf
    rows = []
    for t in tickers:
        try:
            d = yf.Ticker(t).get_earnings_dates(limit=40)
        except Exception as e:
            print(f'EPS estimates not available for {t}: {e}')
            continue
        if d is None or d.empty:
            print(f'EPS estimates not available for {t}')
            continue
        d = d.reset_index()
        date_col = d.columns[0]
        for _, r in d.iterrows():
            ts = pd.Timestamp(r[date_col])
            if ts.tzinfo is not None:
                ts = ts.tz_localize(None)
            rows.append({'ticker': t, 'eps_date': ts.normalize(),
                         'eps_estimate': r.get('EPS Estimate'), 'eps_actual': r.get('Reported EPS')})
    return pd.DataFrame(rows, columns=['ticker', 'eps_date', 'eps_estimate', 'eps_actual'])


def match(calls, yahoo):
    """Nearest Yahoo earnings date within one day of each call (results and call on the same day or the evening before)."""
    out = []
    for _, c in calls.iterrows():
        y = yahoo[yahoo['ticker'] == c['ticker']]
        y = y.assign(gap=(y['eps_date'] - c['call_date']).abs()).query('gap <= @pd.Timedelta(days=1)').dropna(subset=['eps_actual', 'eps_estimate'])
        if len(y):
            r = y.sort_values('gap').iloc[0]
            out.append({'call_id': c['call_id'], 'eps_estimate': r['eps_estimate'], 'eps_actual': r['eps_actual'], 'source': 'Yahoo Finance'})
    return pd.DataFrame(out, columns=['call_id', 'eps_estimate', 'eps_actual', 'source'])


def ols(df, y, xs):
    """OLS with HC1 robust standard errors. Returns coefficients, t, p, R2, n."""
    d = df[[y] + xs].dropna()
    n, k = len(d), len(xs) + 1
    if n < MIN_CALLS:
        return None
    X = np.column_stack([np.ones(n)] + [d[x].to_numpy(float) for x in xs])
    Y = d[y].to_numpy(float)
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ Y
    resid = Y - X @ beta
    meat = (X * resid[:, None] ** 2).T @ X
    cov = XtX_inv @ meat @ XtX_inv * n / (n - k)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), n - k)
    r2 = 1 - (resid ** 2).sum() / ((Y - Y.mean()) ** 2).sum()
    terms = ['const'] + xs
    return {'n': int(n), 'r2': float(r2),
            'coef': {a: float(b) for a, b in zip(terms, beta)},
            't': {a: float(b) for a, b in zip(terms, t)},
            'p': {a: float(b) for a, b in zip(terms, p)}}


def zs(s):
    return (s - s.mean()) / s.std()


def run_test(calls, cars, eps):
    d = calls.merge(eps[['call_id', 'surprise_pct']], on='call_id', how='left')
    spy = cars[cars['benchmark'] == 'SPY'][['call_id', 'car_day', 'car_drift']]
    d = d.merge(spy, on='call_id', how='left')
    d = d.sort_values(['ticker', 'call_date'])
    d['usual_composite'] = d.groupby('ticker')['composite'].transform(lambda s: s.shift().expanding().mean())
    d['tone_vs_usual'] = d['composite'] - d['usual_composite']
    d['surprise_capped'] = d['surprise_pct'].clip(-CAP, CAP)
    have = d.dropna(subset=['surprise_capped', 'car_day'])
    res = {'calls': int(len(d)), 'calls_with_surprise': int(d['surprise_pct'].notna().sum()), 'cap_pct': CAP}
    if len(have) < MIN_CALLS:
        res['status'] = f'too few calls with an earnings surprise ({len(have)}); need {MIN_CALLS}'
        return res
    s = have['surprise_pct']
    res.update({'status': 'ok', 'beats': int((s > 0).sum()), 'misses': int((s < 0).sum()), 'in_line': int((s == 0).sum()),
                'median_surprise_pct': float(s.median())})
    # does tone just echo the numbers? correlation between tone and the surprise
    for tone in ['composite', 'tone_vs_usual']:
        x = have.dropna(subset=[tone])
        rho, p = stats.spearmanr(x[tone], x['surprise_capped'])
        res[f'rho_{tone}_surprise'] = {'rho': float(rho), 'p': float(p), 'n': int(len(x))}
    models = {}
    for y in ['car_day', 'car_drift']:
        for tone in ['composite', 'tone_vs_usual']:
            x = have.dropna(subset=[y, tone]).copy()
            x['surprise_z'], x['tone_z'] = zs(x['surprise_capped']), zs(x[tone])
            x[y] = x[y] * 100   # percent
            m1, m2 = ols(x, y, ['surprise_z']), ols(x, y, ['surprise_z', 'tone_z'])
            if m1 and m2:
                models[f'{y}|{tone}'] = {'surprise_only': m1, 'surprise_and_tone': m2, 'r2_added_by_tone': m2['r2'] - m1['r2']}
    res['models'] = models
    # verdict for the 2-day reaction with the overall tone
    m = models.get('car_day|composite')
    if m:
        p_s, p_t = m['surprise_and_tone']['p']['surprise_z'], m['surprise_and_tone']['p']['tone_z']
        res['verdict'] = ('tone_adds' if p_t < 0.05 else
                          'numbers_only' if p_s < 0.05 else
                          'neither')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    ap.add_argument('--manual', help='CSV of EPS estimates and reported EPS (e.g. from Bloomberg): ticker, call_date, eps_estimate, eps_actual[, source]')
    args = ap.parse_args()
    calls = pd.read_csv(os.path.join(args.data, 'call_sentiment.csv'), parse_dates=['call_date'])
    cars = pd.read_csv(os.path.join(args.data, 'event_returns.csv'))
    try:
        yahoo = fetch_yahoo(sorted(calls['ticker'].unique()))
    except Exception as e:
        print('Could not fetch EPS estimates from Yahoo Finance:', e)
        yahoo = pd.DataFrame(columns=['ticker', 'eps_date', 'eps_estimate', 'eps_actual'])
    print(f'Yahoo Finance: {len(yahoo)} earnings dates for {yahoo["ticker"].nunique()} companies.')
    eps = match(calls, yahoo)
    if args.manual and os.path.exists(args.manual):
        man = pd.read_csv(args.manual).dropna(subset=['eps_estimate', 'eps_actual'])
        man['call_date'] = pd.to_datetime(man['call_date'])
        man['call_id'] = man['ticker'].str.upper() + '_' + man['call_date'].dt.strftime('%Y-%m-%d')
        man['source'] = man['source'] if 'source' in man else 'Manual'
        eps = pd.concat([eps[~eps['call_id'].isin(man['call_id'])], man[['call_id', 'eps_estimate', 'eps_actual', 'source']]])
        print(f'{len(man)} EPS values from {args.manual}')
    eps = calls[['call_id', 'ticker', 'call_date']].merge(eps, on='call_id', how='left')
    eps['eps_estimate'] = pd.to_numeric(eps['eps_estimate'], errors='coerce')
    eps['eps_actual'] = pd.to_numeric(eps['eps_actual'], errors='coerce')
    eps['surprise_pct'] = (eps['eps_actual'] - eps['eps_estimate']) / eps['eps_estimate'].abs() * 100
    eps.loc[eps['eps_estimate'].abs() < 0.01, 'surprise_pct'] = np.nan   # estimate near zero: percent is meaningless
    eps['call_date'] = eps['call_date'].dt.strftime('%Y-%m-%d')
    eps.round(4).to_csv(os.path.join(args.data, 'eps_surprise.csv'), index=False)
    missing = eps[eps['surprise_pct'].isna()]['call_id'].tolist()
    print(f"EPS surprise found for {eps['surprise_pct'].notna().sum()} of {len(eps)} calls.")
    if missing:
        print('No EPS surprise for:', ', '.join(missing))
    res = run_test(calls, cars, eps)
    res['updated'] = pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    json.dump(res, open(os.path.join(args.data, 'surprise_test.json'), 'w'), indent=1)
    print('Verdict:', res.get('verdict', res.get('status')))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:   # never block the data update
        print('EPS surprise step failed:', e)
        sys.exit(0)
