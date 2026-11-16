import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import data_access as da
import market as mk
import ui
from ui import term

bench = da.benchmark()

ui.hero('Market reaction', 'Did the tone line up with the stock move?',
        f'For every benchmark call we look at the stock from one month before to one month after the call, measure how it moved '
        f'relative to the market, and test whether the sentiment measures could have driven a trading strategy.')

st.markdown(f"""<div class="qm-steps">
<div class="qm-step"><span class="n">THE METHOD</span><h5>{term('Event study', 'Event study')}</h5><p>Daily prices from 21 trading days before to 21 after each call (about ±1 month).</p></div>
<div class="qm-step"><span class="n">THE MEASURE</span><h5>{term('Abnormal return', 'Abnormal return')}</h5><p>Stock return minus the benchmark's return each day, so market-wide moves are removed.</p></div>
<div class="qm-step"><span class="n">THE WINDOWS</span><h5>Day, week, month</h5><p>Reaction over the call day and next day, the first week, and the first month after the call.</p></div>
<div class="qm-step"><span class="n">THE TEST</span><h5>{term('Long-short strategy', 'Long-short strategy')}</h5><p>Buy Positive calls, short Negative ones, entering the day after the call so no information is used early.</p></div>
</div>""", unsafe_allow_html=True)
st.write('')

c1, c2 = st.columns([1.2, 2])
bench_choice = c1.radio('Compare each stock with', ['S&P 500 (SPY)', 'Its sector ETF (XLK for tech, KBE for banks)'], horizontal=False)
c2.markdown('<div class="qm-note" style="margin-top:4px">Comparing with the sector ETF asks a sharper question: did the bank beat <i>other banks</i>? '
            'Comparing with the S&amp;P 500 asks whether it beat the market as a whole.</div>', unsafe_allow_html=True)

calls = bench[['call_id', 'ticker', 'call_date', 'sector', 'signal', 'label', 'composite', 'lm_tone', 'tone_shift', 'conviction_score', 'analyst_neg_rate']].copy()
with st.spinner('Fetching prices for all benchmark calls (first load takes a few seconds)...'):
    if bench_choice.startswith('S&P'):
        cars, paths, source = mk.benchmark_event_study(calls[['call_id', 'ticker', 'call_date']])
    else:
        parts_c, parts_p, source = [], [], None
        for sec, etf in mk.SECTOR_ETF.items():
            sub = calls[calls['sector'] == sec]
            if sub.empty:
                continue
            c_, p_, source = mk.benchmark_event_study(sub[['call_id', 'ticker', 'call_date']], benchmark=etf)
            if c_ is not None:
                parts_c.append(c_)
                parts_p.append(p_)
        cars = pd.concat(parts_c) if parts_c else None
        paths = pd.concat(parts_p) if parts_p else None

if cars is None:
    ui.warn(f'<b>Live market data could not be loaded.</b> {source} This page needs prices from Yahoo Finance. Try again in a minute, or add a '
            '<code>data/prices.csv</code> file (exported from the project\'s event-study notebook) to the repository so the page works offline.')
    ui.footer()
    st.stop()

data = calls.merge(cars, on='call_id')
st.caption(f'{len(data)} calls with price data · Source: {source}')

ui.section('01 · THE PICTURE', 'Average stock path by sentiment signal',
           f'Average {term("Cumulative abnormal return (CAR)", "cumulative abnormal return")} of the calls in each signal group, starting from the close the day before the call.')
paths = paths.merge(calls[['call_id', 'signal']], on='call_id')
avg = paths.groupby(['signal', 'day'])['abn_ret'].mean().reset_index()
avg = avg.sort_values('day')
avg['car'] = np.nan
for s in avg['signal'].unique():
    m = avg['signal'] == s
    pre = avg[m & (avg['day'] < 0)]
    post = avg[m & (avg['day'] >= 0)]
    avg.loc[pre.index, 'car'] = -(pre['abn_ret'][::-1].cumsum()[::-1] - pre['abn_ret'])
    avg.loc[post.index, 'car'] = post['abn_ret'].cumsum()
n = data['signal'].value_counts()
avg['group'] = avg['signal'] + ' calls (n=' + avg['signal'].map(n).astype(str) + ')'
dom = [f'{s} calls (n={n.get(s, 0)})' for s in ui.SIGNAL_COLORS]
line = alt.Chart(avg).mark_line(strokeWidth=2.8).encode(
    x=alt.X('day:Q', title='Trading days from the call (0 = call day)'),
    y=alt.Y('car:Q', title='Average cumulative abnormal return', axis=alt.Axis(format='%')),
    color=alt.Color('group:N', scale=alt.Scale(domain=dom, range=list(ui.SIGNAL_COLORS.values()))),
    tooltip=['group', 'day', alt.Tooltip('car:Q', format='+.2%', title='Average CAR')])
zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color=ui.LINE).encode(y='y:Q')
day0 = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(strokeDash=[4, 4], color=ui.MUTED).encode(x='x:Q')
st.altair_chart(alt.layer(zero, day0, line).properties(height=320), width='stretch')

