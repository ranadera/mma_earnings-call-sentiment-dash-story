import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import data_access as da
import ui
from ui import term

METHODS = {'lm_tone': 'Finance dictionary', 'vader': 'VADER', 'textblob': 'TextBlob'}
SECTOR_COLORS = alt.Scale(domain=['Bank', 'Tech'], range=[ui.SECTOR_PALETTE[0], ui.SECTOR_PALETTE[1]])

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

ui.section('01 · SECTORS', 'Each sector speaks its own language',
           f'Averages by sector. The {term("Sector-adjusted tone", "sector-adjusted tone")} ignores routine jargon (for banks: "stress test", '
           '"credit losses"; for tech: "mission-critical", "high conviction").')
cols = {'lm_tone': 'Tone', 'lm_tone_sector': 'Sector-adjusted tone', 'vader': 'VADER', 'tone_shift': 'Tone change into Q&A',
        'analyst_neg_rate': 'Analyst pushback', 'conviction_score': 'Management conviction'}
tab = data.groupby('sector')[[c for c in cols if c in data]].mean().rename(columns=cols)
tab.insert(0, 'Calls', data.groupby('sector').size())
st.dataframe(tab.style.format({c: '{:.2f}' for c in tab.columns if c != 'Calls'}), width='stretch')
both = {'Bank', 'Tech'} <= set(data['sector'])
if both and 'lm_tone_sector' in data:
    g0 = tab.loc['Bank', 'Tone'] - tab.loc['Tech', 'Tone']
    g1 = tab.loc['Bank', 'Sector-adjusted tone'] - tab.loc['Tech', 'Sector-adjusted tone']
    ui.note(f'<b>Honest result:</b> the sector dictionary narrows the bank-tech tone gap from {g0:.2f} to {g1:.2f} '
            f'({(1 - g1 / g0):.0%} smaller). Jargon explains part of why banks score lower, not all of it, which is why we compare banks with banks.')

# ---- three methods, same calls
st.markdown(f'<h4 style="color:{ui.SMITH_BLUE};margin:26px 0 2px">Three methods, the same calls</h4>'
            '<p style="color:#3D4656;margin:0 0 8px">We scored every call with a finance dictionary and two general-language tools. '
            'Sentiment has no answer key, so we compare them two ways: how each one sees banks against tech, and whether any of them '
            'lines up with how the stock moved.</p>', unsafe_allow_html=True)
ev = da.event_returns()
mdata = data.merge(ev[['call_id', 'car_day']], on='call_id', how='left') if ev is not None else data.assign(car_day=np.nan)
rows = []
for col, name in METHODS.items():
    gap = (1 - data.loc[data['sector'] == 'Bank', col].mean() / data.loc[data['sector'] == 'Tech', col].mean()) if both else np.nan
    ok = mdata.dropna(subset=[col, 'car_day'])
    rho = ok[col].corr(ok['car_day'], method='spearman') if len(ok) >= 10 else np.nan
    rows.append({'method': name, 'gap': gap, 'rho': rho})
mt = pd.DataFrame(rows)
c1, c2 = st.columns(2)
with c1:
    if both:
        st.markdown('**How much lower banks score than tech**')
        b = alt.Chart(mt).encode(y=alt.Y('method:N', title=None, sort=list(METHODS.values()), axis=alt.Axis(labelFontSize=12, labelLimit=200)),
                                 x=alt.X('gap:Q', title='Banks below tech (%)', axis=alt.Axis(format='%')))
        st.altair_chart((b.mark_bar(cornerRadiusEnd=4, color=ui.SMITH_BLUE)
                         + b.mark_text(align='left', dx=5, fontWeight='bold').encode(text=alt.Text('gap:Q', format='.0%'))).properties(height=150),
                        width='stretch')
        lm_gap, gen_gap = mt.loc[0, 'gap'], mt.loc[1:, 'gap'].mean()
        st.caption(f'The finance dictionary sees banks as {lm_gap:.0%} less upbeat than tech; the general-language tools see a gap of about '
                   f'{gen_gap:.0%}. Bank vocabulary ("loss", "risk", "provision") weighs heavily in a finance dictionary.')
with c2:
    st.markdown('**Does the score line up with the stock\'s move?**')
    b = alt.Chart(mt.dropna(subset=['rho'])).encode(
        y=alt.Y('method:N', title=None, sort=list(METHODS.values()), axis=alt.Axis(labelFontSize=12, labelLimit=200)),
        x=alt.X('rho:Q', title='Rank correlation with the 2-day move', scale=alt.Scale(domain=[-1, 1])))
    st.altair_chart((b.mark_bar(cornerRadiusEnd=4, color=ui.AZURE)
                     + b.mark_text(align='left', dx=5, fontWeight='bold').encode(text=alt.Text('rho:Q', format='+.2f'))
                     + alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(color=ui.MUTED).encode(x='x:Q')).properties(height=150), width='stretch')
    st.caption('0 means no link; 1 would mean the most upbeat calls always had the best stock reaction. All three are close to 0.')
