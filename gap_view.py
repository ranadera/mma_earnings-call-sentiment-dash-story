"""Version 2 add-on: "first reaction vs. readjustment" (switch: features.SHOW_GAP_STUDY).

Everything for this feature lives here, in pipeline/gap_study.py, data/report_timing.csv, data/gap_study.csv and
.github/workflows/gap-study.yml. If the data file is missing, every function here quietly shows nothing.

Method (daily data only): the reaction is split into
  gap      previous close -> open of the first session after the results (the fast first reaction, much of it algorithmic)
  session  that open -> that close (the readjustment once people have digested the call)
both minus the market's move over the same span. With daily data the gap contains the release and, for most companies,
the call as well, so this separates the first reaction from the readjustment, not the release from the call.
"""
import math
import os

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import ui
from ui import esc

DATA = os.path.join(os.path.dirname(__file__), 'data')


@st.cache_data
def load():
    path = os.path.join(DATA, 'gap_study.csv')
    return pd.read_csv(path) if os.path.exists(path) else None


@st.cache_data
def timing_table():
    path = os.path.join(DATA, 'report_timing.csv')
    return dict(pd.read_csv(path)[['ticker', 'timing']].values) if os.path.exists(path) else {}


def _luck(k, n):
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else float('nan')


def summary(df):
    d = df[df['signal'] != 'Neutral'].dropna(subset=['gap', 'session']).copy()
    d['pred'] = np.where(d['signal'] == 'Positive', 1, -1)
    d['gap_ok'] = np.sign(d['gap']) == d['pred']
    d['ses_ok'] = np.sign(d['session']) == d['pred']
    against = d[~d['gap_ok']]
    back = int(against['ses_ok'].sum())
    return {'d': d, 'n': len(d), 'gap_k': int(d['gap_ok'].sum()), 'ses_k': int(d['ses_ok'].sum()),
            'against': len(against), 'back': back, 'luck_ses': _luck(int(d['ses_ok'].sum()), len(d)),
            'luck_back': _luck(back, len(against)),
            'reversal': float((np.sign(df['gap']) != np.sign(df['session'])).mean()) if len(df) else float('nan'),
            'fade': _fade(df)}


def _fade(df):
    """Bet against the overnight jump during the next session (no sentiment): average, hit rate and p-value."""
    d = df.dropna(subset=['gap', 'session'])
    if len(d) < 10:
        return None
    from scipy import stats
    f = -np.sign(d['gap']) * d['session']
    return {'mean': float(f.mean()), 'hit': float((f > 0).mean()), 'p': float(stats.ttest_1samp(f, 0).pvalue), 'n': len(d)}


