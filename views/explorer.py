import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import data_access as da
import ui
from ui import term

bench = da.benchmark()
calibrated, counts = da.calibrated_sectors(bench)

ui.hero('Benchmark explorer', 'What the benchmark calls tell us',
        f'All {len(bench)} benchmark calls side by side: which sounded most positive, how tone changed once analysts started asking questions, '
        'and how different sectors talk. Use the filters to focus on a peer group or a year.')

f1, f2 = st.columns([1.4, 1])
groups = sorted(bench['group'].unique())
pick = f1.segmented_control('Peer group', groups, selection_mode='multi', default=groups)
years = sorted(bench['year'].unique())
ypick = f2.segmented_control('Year', years, selection_mode='multi', default=years) if len(years) > 1 else years
data = bench[bench['group'].isin(pick or groups) & bench['year'].isin(ypick or years)].copy()
st.caption(f'Showing {len(data)} calls · ' + ' · '.join(f'{(data["group"] == g).sum()} {g.lower()}' for g in (pick or groups)))
if data.empty:
    st.stop()

ui.section('01 · SENTIMENT', 'Which calls sounded most positive?',
           f'The {term("Overall score", "overall score")} combines three methods. Calls are split into thirds: '
           f'{ui.signal_chip("Positive")} {ui.signal_chip("Neutral")} {ui.signal_chip("Negative")}. Hover over a bar for details.')
rank_data = data
if len(data) > 40:
    rank_data = pd.concat([data.nlargest(15, 'composite'), data.nsmallest(15, 'composite')])
    st.caption(f'Showing the 15 most and 15 least positive of {len(data)} calls; the full list is in section 07.')
rank = alt.Chart(rank_data).mark_bar(cornerRadiusEnd=3).encode(
    y=alt.Y('label:N', sort='-x', title=None, axis=alt.Axis(labelLimit=240)),
    x=alt.X('composite:Q', title='Overall score (0 = average benchmark call)'),
    color=alt.Color('signal:N', scale=alt.Scale(domain=list(ui.SIGNAL_COLORS), range=list(ui.SIGNAL_COLORS.values())), legend=None),
    tooltip=['label', 'sector', 'signal', alt.Tooltip('composite:Q', format='+.2f', title='Overall score'),
             alt.Tooltip('lm_tone:Q', format='.2f', title='Tone'), alt.Tooltip('vader:Q', format='.3f', title='VADER')])
st.altair_chart(rank.properties(height=max(220, 26 * len(rank_data))), width='stretch')

with st.expander('Do the three methods agree?'):
    corr = data[['lm_tone', 'vader', 'textblob']].corr(method='spearman')
    corr.index = corr.columns = ['Finance dictionary', 'VADER', 'TextBlob']
    m = corr.reset_index().melt('index', var_name='method', value_name='rho')
    heat = alt.Chart(m).mark_rect().encode(
        x=alt.X('method:N', title=None), y=alt.Y('index:N', title=None),
        color=alt.Color('rho:Q', scale=alt.Scale(scheme='blues', domain=[0, 1]), legend=None), tooltip=[alt.Tooltip('rho:Q', format='.2f')])
    txt = heat.mark_text(fontSize=14, fontWeight='bold').encode(text=alt.Text('rho:Q', format='.2f'), color=alt.value(ui.SMITH_BLUE))
    st.altair_chart((heat + txt).properties(height=220), width='stretch')
    ui.note(f'Rank {term("Correlation", "correlations")} between the methods. Values near 1 mean the methods rank calls the same way. '
            'The finance dictionary is our main measure because it is built for financial language; the two general tools act as a cross-check.')

ui.section('02 · SCRIPT VS. LIVE', 'Does the message hold up under questioning?',
           f'Each row compares management\'s tone in the {term("Prepared presentation", "prepared presentation")} with its tone when answering analysts '
           f'in the {term("Q&A")}. Rows are sorted by the {term("Tone change into Q&A", "tone change")}, biggest drop first.')