agree = data[list(METHODS)].corr(method='spearman')
low = agree.where(~np.eye(len(agree), dtype=bool)).min().min()
ui.note(f'<b>Takeaway:</b> the three methods mostly agree on which calls sound more upbeat (rank correlations of {low:.2f} or higher), '
        'and none of them predicts the stock. Choosing a different dictionary would not change our conclusion.')

ui.section('02 · SENTIMENT', 'Which calls sounded most positive?',
           f'Rank the calls by our {term("Overall score", "overall score")} (all three methods combined) or by one method at a time. '
           'Hover over a bar for details.')
method = st.segmented_control('Rank by', ['Overall score'] + list(METHODS.values()), default='Overall score', key='rank_method')
col = {'Overall score': 'composite', **{v: k for k, v in METHODS.items()}}[method or 'Overall score']
rank_data = data
if len(data) > 40:
    rank_data = pd.concat([data.nlargest(15, col), data.nsmallest(15, col)])
    st.caption(f'Showing the 15 highest and 15 lowest of {len(data)} calls; the full list is in section 07.')
color = (alt.Color('signal:N', scale=alt.Scale(domain=list(ui.SIGNAL_COLORS), range=list(ui.SIGNAL_COLORS.values())),
                   legend=alt.Legend(orient='top', title=None)) if col == 'composite'
         else alt.Color('sector:N', scale=SECTOR_COLORS, legend=alt.Legend(orient='top', title=None)))
rank = alt.Chart(rank_data).mark_bar(cornerRadiusEnd=3).encode(
    y=alt.Y('label:N', sort='-x', title=None, axis=alt.Axis(labelLimit=240)),
    x=alt.X(f'{col}:Q', title=method if col != 'composite' else 'Overall score (0 = average benchmark call)'), color=color,
    tooltip=['label', 'sector', 'signal', alt.Tooltip('composite:Q', format='+.2f', title='Overall score'),
             alt.Tooltip('lm_tone:Q', format='.2f', title='Finance dictionary'), alt.Tooltip('vader:Q', format='.3f', title='VADER'),
             alt.Tooltip('textblob:Q', format='.3f', title='TextBlob')])
st.altair_chart(rank.properties(height=max(220, 26 * len(rank_data))), width='stretch')
if col != 'composite':
    st.caption('Coloured by sector: with a single method, notice how the sectors bunch together.')

ui.section('03 · SCRIPT VS. LIVE', 'Does the message hold up under questioning?',
           'Each bar is one call. Green: more upbeat in the live Q&amp;A. Red: less upbeat.')
view = st.segmented_control('Compare', ["Management: script vs. live answers", "Management's answers vs. analysts' questions"],
                            default="Management: script vs. live answers", key='delta_view')
if view == "Management's answers vs. analysts' questions":
    dcol, dlabel = 'conviction_gap', 'Management answers minus analyst questions (tone)'
    fell = int((data[dcol] < 0).sum())
    ui.note(f'In <b>{fell} of {data[dcol].notna().sum()}</b> calls, management answered in a less upbeat tone than the analysts asked.')
else:
    dcol, dlabel = 'tone_shift', 'Live answers minus prepared script (tone)'
    fell = int((data[dcol] < 0).sum())
    ui.note(f'<b>{fell} of {data[dcol].notna().sum()}</b> calls sounded less upbeat in the live Q&amp;A than in the script.')
dd = data[['label', 'sector', dcol]].dropna()
show_all = st.toggle('Show all calls', value=len(dd) <= 40, key='delta_all')
dd_show = dd if show_all or len(dd) <= 40 else pd.concat([dd.nsmallest(15, dcol), dd.nlargest(15, dcol)])
if not show_all and len(dd) > 40:
    st.caption(f'Showing the 15 biggest drops and 15 biggest gains of {len(dd)} calls.')
dd_show = dd_show.assign(direction=np.where(dd_show[dcol] >= 0, 'More upbeat', 'Less upbeat'))
bars = alt.Chart(dd_show).mark_bar(cornerRadius=2).encode(
    y=alt.Y('label:N', sort=alt.EncodingSortField(field=dcol, order='ascending'), title=None,
            axis=alt.Axis(labelLimit=240, labelOverlap=False), scale=alt.Scale(paddingInner=0.25)),
    x=alt.X(f'{dcol}:Q', title=dlabel),
    color=alt.Color('direction:N', scale=alt.Scale(domain=['More upbeat', 'Less upbeat'], range=[ui.OLIVE, ui.ROSE]),
                    legend=alt.Legend(orient='top', title=None)),
    tooltip=['label', 'sector', alt.Tooltip(f'{dcol}:Q', format='+.2f', title='Change')])