k = st.columns(3)
for col, (label, key) in zip(k, [('Day (0 to +1)', 'car_day'), ('Week (0 to +5)', 'car_week'), ('Month (0 to +21)', 'car_month')]):
    pos = data.loc[data['signal'] == 'Positive', key].mean()
    neg = data.loc[data['signal'] == 'Negative', key].mean()
    gap = pos - neg
    with col:
        ui.kpi(f'{label}: Positive minus Negative', f'{gap:+.2%}' if np.isfinite(gap) else 'n/a',
               f'Positive calls averaged <b>{pos:+.2%}</b>, Negative calls <b>{neg:+.2%}</b>.', color=ui.OLIVE if gap >= 0 else ui.ROSE)

ui.section('02 · CORRELATION', 'Which sentiment measures relate to returns?',
           f'Spearman {term("Correlation", "correlation")} between each measure and the stock\'s abnormal return in each window. '
           f'A star marks a {term("p-value", "p-value")} below 0.05.')
measures = {'composite': 'Overall score', 'lm_tone': 'Tone', 'tone_shift': 'Tone change into Q&A',
            'conviction_score': 'Management conviction', 'analyst_neg_rate': 'Analyst pushback'}
windows = {'car_pre': 'Month before', 'car_day': 'Day', 'car_week': 'Week', 'car_month': 'Month after'}
corr = mk.correlations(data, list(measures), list(windows))
if not corr.empty:
    corr['Measure'] = corr['measure'].map(measures)
    corr['Window'] = corr['window'].map(windows)
    corr['label'] = corr['rho'].map('{:+.2f}'.format) + np.where(corr['p'] < 0.05, '*', '')
    base = alt.Chart(corr).encode(x=alt.X('Window:N', sort=list(windows.values()), title=None, axis=alt.Axis(labelAngle=0, orient='top')),
                                  y=alt.Y('Measure:N', sort=list(measures.values()), title=None, axis=alt.Axis(labelLimit=200)))
    heat = base.mark_rect(cornerRadius=3).encode(color=alt.Color('rho:Q', scale=alt.Scale(scheme='redblue', domain=[-0.8, 0.8]), legend=None),
                                                 tooltip=['Measure', 'Window', alt.Tooltip('rho:Q', format='+.2f'), alt.Tooltip('p:Q', format='.3f'), 'n'])
    txt = base.mark_text(fontSize=13, fontWeight='bold', color=ui.SMITH_BLUE).encode(text='label:N')
    st.altair_chart((heat + txt).properties(height=260), width='stretch')
    best = corr.loc[corr['window'] != 'car_pre'].sort_values('p').iloc[0]
    ui.note(f'Strongest post-call relationship: <b>{best["Measure"]}</b> with the <b>{best["Window"].lower()}</b> return '
            f'(correlation {best["rho"]:+.2f}, p-value {best["p"]:.3f}). '
            + ('This is statistically significant.' if best['p'] < 0.05 else
               f'With only {int(best["n"])} calls this is <b>not</b> statistically significant: a real effect could exist, but this sample cannot confirm it.'))

ui.section('03 · STRATEGY', 'Could sentiment drive a long-short strategy?',
           f'Each signal splits calls into thirds. The {term("Long-short strategy", "strategy")} buys the top third and short-sells the bottom third, '
           'entering at the close the day after the call, hedged against the benchmark, with no trading costs.')
data['sig_shift'] = pd.qcut(data['tone_shift'], 3, labels=['Negative', 'Neutral', 'Positive'])
data['sig_conv'] = pd.qcut(data['conviction_score'], 3, labels=['Negative', 'Neutral', 'Positive'])
rows = []
for name, col in [('Overall sentiment', 'signal'), ('Tone change into Q&A', 'sig_shift'), ('Management conviction', 'sig_conv')]:
    for hold, ret in [('1 week', 'hold_week'), ('1 month', 'car_drift')]:
        r = mk.long_short(data, col, ret)
        if r:
            rows.append({'Signal': name, 'Holding': hold, 'Long leg': r['long'], 'Short leg': r['short'], 'Long-short return': r['spread'],
                         'Longs that rose': r['hit_long'], 'Shorts that fell': r['hit_short'], 'p-value': r['p']})
ls = pd.DataFrame(rows)
if not ls.empty:
    pretty = ls.copy()
    for c in ['Long leg', 'Short leg', 'Long-short return']:
        pretty[c] = pretty[c].map('{:+.2%}'.format)
    for c in ['Longs that rose', 'Shorts that fell']:
        pretty[c] = pretty[c].map('{:.0%}'.format)
    pretty['p-value'] = pretty['p-value'].map('{:.3f}'.format)
    st.dataframe(pretty, hide_index=True, width='stretch')
    best = ls.sort_values('Long-short return', ascending=False).iloc[0]
    ui.note(f'Best combination: <b>{best["Signal"]}</b> held for <b>{best["Holding"]}</b>, returning <b>{best["Long-short return"]:+.2%}</b> per trade '
            f'(p-value {best["p-value"]:.3f}). Week holding = days +2 to +5; month = days +2 to +21.')