fell = int((data['tone_shift'] < 0).sum())
ui.note(f'<b>{fell} of {len(data)}</b> calls sounded less positive in the live Q&A than in the script.')
dd = data[['label', 'pres_tone', 'qa_mgmt_tone', 'tone_shift']].dropna()
order = dd.sort_values('tone_shift')['label'].tolist()
long = dd.melt(['label', 'tone_shift'], ['pres_tone', 'qa_mgmt_tone'], var_name='part', value_name='tone')
long['part'] = long['part'].map({'pres_tone': 'Prepared presentation', 'qa_mgmt_tone': 'Answers in Q&A'})
rule = alt.Chart(dd).mark_rule(color='#B9C3D3', strokeWidth=2).encode(
    y=alt.Y('label:N', sort=order, title=None, axis=alt.Axis(labelLimit=240)), x='pres_tone:Q', x2='qa_mgmt_tone:Q')
pts = alt.Chart(long).mark_circle(size=110, opacity=1).encode(
    y=alt.Y('label:N', sort=order), x=alt.X('tone:Q', title='Tone (net positive words per 100)'),
    color=alt.Color('part:N', scale=alt.Scale(domain=['Prepared presentation', 'Answers in Q&A'], range=[ui.SKY, ui.ROSE])),
    tooltip=['label', 'part', alt.Tooltip('tone:Q', format='.2f'), alt.Tooltip('tone_shift:Q', format='+.2f', title='Change')])
st.altair_chart((rule + pts).properties(height=max(220, 26 * len(dd))), width='stretch')

ui.section('03 · THROUGH THE CALL', 'How tone moves from start to finish',
           'Each call is cut into ten equal parts. The lines show the average tone of each part by sector.')
seg = da.segments()
if seg is not None:
    seg = seg[seg['call_id'].isin(data['call_id'])]
    avg = seg.groupby(['sector', 'segment'])['lm_tone'].mean().reset_index()
    prog = alt.Chart(avg).mark_line(point=alt.OverlayMarkDef(size=50), strokeWidth=2.5).encode(
        x=alt.X('segment:Q', title='Start of call → end of call (tenths)', scale=alt.Scale(domain=[1, 10])),
        y=alt.Y('lm_tone:Q', title='Average tone'), color=alt.Color('sector:N'),
        tooltip=['sector', 'segment', alt.Tooltip('lm_tone:Q', format='.2f')])
    st.altair_chart(prog.properties(height=280), width='stretch')

ui.section('04 · PRESSURE', 'Analyst pushback vs. management response',
           f'Further right: tougher questions ({term("Analyst pushback", "analyst pushback")}). Higher up: management answered in a more positive tone '
           f'than it was asked. Dot size reflects {term("Management conviction", "management conviction")}.')
sc_df = data.dropna(subset=['analyst_neg_rate', 'conviction_gap']).copy()
sc_df['conv_size'] = sc_df['conviction_score'] - sc_df['conviction_score'].min() + 0.3
scatter = alt.Chart(sc_df).mark_circle(opacity=0.85, stroke='white', strokeWidth=1.5).encode(
    x=alt.X('analyst_neg_rate:Q', title='Analyst pushback (negative words per 100)'),
    y=alt.Y('conviction_gap:Q', title='Answers minus questions (tone)'),
    size=alt.Size('conv_size:Q', legend=None, scale=alt.Scale(range=[60, 600])), color=alt.Color('sector:N'),
    tooltip=['label', 'sector', alt.Tooltip('analyst_neg_rate:Q', format='.2f', title='Pushback'),
             alt.Tooltip('conviction_gap:Q', format='+.2f', title='Answers vs questions'), alt.Tooltip('conviction_score:Q', format='+.2f', title='Conviction')])
zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color=ui.LINE).encode(y='y:Q')
st.altair_chart((zero + scatter).properties(height=340), width='stretch')
top = sc_df.nlargest(2, 'conviction_score')['label'].tolist()
low = sc_df.nsmallest(2, 'conviction_score')['label'].tolist()
ui.note(f'Highest conviction: <b>{", ".join(top)}</b>. Lowest: <b>{", ".join(low)}</b>, where management answered less positively than it was asked.')