zero = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(color=ui.MUTED).encode(x='x:Q')
st.altair_chart((bars + zero).properties(height=max(220, 24 * len(dd_show))), width='stretch')

ui.section('04 · THROUGH THE CALL', 'How tone moves from start to finish',
           'Each call is cut into ten equal parts. The lines show the average tone of each part by sector; the dashed lines mark '
           'where the Q&amp;A starts, on average.')
seg = da.segments()
if seg is not None:
    seg = seg[seg['call_id'].isin(data['call_id'])]
    avg = seg.groupby(['sector', 'segment'])['lm_tone'].mean().reset_index()
    prog = alt.Chart(avg).mark_line(point=alt.OverlayMarkDef(size=50), strokeWidth=2.5).encode(
        x=alt.X('segment:Q', title='Start of call → end of call (tenths)', scale=alt.Scale(domain=[1, 10])),
        y=alt.Y('lm_tone:Q', title='Average tone'), color=alt.Color('sector:N', scale=SECTOR_COLORS, legend=alt.Legend(orient='top', title=None)),
        tooltip=['sector', 'segment', alt.Tooltip('lm_tone:Q', format='.2f')])
    layers = prog
    if 'qa_start' in data and data['qa_start'].notna().any():
        qa = data.dropna(subset=['qa_start']).groupby('sector')['qa_start'].mean().reset_index()
        qa['x'] = (qa['qa_start'] + 0.5).clip(1, 10)   # tenths 0-10 -> segment axis 1-10 (segment k covers tenths k-1..k)
        qa['label'] = 'Q&A starts (' + qa['sector'] + ' avg)'
        layers = (prog + alt.Chart(qa).mark_rule(strokeDash=[6, 4], strokeWidth=2).encode(
                      x='x:Q', color=alt.Color('sector:N', scale=SECTOR_COLORS, legend=None), tooltip=['label'])
                  + alt.Chart(qa).mark_text(align='left', dx=4, dy=-6, fontWeight='bold', fontSize=11).encode(
                      x='x:Q', y=alt.value(12), text='label:N', color=alt.Color('sector:N', scale=SECTOR_COLORS, legend=None)))
    else:
        st.caption('The Q&A marker appears after the next data update.')
    st.altair_chart(layers.properties(height=300), width='stretch')

ui.section('05 · PRESSURE', 'Analyst pushback vs. management response',
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

ui.section('06 · OVER TIME', 'How tone moved quarter by quarter',
           'Three measures on the same timeline, one chart each so every measure keeps its own scale. Watch March 2023, when Silicon Valley '
           'Bank failed: did banks sound more cautious in the calls that followed?')
secs = [s for s in ['Bank', 'Tech'] if s in set(data['sector'])]
spick = st.segmented_control('Sector', secs, selection_mode='multi', default=secs, key='time_sectors',
                             format_func=lambda s: {'Bank': 'Banks', 'Tech': 'Tech'}.get(s, s)) if len(secs) > 1 else secs
tdata = data[data['sector'].isin(spick or secs)]
by_q = tdata.groupby(['quarter', 'sector']).agg(tone=('lm_tone', 'mean'), shift=('tone_shift', 'mean'), pushback=('analyst_neg_rate', 'mean'),
                                                 calls=('call_id', 'count')).reset_index()
if by_q['quarter'].nunique() >= 2:
    charts = []
    for i, (c, t) in enumerate([('tone', 'Tone'), ('shift', 'Tone change into Q&A'), ('pushback', 'Analyst pushback')]):
        charts.append(alt.Chart(by_q).mark_line(point=alt.OverlayMarkDef(size=45, filled=True), strokeWidth=2.4).encode(
            x=alt.X('quarter:O', title=None, axis=alt.Axis(labelAngle=0, labels=i == 2)),
            y=alt.Y(f'{c}:Q', title=None),
            color=alt.Color('sector:N', scale=SECTOR_COLORS, legend=alt.Legend(orient='top', title=None) if i == 0 else None),
            tooltip=['quarter', 'sector', alt.Tooltip(f'{c}:Q', format='.2f', title=t), 'calls']).properties(
            height=140, title=alt.TitleParams(t, anchor='start', fontSize=13, color=ui.SMITH_BLUE)))
    st.altair_chart(alt.vconcat(*charts, spacing=26).resolve_scale(color='shared'), width='stretch')
    st.caption('Tone: net upbeat words per 100. Tone change into Q&A: live answers minus script (below 0 = less upbeat live). '
               'Analyst pushback: negative words per 100 in analysts\' questions. Hover a point for the number of calls behind it.')
else:
    ui.note('This chart appears once the benchmark covers more than one quarter.')

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
