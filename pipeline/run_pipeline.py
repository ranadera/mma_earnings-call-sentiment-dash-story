"""Quanta-Mentals automated pipeline: transcripts -> sentiment scores -> event study -> model.

Runs the same steps as the notebooks, without manual work, and writes only derived numbers
(no transcript text) to the app's data folder.

    python pipeline/run_pipeline.py --transcripts ../transcripts --out data

Folders under --transcripts become the `dataset` column (e.g. benchmark, banks_2023_24).
A ticker missing from data/sector_map.csv gets its folder's sector: a folder name containing
"bank" -> Bank, "tech" -> Tech, otherwise Other.
"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sentiment_core as sc  # noqa: E402

MARKET = 'SPY'
SECTOR_ETF = {'Tech': 'XLK', 'Bank': 'KBE'}
WINDOW = 21
FEATURES = ['lm_tone', 'lm_tone_sector', 'composite', 'tone_shift', 'conviction_score', 'analyst_neg_rate', 'hedging']


def zs(s):
    return (s - s.mean()) / s.std()


def folder_sector(dataset):
    d = dataset.lower()
    return 'Bank' if 'bank' in d else 'Tech' if 'tech' in d else 'Other'


# ---------- 1. Read and score every transcript ----------
def score_all(root, data_dir):
    lm = sc.load_lm(os.path.join(data_dir, 'LM_MasterDictionary.csv'))
    smap = sc.load_sector_map(os.path.join(data_dir, 'sector_map.csv'))
    lexicon = sc.load_sector_lexicon(os.path.join(data_dir, 'sector_lexicon.csv'))
    files = sorted(f for f in glob.glob(os.path.join(root, '**', '*'), recursive=True) if f.lower().endswith(('.pdf', '.txt')))
    calls, seg_rows, kept = [], [], set()
    for f in files:
        rel = os.path.relpath(f, root)
        dataset = rel.split(os.sep)[0] if os.sep in rel else 'transcripts'
        raw = sc.read_text(f, open(f, 'rb').read())
        meta = sc.get_meta(raw)
        if not meta['ticker'] or not meta['call_date']:
            print('Skipped (ticker or date not found):', rel)
            continue
        call_id = meta['ticker'] + '_' + meta['call_date']
        if call_id in kept:
            print('Duplicate call skipped:', rel)
            continue
        sector = smap.get(meta['ticker'].upper()) or folder_sector(dataset)
        fmt, turns = sc.parse(raw)
        t = sc.score_turns(turns, lm, sc.neutral_terms(lexicon, sector))
        if t.empty or t['n_words'].sum() < 200:
            print('Skipped (too little text):', rel)
            continue
        kept.add(call_id)
        overall = sc.summarise(t)
        parts = {p: sc.summarise(g) for p, g in t.groupby('part')}
        row = {'call_id': call_id, 'ticker': meta['ticker'], 'company': meta['company'] or meta['ticker'], 'sector': sector,
               'dataset': dataset, 'call_date': meta['call_date'], 'is_transcript': not fmt.startswith('Plain'), 'format': fmt,
               'words': overall['words'], 'lm_tone': overall['lm_tone'],
               'lm_polarity': (t['lm_pos'].sum() - t['lm_neg'].sum()) / max(t['lm_pos'].sum() + t['lm_neg'].sum(), 1),
               'lm_uncertainty': overall['lm_uncertainty'], 'vader': overall['vader'], 'textblob': overall['textblob'],
               'lm_tone_sector': (t['adj_pos'].sum() - t['adj_neg'].sum()) / overall['words'] * 100}
        get = lambda p, k: parts.get(p, {}).get(k, np.nan)
        row.update({'pres_tone': get('presentation', 'lm_tone'), 'qa_mgmt_tone': get('qa_management', 'lm_tone'),
                    'analyst_tone': get('qa_analyst', 'lm_tone'), 'analyst_neg_rate': get('qa_analyst', 'lm_neg_rate'),
                    'hedging': get('qa_management', 'lm_uncertainty') - get('presentation', 'lm_uncertainty')})
        a = t[t['part'] == 'qa_analyst']
        row['analyst_neg_share'] = ((a['lm_pos'] - a['lm_neg']) < 0).mean() if len(a) else np.nan
        segs, _ = sc.segments(t, lm)
        row['call_drift'] = segs['lm_tone'].iloc[-3:].mean() - segs['lm_tone'].iloc[:3].mean()
        m = t[t['part'] == 'qa_management'].copy()
        m = m[m['n_words'] >= 30]
        m['tone'] = (m['lm_pos'] - m['lm_neg']) / m['n_words'] * 100
        row['qa_slope'] = np.polyfit(np.arange(len(m)), m['tone'], 1)[0] if len(m) >= 3 else np.nan
        calls.append(row)
        seg_rows += [{'segment': s, 'call_id': call_id, 'lm_tone': v, 'sector': sector} for s, v in zip(segs['segment'], segs['lm_tone'])]
        print(f'Scored {call_id:22s} {sector:6s} {dataset}')
    calls = pd.DataFrame(calls)
    if calls.empty:
        raise SystemExit('No transcripts could be scored.')

    full = calls['is_transcript']
    calls['tone_shift'] = calls['qa_mgmt_tone'] - calls['pres_tone']
    calls['conviction_gap'] = calls['qa_mgmt_tone'] - calls['analyst_tone']
    z = (calls.loc[full, ['lm_tone', 'vader', 'textblob']] - calls.loc[full, ['lm_tone', 'vader', 'textblob']].mean()) / calls.loc[full, ['lm_tone', 'vader', 'textblob']].std()
    calls['composite'] = z.mean(axis=1)
    q1, q2 = calls.loc[full, 'composite'].quantile([1 / 3, 2 / 3])
    calls['signal'] = np.where(calls['composite'] <= q1 + 1e-9, 'Negative', np.where(calls['composite'] <= q2 + 1e-9, 'Neutral', 'Positive'))
    calls.loc[~full, 'signal'] = np.nan
    calls['lm_signal'] = pd.qcut(calls.loc[full, 'lm_tone'], 3, labels=['Negative', 'Neutral', 'Positive'])
    b = calls[full]
    calls['conviction_score'] = (zs(b['conviction_gap']) + zs(b['tone_shift']) - zs(b['hedging']) - zs(b['analyst_neg_rate'])) / 4
    calls['sector_composite'] = b.groupby('sector')['composite'].transform(lambda s: zs(s) if len(s) >= 3 else np.nan)
    calls['quarter'] = pd.to_datetime(calls['call_date']).dt.to_period('Q').astype(str)
    calls['year'] = pd.to_datetime(calls['call_date']).dt.year
    gpath = os.path.join(data_dir, 'peer_groups.csv')
    groups = dict(pd.read_csv(gpath, dtype=str).dropna().values) if os.path.exists(gpath) else {}
    calls['group'] = calls['ticker'].map(groups).fillna('Other ' + calls['sector'].str.lower())
    return calls.sort_values(['dataset', 'call_date', 'ticker']), pd.DataFrame(seg_rows)


# ---------- 2. Prices and event study ----------
def download_prices(tickers, start, end, local_file, extra_file=None):
    import yfinance as yf
    have = pd.read_csv(local_file, index_col=0, parse_dates=True) if os.path.exists(local_file) else pd.DataFrame()
    if extra_file and os.path.exists(extra_file):  # e.g. Bloomberg prices for delisted stocks (SIVB, CMA)
        extra = pd.read_csv(extra_file, index_col=0, parse_dates=True)
        extra.columns = [c.upper() for c in extra.columns]
        print('Saved prices supplied for:', ', '.join(extra.columns))
        have = extra if have.empty else extra.combine_first(have)
    frames = []
    for t in sorted(set(tickers)):
        s = None
        for attempt in range(3):
            try:
                h = yf.Ticker(t).history(start=start, end=end, auto_adjust=True)
                if h is not None and not h.empty:
                    s = h['Close']
                    break
            except Exception as e:
                print('  retry', t, type(e).__name__)
            time.sleep(2 * (attempt + 1))
        if s is None:
            if t in have.columns:
                print('  no live prices for', t, '- using the saved price file')
                frames.append(have[t].dropna())
            else:
                print('  no prices for', t, '(add them to data/prices.csv, e.g. from Bloomberg, for delisted stocks)')
            continue
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        frames.append(s.rename(t))
        time.sleep(0.4)
    px = pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()
    for t in have.columns:  # keep tickers only the saved file has (e.g. Bloomberg prices for delisted stocks)
        if t not in px.columns:
            px = px.join(have[t], how='outer')
    return px


def event_window(px, ticker, call_date, bench):
    if ticker not in px.columns or bench not in px.columns:
        return None
    rets = px[[ticker, bench]].dropna().pct_change()
    days = rets.index
    t0 = days.searchsorted(pd.Timestamp(call_date))
    rows = [{'day': k, 'abn_ret': rets[ticker].iloc[t0 + k] - rets[bench].iloc[t0 + k]}
            for k in range(-WINDOW, WINDOW + 1) if 0 < t0 + k < len(days)]
    return pd.DataFrame(rows) if rows else None


def car(ev, a, b):
    w = ev[(ev['day'] >= a) & (ev['day'] <= b)]
    return w['abn_ret'].sum() if not w.empty and w['day'].max() >= b and w['day'].min() <= a else np.nan


def event_study(calls, px):
    rows, paths = [], []
    for _, c in calls.iterrows():
        for label, bench in [('SPY', MARKET), ('sector', SECTOR_ETF.get(c['sector']))]:
            if bench is None:
                continue
            ev = event_window(px, c['ticker'], c['call_date'], bench)
            if ev is None:
                continue
            rows.append({'call_id': c['call_id'], 'benchmark': label, 'etf': bench, 'car_pre': car(ev, -WINDOW, -1),
                         'car_day': car(ev, 0, 1), 'car_week': car(ev, 0, 5), 'car_month': car(ev, 0, WINDOW),
                         'hold_week': car(ev, 2, 5), 'car_drift': car(ev, 2, WINDOW)})
            paths.append(ev.assign(call_id=c['call_id'], benchmark=label))
    return pd.DataFrame(rows), (pd.concat(paths) if paths else pd.DataFrame())


# ---------- 3. Predictive model: train on earlier years, test on the latest ----------
def train_model(calls, cars, out_dir):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    d = calls[calls['is_transcript']].merge(cars[cars['benchmark'] == 'SPY'], on='call_id')
    years = sorted(d['year'].unique())
    results = {'status': 'not enough data', 'years': [int(y) for y in years]}
    if len(years) < 2:
        results['note'] = 'Needs calls from at least two years (e.g. 2023 and 2024) to train on one and test on the next.'
        return results, pd.DataFrame()
    test_year = 2024 if 2024 in years and years[0] < 2024 else years[-1]
    train = d[d['year'] < test_year]
    test = d[d['year'] == test_year]
    later = d[d['year'] > test_year]
    results = {'status': 'ok', 'train_years': sorted(int(y) for y in train['year'].unique()), 'test_year': int(test_year),
               'later_years': sorted(int(y) for y in later['year'].unique()), 'targets': {}}
    preds = []
    for target, label in [('car_day', 'Reaction: beats the market over days 0 to +1'),
                          ('car_drift', 'Drift: beats the market from day +2 to +21 (tradable after the call)')]:
        tr, te = train.dropna(subset=FEATURES + [target]), test.dropna(subset=FEATURES + [target])
        if len(tr) < 20 or len(te) < 10 or tr[target].gt(0).nunique() < 2:
            results['targets'][target] = {'label': label, 'status': f'not enough calls (train {len(tr)}, test {len(te)})'}
            continue
        scaler = StandardScaler().fit(tr[FEATURES])
        model = LogisticRegression(C=1.0, max_iter=1000).fit(scaler.transform(tr[FEATURES]), tr[target] > 0)
        p = model.predict_proba(scaler.transform(te[FEATURES]))[:, 1]
        y = (te[target] > 0).to_numpy()
        base = max(tr[target].gt(0).mean(), 1 - tr[target].gt(0).mean())
        hi, lo = p >= np.quantile(p, 2 / 3), p <= np.quantile(p, 1 / 3)
        results['targets'][target] = {
            'label': label, 'status': 'ok', 'n_train': int(len(tr)), 'n_test': int(len(te)),
            'accuracy': float(((p > 0.5) == y).mean()), 'baseline_accuracy': float(base),
            'auc': float(roc_auc_score(y, p)) if len(set(y)) == 2 else None,
            'long_short': float(te.loc[hi, target].mean() - te.loc[lo, target].mean()),
            'coefficients': {f: float(c) for f, c in zip(FEATURES, model.coef_[0])}}
        lt = later.dropna(subset=FEATURES + [target])
        if len(lt) >= 5:
            pl = model.predict_proba(scaler.transform(lt[FEATURES]))[:, 1]
            results['targets'][target]['later_accuracy'] = float(((pl > 0.5) == (lt[target] > 0).to_numpy()).mean())
            results['targets'][target]['n_later'] = int(len(lt))
        preds.append(te[['call_id', 'ticker', 'call_date', 'sector']].assign(target=target, prob_up=p, actual=te[target].to_numpy()))
    return results, (pd.concat(preds) if preds else pd.DataFrame())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--transcripts', required=True)
    ap.add_argument('--out', default='data')
    ap.add_argument('--no-prices', action='store_true')
    ap.add_argument('--extra-prices', help='CSV of daily closing prices (date column, one column per ticker), e.g. from Bloomberg')
    args = ap.parse_args()

    calls, segs = score_all(args.transcripts, args.out)
    calls.to_csv(os.path.join(args.out, 'call_sentiment.csv'), index=False)
    segs.to_csv(os.path.join(args.out, 'segment_tone.csv'), index=False)
    print(f'\n{len(calls)} calls scored:', calls.groupby(['dataset', 'sector']).size().to_dict())

    results = {'status': 'prices skipped'}
    if not args.no_prices:
        dates = pd.to_datetime(calls['call_date'])
        start = (dates.min() - pd.Timedelta(days=60)).strftime('%Y-%m-%d')
        tickers = list(calls['ticker'].unique()) + [MARKET] + list(SECTOR_ETF.values())
        price_file = os.path.join(args.out, 'prices.csv')
        px = download_prices(tickers, start, None, price_file, args.extra_prices)
        if not px.empty:
            px.round(4).to_csv(price_file)
            cars, paths = event_study(calls, px)
            cars.to_csv(os.path.join(args.out, 'event_returns.csv'), index=False)
            paths.round(6).to_csv(os.path.join(args.out, 'event_paths.csv'), index=False)
            print(f'Event study: {cars["call_id"].nunique()} calls with prices')
            results, preds = train_model(calls, cars, args.out)
            preds.to_csv(os.path.join(args.out, 'model_predictions.csv'), index=False)
    results['updated'] = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M UTC')
    results['calls'] = int(len(calls))
    json.dump(results, open(os.path.join(args.out, 'model_results.json'), 'w'), indent=2)
    print('Model:', json.dumps(results, indent=2)[:1500])


if __name__ == '__main__':
    main()