ui.section('05 · SECTORS', 'Each sector speaks its own language',
           f'Averages by sector. The {term("Sector-adjusted tone", "sector-adjusted tone")} ignores routine jargon (for banks: "stress test", '
           '"credit losses"; for tech: "mission-critical", "high conviction").')
cols = {'lm_tone': 'Tone', 'lm_tone_sector': 'Sector-adjusted tone', 'vader': 'VADER', 'tone_shift': 'Tone change into Q&A',
        'analyst_neg_rate': 'Analyst pushback', 'conviction_score': 'Management conviction'}
tab = data.groupby('sector')[[c for c in cols if c in data]].mean().rename(columns=cols)
tab.insert(0, 'Calls', data.groupby('sector').size())
st.dataframe(tab.style.format({c: '{:.2f}' for c in tab.columns if c != 'Calls'}), width='stretch')
if {'Bank', 'Tech'} <= set(data['sector']) and 'lm_tone_sector' in data:
    g0 = tab.loc['Bank', 'Tone'] - tab.loc['Tech', 'Tone']
    g1 = tab.loc['Bank', 'Sector-adjusted tone'] - tab.loc['Tech', 'Sector-adjusted tone']
    ui.note(f'<b>Honest result:</b> the sector dictionary narrows the bank-tech tone gap from {g0:.2f} to {g1:.2f} '
            f'({(1 - g1 / g0):.0%} smaller). Jargon explains part of why banks score lower, not all of it, which is why we compare banks with banks.')

ui.section('06 · OVER TIME', 'How tone moved quarter by quarter',
           'Average tone of each peer group by quarter. Watch March 2023, when Silicon Valley Bank failed: did regional banks sound '
           'more cautious than large banks in the calls that followed?')
by_q = data.groupby(['quarter', 'group']).agg(tone=('lm_tone', 'mean'), shift=('tone_shift', 'mean'), pushback=('analyst_neg_rate', 'mean'), calls=('call_id', 'count')).reset_index()
if by_q['quarter'].nunique() >= 2:
    metric = st.radio('Measure', ['Tone', 'Tone change into Q&A', 'Analyst pushback'], horizontal=True, label_visibility='collapsed')
    col = {'Tone': 'tone', 'Tone change into Q&A': 'shift', 'Analyst pushback': 'pushback'}[metric]
    ln = alt.Chart(by_q).mark_line(point=alt.OverlayMarkDef(size=50, filled=True), strokeWidth=2.4).encode(
        x=alt.X('quarter:O', title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y(f'{col}:Q', title=metric),
        color=alt.Color('group:N', title=None), tooltip=['quarter', 'group', alt.Tooltip(f'{col}:Q', format='.2f'), 'calls'])
    st.altair_chart(ln.properties(height=320), width='stretch')
else:
    ui.note('This chart appears once the benchmark covers more than one quarter (e.g. after adding the 2023–2024 transcripts).')

ui.section('07 · DATA', 'All benchmark calls')
show = data[['label', 'sector', 'signal', 'composite', 'lm_tone', 'lm_tone_sector', 'pres_tone', 'qa_mgmt_tone', 'tone_shift', 'analyst_neg_rate', 'conviction_score']]
st.dataframe(show.sort_values('composite', ascending=False), hide_index=True, width='stretch',
             column_config={'label': 'Call', 'sector': 'Sector', 'signal': 'Signal',
                            'composite': st.column_config.NumberColumn('Overall score', format='%+.2f'),
                            'lm_tone': st.column_config.NumberColumn('Tone', format='%.2f'),
                            'lm_tone_sector': st.column_config.NumberColumn('Sector-adj. tone', format='%.2f'),
                            'pres_tone': st.column_config.NumberColumn('Presentation', format='%.2f'),
                            'qa_mgmt_tone': st.column_config.NumberColumn('Q&A answers', format='%.2f'),
                            'tone_shift': st.column_config.NumberColumn('Change into Q&A', format='%+.2f'),
                            'analyst_neg_rate': st.column_config.NumberColumn('Pushback', format='%.2f'),
                            'conviction_score': st.column_config.NumberColumn('Conviction', format='%+.2f')})
ui.footer()