def story_chapter(chapter, so_what):
    """Chapter for the story page. chapter / so_what are the story page's own helpers."""
    df = load()
    if df is None or df.empty:
        return
    s = summary(df)
    n = s['n']
    if n < 10:
        return
    chapter('gap', 'CHAPTER 4 · PART 2',
            f'First reaction vs. readjustment: the tone matched the overnight jump in {s["gap_k"]} of {n} calls, '
            f'and the next trading session in {s["ses_k"]} of {n}',
            'Results come out first, and the first price move happens before the market opens, much of it from trading '
            'algorithms. Then people digest the call and the stock readjusts during the day. We split the reaction in two, '
            'each measured against the market: the <b>overnight jump</b> (last close to the next open) and the '
            '<b>first trading session</b> (that open to that close).')
    bars = pd.DataFrame([
        {'part': 'Overnight jump (first reaction)', 'rate': s['gap_k'] / n, 'label': f'{s["gap_k"]} of {n}'},
        {'part': 'First trading session (readjustment)', 'rate': s['ses_k'] / n, 'label': f'{s["ses_k"]} of {n}'}])
    base = alt.Chart(bars).encode(
        y=alt.Y('part:N', title=None, scale=alt.Scale(domain=list(bars['part']), paddingInner=0.35),
                axis=alt.Axis(labelFontSize=13, labelFontWeight='bold', labelLimit=320)),
        x=alt.X('rate:Q', title='Share of calls where the move went the way the tone suggested', scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(format='%')))
    chart = (base.mark_bar(cornerRadiusEnd=4, color=ui.AZURE)
             + base.mark_text(align='left', dx=6, fontWeight='bold', fontSize=13).encode(
                 text=alt.Text('label:N'))
             + alt.Chart(pd.DataFrame({'x': [0.5]})).mark_rule(color=ui.ROSE, strokeDash=[5, 4], strokeWidth=2).encode(x='x:Q'))
    st.altair_chart(chart.properties(height=170, title='Dashed line = coin flip (50%)'), width='stretch')
    if s['against']:
        st.markdown(f'When the overnight jump went <b>against</b> the tone ({s["against"]} calls), the stock moved back '
                    f'toward the tone during the next session in <b>{s["back"]} of {s["against"]}</b>. '
                    f'Overall, the session reversed the overnight jump in <b>{s["reversal"]:.0%}</b> of calls.',
                    unsafe_allow_html=True)
    if s['fade']:
        f = s['fade']
        st.markdown(f'<b>Timing, not tone:</b> betting against the overnight jump during the next session (buying after a drop, '
                    f'selling after a rise) averaged <b>{f["mean"]:+.2%}</b> per call against the market, before costs, and worked in '
                    f'{f["hit"]:.0%} of {f["n"]} calls (p-value {f["p"]:.2f}).', unsafe_allow_html=True)
    if s['ses_k'] > s['gap_k'] and s['luck_ses'] < 0.05:
        msg = ('The readjustment followed the tone more often than the first reaction did. That fits the idea that the '
               'fast first move reacts to the numbers, and people then adjust once they have heard how management sounded.')
    else:
        msg = ('Neither part follows the tone reliably in our sample: a coin would do about as well. The first reaction and '
               'the readjustment both seem driven by the numbers, guidance and expectations more than by how management sounded.')
    so_what(msg + ' <i>Limit: with daily prices the overnight jump includes the release and, for most companies, the call '
            'itself, so this separates the first reaction from the readjustment, not the release from the call.</i>')


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _live_ohlc(symbols, start, end):
    import yfinance as yf
    out = {}
    for t in symbols:
        h = yf.Ticker(t).history(start=start, end=end, auto_adjust=True)
        if h is None or h.empty:
            raise LookupError(t)
        h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
        out[t] = h[['Open', 'Close']]
    return out


def call_block(ticker, call_date):
    """First reaction vs. readjustment for one uploaded call (live daily prices). Shows nothing if prices are unavailable."""
    if not ticker or not call_date:
        return
    import market as mk
    from pipeline.gap_study import split
    sym = mk.resolve_ticker(ticker) or ticker
    bench, bench_label = mk.benchmark_for(sym)
    start = (pd.Timestamp(call_date) - pd.Timedelta(days=10)).strftime('%Y-%m-%d')
    end = (pd.Timestamp(call_date) + pd.Timedelta(days=10)).strftime('%Y-%m-%d')
    try:
        raw = _live_ohlc((sym, bench), start, end)
    except Exception:
        return
    r = split({sym: raw[sym], 'SPY': raw[bench]}, sym, call_date, timing_table().get(ticker.upper()))
    if not r:
        return
    when = ('before the market opened' if r['timing'] == 'before_open' else 'after the market closed')
    how = '' if r['timing_source'] == 'report_timing.csv' else ' (estimated from the prices)'
    st.markdown(f'<h4 style="color:{ui.SMITH_BLUE};margin:22px 0 4px">First reaction vs. readjustment</h4>'
                f'<p style="color:#3D4656;margin:0 0 6px">This company reports {when}{how}, so the first session after the results was '
                f'<b>{pd.Timestamp(r["reaction_date"]):%a %d %b %Y}</b>. Both moves are against the {esc(bench_label)}.</p>',
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.kpi('Overnight jump', f'{r["gap"]:+.1%}', 'Last close to the next open: the fast first reaction.',
               color=ui.OLIVE if r['gap'] >= 0 else ui.ROSE)
    with c2:
        ui.kpi('First trading session', f'{r["session"]:+.1%}', 'Open to close: the readjustment once people digested the call.',
               color=ui.OLIVE if r['session'] >= 0 else ui.ROSE)
    with c3:
        same = np.sign(r['gap']) == np.sign(r['session'])
        ui.kpi('What happened next', 'Kept going' if same else 'Reversed',
               'The session moved the same way as the overnight jump.' if same else
               'The session moved against the overnight jump: the first reaction was partly undone.', color=ui.SKY)
    st.caption('Daily open and close prices from Yahoo Finance. With daily data the overnight jump includes the release and, '
               'usually, the call itself.')