ui.warn('<b>Read with care.</b> About 20 calls, clustered in the same weeks, no transaction or shorting costs. '
        'These results show how the test works; a real strategy needs hundreds of calls across several years. Not investment advice.')

ui.section('04 · PREDICTIVE MODEL', 'Train on one year, test on the next',
           'A logistic regression learns from the sentiment measures of earlier calls whether a stock beat the market, '
           'then predicts calls it has never seen. Testing on a later year is the honest way to check a trading signal: '
           'nothing from the test year is used in training.')
mr = da.model_results()
if not mr or mr.get('status') != 'ok' or not any(t.get('status') == 'ok' for t in mr.get('targets', {}).values()):
    ui.note('<b>Not trained yet.</b> ' + ((mr or {}).get('note') or 'The model needs calls from at least two years (e.g. 2023 and 2024).')
            + ' Add the 2023–2024 transcripts to the transcripts repository; the automated pipeline trains the model and updates this section.')
else:
    names = {'lm_tone': 'Tone', 'lm_tone_sector': 'Sector-adjusted tone', 'composite': 'Overall score', 'tone_shift': 'Tone change into Q&A',
             'conviction_score': 'Management conviction', 'analyst_neg_rate': 'Analyst pushback', 'hedging': 'Hedging'}
    st.caption(f"Trained on {', '.join(map(str, mr['train_years']))} · tested on {mr['test_year']}"
               + (f" · also checked on {', '.join(map(str, mr['later_years']))}" if mr.get('later_years') else '')
               + f" · updated {mr.get('updated', '')}")
    for key, r in mr['targets'].items():
        st.markdown(f"**{r['label']}**")
        if r.get('status') != 'ok':
            st.caption(r.get('status'))
            continue
        cols = st.columns(4)
        lift = r['accuracy'] - r['baseline_accuracy']
        with cols[0]:
            ui.kpi('Test accuracy', f"{r['accuracy']:.0%}", f"Always guessing the most common outcome: <b>{r['baseline_accuracy']:.0%}</b>",
                   color=ui.OLIVE if lift > 0 else ui.ROSE)
        with cols[1]:
            ui.kpi(term('AUC', 'AUC'), f"{r['auc']:.2f}" if r.get('auc') is not None else 'n/a', '0.5 = coin flip; 1.0 = perfect ranking', color=ui.SKY)
        with cols[2]:
            ui.kpi('Long-short (test year)', f"{r['long_short']:+.2%}", 'Top third of predicted calls minus bottom third', color=ui.OLIVE if r['long_short'] > 0 else ui.ROSE)
        with cols[3]:
            ui.kpi('Calls', f"{r['n_train']} → {r['n_test']}", 'training → test' + (f"; later-year accuracy <b>{r['later_accuracy']:.0%}</b> ({r['n_later']} calls)" if 'later_accuracy' in r else ''), color=ui.PUMPKIN)
        coef = pd.DataFrame([{'measure': names.get(k, k), 'weight': v} for k, v in r['coefficients'].items()])
        coef['direction'] = np.where(coef['weight'] >= 0, 'Higher → more likely to beat the market', 'Higher → less likely')
        ch = alt.Chart(coef).mark_bar(cornerRadiusEnd=3, size=18).encode(
            y=alt.Y('measure:N', sort='-x', title=None, axis=alt.Axis(labelLimit=200)),
            x=alt.X('weight:Q', title='Model weight (on standardised measures)'),
            color=alt.Color('direction:N', scale=alt.Scale(domain=['Higher → more likely to beat the market', 'Higher → less likely'], range=[ui.OLIVE, ui.ROSE]),
                            legend=alt.Legend(labelLimit=320)),
            tooltip=['measure', alt.Tooltip('weight:Q', format='+.2f')])
        st.altair_chart(ch.properties(height=alt.Step(28)), width='stretch')
    ui.note('<b>How to read it.</b> If test accuracy is not clearly above the "always guess" baseline, the sentiment measures do not predict '
            'returns out of sample, which is itself a valid finding. The weights show which measures the model leaned on; overlapping measures '
            '(tone, sector-adjusted tone, overall score) share credit, so read them together.')

with st.expander('Per-call returns'):
    show = data[['label', 'signal', 'composite', 'car_pre', 'car_day', 'car_week', 'car_month']].sort_values('composite', ascending=False)
    st.dataframe(show, hide_index=True, width='stretch', column_config={
        'label': 'Call', 'signal': 'Signal', 'composite': st.column_config.NumberColumn('Overall score', format='%+.2f'),
        'car_pre': st.column_config.NumberColumn('Month before', format='%+.3f'), 'car_day': st.column_config.NumberColumn('Day', format='%+.3f'),
        'car_week': st.column_config.NumberColumn('Week', format='%+.3f'), 'car_month': st.column_config.NumberColumn('Month after', format='%+.3f')})
ui.footer()
