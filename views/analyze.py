import datetime as dt
import os
from collections import Counter

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import data_access as da
import market as mk
import sentiment_core as sc
import ui
from ui import esc, term

bench = da.benchmark()
calibrated, counts = da.calibrated_sectors(bench)
sector_map = da.sector_map()
lexicon = da.lexicon()
PART_NAMES = {'presentation': 'Prepared presentation', 'qa_management': 'Management answers (Q&A)', 'qa_analyst': 'Analyst questions (Q&A)'}


@st.cache_data(show_spinner='Reading and scoring the transcript...')
def analyse(name, data, sector_for_lexicon):
    raw = sc.read_text(name, data)
    meta = sc.get_meta(raw)
    fmt, turns = sc.parse(raw)
    scored = sc.score_turns(turns, da.lm(), sc.neutral_terms(lexicon, sector_for_lexicon))
    segs, qa_start = sc.segments(scored, da.lm())
    return meta, fmt, scored, segs, qa_start


def detect_meta(name, data):
    return sc.get_meta(sc.read_text(name, data))


ui.hero('Analyze a call', 'Score any earnings call in seconds',
        'Upload a transcript (Bloomberg, LSEG or company investor-relations PDF) or paste the text of any earnings call. The app splits it into the scripted '
        'presentation and the live Q&amp;A, measures the tone of each part, compares it with its sector, and shows how the stock moved around the call.')

with st.sidebar:
    st.markdown('<div class="qm-side-brand">QUANTA-MENTALS<span>Call analyzer</span></div>', unsafe_allow_html=True)
    st.markdown('<p class="qm-side-h">1 · Transcript</p>', unsafe_allow_html=True)
    source = st.radio('Input', ['Upload a file', 'Paste text'], horizontal=True, label_visibility='collapsed')
    name, data = None, None
    if source == 'Upload a file':
        f = st.file_uploader('PDF or text file', type=['pdf', 'txt'], help='Bloomberg and LSEG PDFs are read automatically, including the ticker and date.')
        if f is not None:
            name, data = f.name, f.getvalue()
    else:
        text = st.text_area('Paste the transcript', height=220,
                            help='If the text contains a heading such as "Questions And Answers", the app splits the presentation from the Q&A.')
        if text.strip():
            name, data = 'pasted.txt', text.encode('utf-8')

    st.markdown('<p class="qm-side-h">2 · Company</p>', unsafe_allow_html=True)
    auto = detect_meta(name, data) if data else {'ticker': '', 'call_date': '', 'company': ''}
    ticker = st.text_input('Ticker', value=auto['ticker'], placeholder='e.g. JPM',
                           help='Read from the transcript when possible. Needed for the sector and the price reaction.').strip().upper()
    default_date = pd.to_datetime(auto['call_date']).date() if auto['call_date'] else None
    call_date = st.date_input('Call date', value=default_date, max_value=dt.date.today(), format='YYYY-MM-DD')

    st.markdown('<p class="qm-side-h">3 · Compare with</p>', unsafe_allow_html=True)
    detected, how = (sector_map.get(ticker), 'our sector map') if ticker in sector_map else (None, None)
    if ticker and not detected:
        detected, how = mk.yahoo_sector(ticker), 'Yahoo Finance'
    options = ['Auto-detect'] + calibrated + ['All benchmark calls']
    sector_choice = st.selectbox('Benchmark group', options, label_visibility='collapsed',
                                 help='Each sector has its own vocabulary (banks say credit, losses and reserves, which the finance dictionary counts as negative), '
                                      'so a call is best compared with its own sector.')
    if sector_choice == 'Auto-detect':
        st.caption(f'Detected: **{detected}** (from {how})' if detected else 'Enter a ticker to detect the sector.')
    st.markdown('<div class="qm-side-foot">Tone uses the Loughran-McDonald finance dictionary, cross-checked with VADER and TextBlob, '
                'on the same scale as the benchmark calls.</div>', unsafe_allow_html=True)

if data is None:
    ui.coverage_banner(bench, calibrated, counts)
    st.markdown("""<div class="qm-empty">""" + ui.icon("upload_file") + """
<h3>Start with a transcript</h3><p>Use the panel on the left to upload a Bloomberg, LSEG or company investor-relations PDF, or paste the text of any earnings call.</p></div>""",
                unsafe_allow_html=True)
    st.markdown(f"""<div class="qm-steps">
<div class="qm-step"><span class="n">1 · READ</span><h5>Split the call</h5><p>{term("Prepared presentation", "Prepared presentation")}, analyst questions and management answers.</p></div>
<div class="qm-step"><span class="n">2 · SCORE</span><h5>Measure tone</h5><p>Upbeat, downbeat and uncertain finance words, cross-checked by two general tools.</p></div>
<div class="qm-step"><span class="n">3 · COMPARE</span><h5>Against its sector</h5><p>Placed against bank or tech {term("Benchmark", "benchmark")} calls and given a {term("Signal", "signal")}.</p></div>
<div class="qm-step"><span class="n">4 · REACT</span><h5>Check the stock</h5><p>Live {term("Abnormal return", "abnormal return")} over the day, week and month after the call.</p></div>
</div>""", unsafe_allow_html=True)
    ui.footer()
    st.stop()

if sector_choice == 'Auto-detect':
    sector = detected if detected in calibrated else None
elif sector_choice == 'All benchmark calls':
    sector = None
else:
    sector = sector_choice
lex_sector = sector or detected

meta, fmt, scored, segs, qa_start = analyse(name, data, lex_sector)
if scored.empty or scored['n_words'].sum() < 200:
    ui.warn('Not enough text could be read from this file. If it is a scanned PDF, it needs text recognition (OCR) first.')
    st.stop()

res = sc.score_call(scored, bench, sector)
peers = bench[bench['sector'] == sector] if sector else bench
peer_word = f'{sector.lower()} calls' if sector else 'all benchmark calls'
company = meta['company'] or (da.SHORT_NAMES.get(ticker) or ticker or os.path.splitext(name)[0])

st.markdown(f'<div class="qm-company"><h3>{esc(company)}</h3><div class="meta">'
            + ' · '.join(esc(x) for x in [ticker, detected and f'{detected} sector', call_date and call_date.isoformat(), f'{fmt} format', f'compared with {peer_word}'] if x)
            + '</div></div>', unsafe_allow_html=True)
if sector_choice == 'Auto-detect' and sector is None:
    if detected:
        ui.warn(f'<b>{esc(ticker)}</b> is in the <b>{esc(detected)}</b> sector (from {how}). The benchmark covers {" and ".join(calibrated)} only so far, '
                f'so this call is compared with all {len(bench)} benchmark calls. Read the relative scores with care.')
    elif ticker:
        ui.warn(f'The sector of <b>{esc(ticker)}</b> could not be looked up, so this call is compared with all {len(bench)} benchmark calls. '
                f'Pick <b>Bank</b> or <b>Tech</b> under "Compare with" in the left panel if one fits.')
    else:
        ui.warn(f'No ticker was found in this text, so the sector is unknown and the call is compared with all {len(bench)} benchmark calls. '
                f'Enter the ticker in the left panel to compare it with its own sector and to see the price reaction.')
if fmt.startswith('Plain'):
    ui.warn('Speakers could not be identified in this text, so analyst questions and management answers cannot be separated. The overall tone is still valid; the Q&A measures are limited.')

mode = st.segmented_control('View', ['Story mode', 'Full analysis'], default='Story mode', key='view_mode',
                            help='Story mode tells what happened on the call in plain language. Full analysis shows every number, chart and the method.')
if mode != 'Full analysis':
    import call_story
    import features
    with st.spinner('Checking how the stock reacted...'):
        story_reaction = mk.call_reaction(ticker, call_date, detected)
    call_story.render(company=company, ticker=ticker, call_date=call_date, scored=scored, res=res, peers=peers, peer_word=peer_word,
                      lm=da.lm(), neutral=sc.neutral_terms(lexicon, lex_sector), reaction=story_reaction)
    if features.SHOW_PROF_MEHMET:
        import prof_mehmet
        prof_mehmet.render(res, peer_word, lex_sector,
                           None if 'error' in story_reaction else {k: story_reaction[k] for k in ('day', 'pre', 'week', 'size')})
    ui.references()
    ui.footer()
    st.stop()

pct = (peers['composite'] < res['composite']).mean()
color = ui.SIGNAL_COLORS[res['signal']]
reading = {'Positive': 'Management sounds clearly more upbeat than most calls.',
           'Neutral': 'Management sounds about as upbeat as a typical call.',
           'Negative': 'Management sounds more cautious than most calls.'}[res['signal']]
st.markdown(f'<div class="qm-signal"><div class="pill" style="background:{color}">{esc(res["signal"])}</div>'
            f'<div class="txt"><b>{term("Signal", "Sentiment signal")}.</b> {reading} This call is more positive than '
            f'<b>{pct:.0%}</b> of {esc(peer_word)}.</div></div>', unsafe_allow_html=True)


def fin(x):
    return x is not None and np.isfinite(x)


avg_tone = peers['lm_tone'].mean()
takes = [(f'{res["signal"]} overall',
          (f'Less positive than <b>every one</b> of the {esc(peer_word.removeprefix("all "))}. Tone' if pct == 0 else f'More positive than <b>every one</b> of the {esc(peer_word.removeprefix("all "))}. Tone' if pct == 1 else f'More positive than <b>{pct:.0%}</b> of {esc(peer_word)}. Tone')
          + f' of <b>{res["lm_tone"]:.2f}</b> net positive words per 100, '
          f'against an average of {avg_tone:.2f}.'
          + (f' Ignoring routine {esc(lex_sector.lower())} jargon, it is <b>{res["lm_tone_sector"]:.2f}</b>.' if lex_sector and fin(res['lm_tone_sector']) and abs(res['lm_tone_sector'] - res['lm_tone']) > 0.05 else ''))]
if fin(res['tone_shift']):
    fell_share = (peers['tone_shift'] < 0).mean()
    up = res['tone_shift'] >= 0
    hedge = ''
    if fin(res['hedging']):
        hedge = f' Uncertain words {"rose" if res["hedging"] > 0 else "fell"} by {abs(res["hedging"]):.2f} per 100 in the live answers.'
    takes.append(('Script vs. live answers',
                  f'Tone {"<b>held up</b>" if up else "<b>softened</b>"} from the scripted remarks ({res["pres_tone"]:.2f}) to the live answers '
                  f'({res["qa_mgmt_tone"]:.2f}). For comparison, tone fell in {fell_share:.0%} of {esc(peer_word)}.{hedge}'))
else:
    takes.append(('Script vs. live answers', 'Speakers could not be identified, so the scripted remarks and live answers cannot be compared. '
                  'Use a Bloomberg, LSEG or investor-relations transcript for this measure.'))
if fin(res['analyst_neg_rate']):
    a_avg = peers['analyst_neg_rate'].mean()
    tough = res['analyst_neg_rate'] > a_avg
    conv = res.get('conviction_score', np.nan)
    takes.append(('Analysts and conviction',
                  f'Analyst questions were <b>{"more" if tough else "less"} critical</b> than usual ({res["analyst_neg_rate"]:.2f} vs. {a_avg:.2f} negative words per 100).'
                  + (f' Management conviction of <b>{conv:+.2f}</b>: it held its message {"better" if conv >= 0 else "less well"} than the average call.' if fin(conv) else '')))
else:
    neg_top = Counter(w for ws in scored['neg_words'] for w in ws).most_common(3)
    takes.append(('What drove the tone', ('Most frequent negative words: ' + ', '.join(f'<b>{esc(w)}</b> ({c})' for w, c in neg_top) + '.')
                  if neg_top else 'No negative finance words were found in this text.'))
st.markdown('<div class="qm-takes"><div class="qm-takes-h">Top 3 takeaways</div><div class="qm-takes-g">'
            + ''.join(f'<div class="qm-take"><span class="n">{i}</span><h5>{esc(t)}</h5><p>{b}</p></div>' for i, (t, b) in enumerate(takes, 1))
            + '</div></div>', unsafe_allow_html=True)


def vs(value, avg, unit=''):
    if not np.isfinite(value) or not np.isfinite(avg):
        return ''
    diff = value - avg
    word = 'above' if diff >= 0 else 'below'
    return f'<b>{abs(diff):.2f}{unit} {word}</b> the {esc(sector.lower() if sector else "benchmark")} average ({avg:.2f})'


k = st.columns(5)
with k[0]:
    ui.kpi(term('Tone'), f"{res['lm_tone']:.2f}", vs(res['lm_tone'], peers['lm_tone'].mean()))
with k[1]:
    adj_avg = peers['lm_tone_sector'].mean() if 'lm_tone_sector' in peers else np.nan
    ui.kpi(term('Sector-adjusted tone'), f"{res['lm_tone_sector']:.2f}" if np.isfinite(res['lm_tone_sector']) else 'n/a',
           vs(res['lm_tone_sector'], adj_avg) or 'Ignores routine sector jargon.', color=ui.SKY)
with k[2]:
    ui.kpi(term('Overall score'), f"{res['composite']:+.2f}", '0 = average benchmark call; ±1 = one standard deviation.', color=color)
with k[3]:
    shift = res['tone_shift']
    ui.kpi(term('Tone change into Q&A'), f'{shift:+.2f}' if np.isfinite(shift) else 'n/a',
           ('Message <b>softened</b> under questioning.' if shift < 0 else 'Message <b>held or improved</b> in the Q&A.') if np.isfinite(shift) else 'Needs speaker labels.',
           color=ui.ROSE if np.isfinite(shift) and shift < 0 else ui.OLIVE)
with k[4]:
    conv = res['conviction_score']
    ui.kpi(term('Management conviction'), f'{conv:+.2f}' if np.isfinite(conv) else 'n/a',
           ('Held its message <b>better</b> than the average call.' if conv >= 0 else 'Held its message <b>less well</b> than the average call.') if np.isfinite(conv) else 'Needs speaker labels.',
           color=ui.OLIVE if np.isfinite(conv) and conv >= 0 else ui.ROSE)

ui.section('A · INSIDE THE CALL', 'Scripted remarks vs. live answers',
           f'Tone of each part of the call compared with the average of {esc(peer_word)}, and how tone moves from the first minute to the last.')
left, right = st.columns(2)
peer_name = f'{sector} average' if sector else 'Benchmark average'
with left:
    rows = []
    for p, label in PART_NAMES.items():
        g = scored[scored['part'] == p]
        if g['n_words'].sum() > 0:
            tone = (g['lm_pos'].sum() - g['lm_neg'].sum()) / g['n_words'].sum() * 100
            col = {'presentation': 'pres_tone', 'qa_management': 'qa_mgmt_tone', 'qa_analyst': 'analyst_tone'}[p]
            rows += [{'part': label, 'series': 'This call', 'tone': tone}, {'part': label, 'series': peer_name, 'tone': peers[col].mean()}]
    if rows:
        df = pd.DataFrame(rows)
        chart = alt.Chart(df).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y('part:N', title=None, sort=list(PART_NAMES.values()), axis=alt.Axis(labelLimit=220),
                    scale=alt.Scale(paddingInner=0.35, paddingOuter=0.2)),
            yOffset=alt.YOffset('series:N', sort=['This call', peer_name]),
            x=alt.X('tone:Q', title='Tone (net positive words per 100)'),
            color=alt.Color('series:N', scale=alt.Scale(domain=['This call', peer_name], range=[ui.AZURE, '#B9C3D3'])),
            tooltip=['part', 'series', alt.Tooltip('tone:Q', format='.2f')])
        zero = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(color=ui.MUTED).encode(x='x:Q')
        labels = alt.Chart(df).mark_text(align='left', dx=4, fontSize=11, color=ui.INK).encode(
            y=alt.Y('part:N', sort=list(PART_NAMES.values())), yOffset=alt.YOffset('series:N', sort=['This call', peer_name]),
            x=alt.X('pos:Q'), text=alt.Text('tone:Q', format='.2f')).transform_calculate(pos='max(datum.tone, 0)')
        st.altair_chart((chart + zero + labels).properties(height=250, title='Tone by part of the call'), width='stretch')
with right:
    line_df = segs.assign(series='This call')
    seg_all = da.segments()
    if seg_all is not None:
        sp = seg_all[seg_all['sector'] == sector] if sector else seg_all[seg_all['call_id'].isin(bench['call_id'])]
        line_df = pd.concat([line_df, sp.groupby('segment')['lm_tone'].mean().reset_index().assign(series=peer_name)])
    lines = alt.Chart(line_df).mark_line(point=alt.OverlayMarkDef(size=45), strokeWidth=2.5).encode(
        x=alt.X('segment:Q', title='Start of call → end of call (tenths)', scale=alt.Scale(domain=[1, 10])),
        y=alt.Y('lm_tone:Q', title='Tone'),
        color=alt.Color('series:N', scale=alt.Scale(domain=['This call', peer_name], range=[ui.AZURE, '#B9C3D3'])),
        tooltip=['series', 'segment', alt.Tooltip('lm_tone:Q', format='.2f')])
    layers = [lines]
    if qa_start is not None:
        layers.append(alt.Chart(pd.DataFrame({'x': [qa_start + 0.5], 't': ['Q&A starts']})).mark_rule(strokeDash=[4, 4], color=ui.MUTED).encode(x='x:Q', tooltip='t'))
    st.altair_chart(alt.layer(*layers).properties(height=250, title='How tone moves through the call'), width='stretch')
    st.caption('The dashed line marks where the Q&A starts.')

ui.section('B · SENTIMENT PROFILE', 'Fingerprint and question-by-question view',
           f'Left: each measure compared with {esc(peer_word)}, scaled so that right of the line is more upbeat or confident than average. '
           'Right: the tone of each analyst question and of management\'s answer to it, in the order they came.')
left, right = st.columns([1, 1.15])
with left:
    measures = [('Tone', 'lm_tone', 1), ('Sector-adjusted tone', 'lm_tone_sector', 1), ('VADER (general tool)', 'vader', 1),
                ('TextBlob (general tool)', 'textblob', 1), ('Fewer uncertain words', 'lm_uncertainty', -1),
                ('Tone held into Q&A', 'tone_shift', 1), ('Less hedging in Q&A', 'hedging', -1), ('Milder analyst questions', 'analyst_neg_rate', -1)]
    fp = []
    for label, col, sign in measures:
        if col in peers and fin(res.get(col)) and peers[col].std() > 0:
            fp.append({'measure': label, 'z': float(np.clip(sign * (res[col] - peers[col].mean()) / peers[col].std(), -3, 3))})
    if fp:
        fp = pd.DataFrame(fp)
        fp['side'] = np.where(fp['z'] >= 0, 'Above average', 'Below average')
        bars = alt.Chart(fp).mark_bar(cornerRadiusEnd=3, size=20).encode(
            y=alt.Y('measure:N', sort=[m[0] for m in measures], title=None, axis=alt.Axis(labelLimit=200)),
            x=alt.X('z:Q', title=f'Standard deviations from the {sector.lower() if sector else "benchmark"} average', scale=alt.Scale(domain=[-3, 3])),
            color=alt.Color('side:N', scale=alt.Scale(domain=['Above average', 'Below average'], range=[ui.OLIVE, ui.ROSE])),
            tooltip=['measure', alt.Tooltip('z:Q', format='+.2f', title='Std. deviations')])
        mid = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(color=ui.INK).encode(x='x:Q')
        st.altair_chart((bars + mid).properties(height=alt.Step(34), title='Sentiment fingerprint'), width='stretch')
with right:
    ex, cur, n = [], None, 0
    for _, r in scored[scored['part'].isin(['qa_analyst', 'qa_management'])].iterrows():
        if r['part'] == 'qa_analyst' and r['speaker'] != cur:
            cur, n = r['speaker'], n + 1
        if n:
            ex.append({'exchange': n, 'analyst': cur, 'who': 'Analyst question' if r['part'] == 'qa_analyst' else 'Management answer',
                       'pos': r['lm_pos'], 'neg': r['lm_neg'], 'words': r['n_words']})
    if ex:
        ex = pd.DataFrame(ex).groupby(['exchange', 'analyst', 'who'], as_index=False)[['pos', 'neg', 'words']].sum()
        ex = ex[ex['words'] >= 20]
        ex['tone'] = (ex['pos'] - ex['neg']) / ex['words'] * 100
    if isinstance(ex, pd.DataFrame) and ex['exchange'].nunique() >= 3:
        qa = alt.Chart(ex).mark_line(point=alt.OverlayMarkDef(size=55, filled=True), strokeWidth=2).encode(
            x=alt.X('exchange:O', title='Analyst exchange (in order)', axis=alt.Axis(labelAngle=0)),
            y=alt.Y('tone:Q', title='Tone'),
            color=alt.Color('who:N', scale=alt.Scale(domain=['Management answer', 'Analyst question'], range=[ui.SMITH_BLUE, '#D19A00'])),
            tooltip=['exchange', 'analyst', 'who', alt.Tooltip('tone:Q', format='.2f'), 'words'])
        zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color=ui.LINE).encode(y='y:Q')
        st.altair_chart((zero + qa).properties(height=300, title='Question by question'), width='stretch')
        worst = ex[ex['who'] == 'Analyst question'].nsmallest(1, 'tone')
        if not worst.empty:
            st.caption(f'Toughest question: exchange {int(worst["exchange"].iloc[0])} ({worst["analyst"].iloc[0]}). Hover over a point for the details.')
    else:
        ui.note('The question-by-question view needs a transcript with speaker labels (Bloomberg, LSEG or investor-relations format).')

ui.section('C · IN CONTEXT', 'Where this call sits among the benchmark',
           f'Every grey dot is a benchmark call; the blue diamond is this call. Dashed lines split the benchmark into Negative, Neutral and Positive thirds.')
strip = pd.concat([bench[['label', 'sector', 'composite', 'signal']].assign(kind='Benchmark calls'),
                   pd.DataFrame([{'label': 'This call', 'sector': detected or 'unknown', 'composite': res['composite'], 'signal': res['signal'], 'kind': 'This call'}])])
q1, q2 = bench['composite'].quantile([1 / 3, 2 / 3])
dots = alt.Chart(strip).mark_point(filled=True, opacity=0.9).encode(
    x=alt.X('composite:Q', title='Overall score (0 = average benchmark call)'),
    y=alt.Y('kind:N', title=None, sort=['This call', 'Benchmark calls']),
    color=alt.Color('kind:N', scale=alt.Scale(domain=['This call', 'Benchmark calls'], range=[ui.AZURE, '#9AA5B8']), legend=None),
    size=alt.Size('kind:N', scale=alt.Scale(domain=['This call', 'Benchmark calls'], range=[420, 90]), legend=None),
    shape=alt.Shape('kind:N', scale=alt.Scale(domain=['This call', 'Benchmark calls'], range=['diamond', 'circle']), legend=None),
    tooltip=['label', 'sector', 'signal', alt.Tooltip('composite:Q', format='+.2f')])
cuts = alt.Chart(pd.DataFrame({'x': [q1, q2]})).mark_rule(strokeDash=[4, 4], color='#C8CFDB').encode(x='x:Q')
st.altair_chart(alt.layer(cuts, dots).properties(height=140), width='stretch')

reaction = None
ui.section('D · MARKET REACTION', 'How the stock moved around this call',
           f'The line shows the stock\'s {term("Cumulative abnormal return (CAR)", "cumulative abnormal return")}: how much it beat or lagged the market, '
           'starting from the close the day before the call. Prices are fetched live from Yahoo Finance.')
if not ticker or not call_date:
    ui.note('Enter the <b>ticker</b> and <b>call date</b> above to see the price reaction.')
else:
    with st.spinner('Looking up the price symbol...'):
        pt = mk.resolve_ticker(ticker) or ticker
    mkt, mkt_label = mk.benchmark_for(pt)
    bench_etf = mk.SECTOR_ETF.get(detected) if mkt == mk.MARKET else None
    start = (pd.Timestamp(call_date) - pd.Timedelta(days=220)).strftime('%Y-%m-%d')
    end = min(pd.Timestamp(call_date) + pd.Timedelta(days=50), pd.Timestamp.today()).strftime('%Y-%m-%d')
    with st.spinner('Fetching prices...'):
        px, source = mk.prices(tuple([pt, mkt] + ([bench_etf] if bench_etf else [])), start, end)
    ev = mk.event_window(px, pt, call_date, mkt) if px is not None else None
    if ev is None:
        ui.warn(f'Price data for <b>{esc(ticker)}</b> could not be loaded. {esc(source or "")} The sentiment results above are unaffected.')
    else:
        ev_sec = mk.event_window(px, pt, call_date, bench_etf) if bench_etf else None

        def raw(ev, a, b, col):
            w = ev[(ev['day'] >= a) & (ev['day'] <= b)]
            return (1 + w[col]).prod() - 1 if not w.empty and w['day'].max() >= b else np.nan

        pre_car, day_car, week_car, month_car = mk.car(ev, -21, -1), mk.car(ev, 0, 1), mk.car(ev, 0, 5), mk.car(ev, 0, 21)
        stock_day, mkt_day = raw(ev, 0, 1, 'ret'), raw(ev, 0, 1, 'bench_ret')
        noise, est_n, est_window = mk.estimation_sd(px, pt, call_date, mkt)
        t_stat = day_car / (noise * np.sqrt(2)) if np.isfinite(day_car) and noise and noise > 0 else np.nan
        size = abs(t_stat) if np.isfinite(t_stat) else np.nan
        sec_day = mk.car(ev_sec, 0, 1) if ev_sec is not None else np.nan

        st.markdown(f"""<div class="qm-steps">
<div class="qm-step"><span class="n">THE QUESTION</span><h5>Did this call move the stock?</h5><p>We look at the stock from one month before to one month after the call.</p></div>
<div class="qm-step"><span class="n">THE ADJUSTMENT</span><h5>Remove the market's move</h5><p>Each day we subtract the {mkt_label}'s return, so a market-wide rally or sell-off is not credited to the call. This is the {term("Abnormal return", "abnormal return")}.</p></div>
<div class="qm-step"><span class="n">THE SIZE TEST</span><h5>Was the move unusual?</h5><p>We compare the move after the call with how much this stock normally wobbles against the market on an ordinary day.</p></div>
<div class="qm-step"><span class="n">THE VIEW</span><h5>Does it match the tone?</h5><p>We check whether the stock moved in the direction the call's tone suggested.</p></div>
</div>""", unsafe_allow_html=True)
        st.write('')

        st.caption('All four figures are abnormal returns: the stock\'s move minus the ' + mkt_label + '\'s move over the same days.')
        k = st.columns(4)
        cards = [('Month before (−21 to −1)', pre_car, 'Was the stock already rising or falling before the call?'),
                 ('Reaction (day 0 to +1)', day_car, f'Stock itself <b>{stock_day:+.1%}</b>, {mkt_label} <b>{mkt_day:+.1%}</b>' if np.isfinite(stock_day) else 'Not enough trading days yet'),
                 ('First week (0 to +5)', week_car, 'Did the reaction hold, grow or fade?'),
                 ('First month (0 to +21)', month_car, 'The longer-run move after the call')]
        for col, (label, v, note) in zip(k, cards):
            with col:
                ui.kpi(label, f'{v:+.1%}' if np.isfinite(v) else 'n/a', note,
                       color=ui.MUTED if not np.isfinite(v) else ui.OLIVE if v >= 0 else ui.ROSE)

        plot = ev.assign(benchmark=f'vs. {mkt_label} ({mkt.replace(".TO", "")})')
        if ev_sec is not None:
            plot = pd.concat([plot, ev_sec.assign(benchmark=f'vs. {detected} ETF ({bench_etf})')])
        band = alt.Chart(pd.DataFrame({'x': [0], 'x2': [1]})).mark_rect(color=ui.GOLD, opacity=0.18).encode(x='x:Q', x2='x2:Q')
        line = alt.Chart(plot).mark_line(strokeWidth=2.5).encode(
            x=alt.X('day:Q', title='Trading days from the call (0 = call day; shaded = reaction days 0 to +1)'),
            y=alt.Y('car:Q', title='vs. benchmark (cumulative)', axis=alt.Axis(format='%')),
            color=alt.Color('benchmark:N', title=None, scale=alt.Scale(domain=sorted(plot['benchmark'].unique(), key=lambda x: 'S&P' not in x),
                                                                       range=[ui.AZURE, ui.PUMPKIN])),
            tooltip=['benchmark', 'day', alt.Tooltip('date:T', format='%d %b %Y'), alt.Tooltip('car:Q', format='+.2%', title='Cumulative')])
        zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color=ui.LINE).encode(y='y:Q')
        st.altair_chart(alt.layer(band, zero, line).properties(height=300), width='stretch')
        st.caption('Read the line as a running score against the market: above zero = the stock did better than the ' + mkt_label + ' since the start of that side of '
                   'the window; below zero = worse. Left of the shaded band: the month before the call. Right of it: the month after.')

        # our view
        if not np.isfinite(day_car):
            ui.note('The call is too recent to judge the reaction: at least two trading days after the call are needed.')
        else:
            up = day_car >= 0
            size_txt = (f'not statistically different from normal day-to-day movement (t = {t_stat:+.2f})' if size < 1.96 else
                        f'statistically unusual at the 5% level (t = {t_stat:+.2f})' if size < 2.58 else
                        f'statistically unusual at the 1% level (t = {t_stat:+.2f})') if np.isfinite(size) else 'of unknown significance'
            level = 'small' if not np.isfinite(size) or size < 1.96 else 'large'
            match = (res['signal'] == 'Positive' and up) or (res['signal'] == 'Negative' and not up)
            clash = (res['signal'] == 'Positive' and not up) or (res['signal'] == 'Negative' and up)
            if level == 'small':
                verdict, colour, body = 'No statistically unusual reaction', ui.MUTED, (
                    f'Over the call day and the next day the stock {"beat" if up else "lagged"} the market by {abs(day_car):.1%}, which is {size_txt}. '
                    'We cannot separate the reaction to this call from ordinary daily movement.')
            elif match:
                verdict, colour, body = 'Unusual reaction, in the direction of the tone', ui.OLIVE if up else ui.ROSE, (
                    f'The stock {"beat" if up else "lagged"} the market by {abs(day_car):.1%} over days 0 to +1, a move that is {size_txt}, '
                    f'and in the same direction as the call\'s <b>{res["signal"].lower()}</b> tone. This is consistent with the call, and the results '
                    'released with it, carrying news for investors. It is an association, not proof that the language caused the move.')
            elif clash:
                verdict, colour, body = 'Unusual reaction, opposite to the tone', ui.PUMPKIN, (
                    f'The stock {"beat" if up else "lagged"} the market by {abs(day_car):.1%} over days 0 to +1 ({size_txt}), the <b>opposite</b> of what '
                    f'the call\'s {res["signal"].lower()} tone suggested. The tone does not explain this move; other information, such as the '
                    'reported numbers versus expectations, guidance, or other news on the same days, is the more likely driver.')
            else:
                verdict, colour, body = 'Unusual reaction after a neutral-toned call', ui.SKY, (
                    f'The stock {"beat" if up else "lagged"} the market by {abs(day_car):.1%} over days 0 to +1 ({size_txt}). The call\'s tone was '
                    'neutral, so the language does not explain the direction; the numbers, guidance or other news are the likelier drivers.')
            extra = []
            if np.isfinite(pre_car) and abs(pre_car) > 0.03:
                extra.append(f'The stock had already {"outperformed" if pre_car > 0 else "underperformed"} the market by {abs(pre_car):.1%} in the month before the call, '
                             'so part of the news may have been priced in beforehand.')
            if np.isfinite(week_car):
                if np.sign(week_car) == np.sign(day_car) and abs(week_car) > abs(day_car):
                    extra.append(f'The move <b>continued</b> through the first week ({week_car:+.1%} vs. the market).')
                elif np.sign(week_car) != np.sign(day_car):
                    extra.append(f'The move <b>reversed</b> within the first week ({week_car:+.1%} vs. the market).')
                else:
                    extra.append(f'Part of the move faded during the first week ({week_car:+.1%} vs. the market).')
            if np.isfinite(sec_day):
                extra.append(f'Against its sector ETF ({bench_etf}) it {"beat" if sec_day >= 0 else "lagged"} by {abs(sec_day):.1%}, '
                             + ('so the move was specific to this company, not the whole sector.' if np.sign(sec_day) == np.sign(day_car) and abs(sec_day) >= 0.5 * abs(day_car)
                                else 'so much of the move was shared with the rest of the sector.'))
            st.markdown(f"""<div class="qm-verdict" style="border-left-color:{colour}">
<div class="lbl">OUR VIEW</div><h4>{esc(verdict)}</h4><p>{body}</p>{''.join(f'<p>{x}</p>' for x in extra)}
<p class="small">Significance test: t = CAR(0,+1) / (σ × √2), where σ = {noise:.2%} is the standard deviation of the stock's daily abnormal return
in the estimation window ({est_window}, {est_n} trading days before the call). |t| ≥ 1.96 is unusual at the 5% level, |t| ≥ 2.58 at the 1% level,
assuming independent, normally distributed daily abnormal returns (Brown &amp; Warner 1985; MacKinlay 1997).</p></div>""", unsafe_allow_html=True)

        st.markdown("""<div class="qm-limits"><h4>What this view does not consider</h4>
<p>We only remove the move of the overall market (and, where shown, the sector). Stock prices change for many reasons that are <b>not</b> analysed here, including:</p>
<ul><li><b>Macroeconomic factors:</b> interest-rate decisions, inflation and jobs data, bond yields, currency moves, oil prices, geopolitical events.</li>
<li><b>Company and industry factors:</b> reported earnings versus analyst expectations, guidance changes, analyst upgrades and downgrades, deals, legal or regulatory news, management changes, competitors' results.</li>
<li><b>Market factors:</b> fund flows, options expiry, index changes, short covering, overall risk appetite.</li></ul>
<p>Our view is therefore an indication of <b>association</b>, not proof that the call caused the move. One call is an anecdote; the <b>Market reaction</b> page tests the pattern across all benchmark calls.</p>
<p class="disc">This is a student research project for MMA 823 (Smith School of Business, Queen's University). It is <b>not financial advice</b> and must not be used to make investment decisions.</p></div>""",
                    unsafe_allow_html=True)
        with st.expander('Method, data sources and reproducibility', icon=':material/fact_check:'):
            yh = lambda t: f'https://finance.yahoo.com/quote/{t}/history/'
            etf_line = f' and the sector ETF <a href="{yh(bench_etf)}" target="_blank">{bench_etf}</a>' if bench_etf else ''
            st.markdown(f"""<div class="qm-note" style="font-size:13.6px">
<b>Data.</b> Daily adjusted closing prices for <a href="{yh(pt)}" target="_blank">{esc(pt)}</a>, the {mkt_label} ETF
<a href="{yh(mkt)}" target="_blank">{mkt}</a>{etf_line}, from Yahoo Finance via the open-source
<a href="https://github.com/ranaroussi/yfinance" target="_blank">yfinance</a> library (not affiliated with Yahoo; Yahoo's data is intended for personal use).
Source used for this page: <b>{esc(source)}</b>. Click a ticker to check the prices on Yahoo Finance.<br><br>
<b>Method</b> (market-adjusted model, MacKinlay 1997):<br>
• Daily return R = P(t) / P(t−1) − 1, using adjusted closes. Day 0 = the call date, or the next trading day.<br>
• Abnormal return AR(t) = R<sub>stock</sub>(t) − R<sub>benchmark</sub>(t).<br>
• Cumulative abnormal return CAR(a, b) = sum of AR(t) from day a to day b. Windows: month before (−21 to −1), reaction (0 to +1), week (0 to +5), month (0 to +21).<br>
• Significance: t = CAR(0,+1) / (σ × √2), σ estimated on {est_window} ({est_n} days), which do not overlap the reaction window.<br>
• Day 0 to +1 is used so that calls held after the market close are captured.<br><br>
<b>How the text on this page is produced.</b> No AI or language model is used. All numbers are computed by the code in
<a href="https://github.com/ranadera/mma_earnings-call-sentiment/blob/main/views/analyze.py" target="_blank">views/analyze.py</a> and
<a href="https://github.com/ranadera/mma_earnings-call-sentiment/blob/main/market.py" target="_blank">market.py</a>; the sentences
in "Our view" are fixed templates chosen by explicit rules (the size of t and whether the direction matches the tone signal).</div>""",
                        unsafe_allow_html=True)
            dl = ev[['day', 'date', 'ret', 'bench_ret', 'abn_ret', 'car']].rename(columns={'ret': f'{pt}_return', 'bench_ret': f'{mkt}_return'})
            st.download_button('Download the daily returns used (CSV)', dl.to_csv(index=False), file_name=f'event_window_{ticker}_{call_date}.csv', mime='text/csv')
        st.caption(f'Source: {source}. Abnormal return = stock return minus benchmark return each day. References at the end of the page.')
        reaction = {'day': day_car, 'pre': pre_car, 'week': week_car, 'size': size}

ui.section('E · UNDER THE HOOD', 'What drove the score')
c1, c2, c3 = st.columns(3)
pos = Counter(w for ws in scored['pos_words'] for w in ws).most_common(10)
neg = Counter(w for ws in scored['neg_words'] for w in ws).most_common(10)


def word_bars(words, title, colour):
    if not words:
        st.caption('None found.')
        return
    d = pd.DataFrame(words, columns=['word', 'count'])
    ch = alt.Chart(d).mark_bar(cornerRadiusEnd=3, color=colour).encode(
        y=alt.Y('word:N', sort='-x', title=None, axis=alt.Axis(labelOverlap=False, labelLimit=150)),
        x=alt.X('count:Q', title='Times used'), tooltip=['word', 'count'])
    txt = ch.mark_text(align='left', dx=3, fontSize=11, color=ui.INK).encode(text='count:Q')
    st.altair_chart((ch + txt).properties(height=alt.Step(24), title=title), width='stretch')


with c1:
    word_bars(pos, 'Most frequent positive words', ui.OLIVE)
with c2:
    word_bars(neg, 'Most frequent negative words', ui.ROSE)
with c3:
    st.markdown('**Sector jargon set aside**')
    nt = sc.neutral_terms(lexicon, lex_sector)
    jargon = Counter()
    for t in scored['clean']:
        toks = t.lower().split()
        for i, w in enumerate(toks):
            w = w.strip('.,;:()"\'')
            if w in nt['words'] or (i > 0 and (toks[i - 1].strip('.,;:()"\''), w) in nt['pairs']):
                jargon[w if w in nt['words'] else toks[i - 1].strip('.,;:()"\'') + ' ' + w] += 1
    if jargon:
        st.dataframe(pd.DataFrame(jargon.most_common(10), columns=['term', 'count']), hide_index=True, width='stretch')
    else:
        st.caption('None found for this sector.')
    st.caption('These words are routine jargon in the sector and are ignored in the sector-adjusted tone.')

analysts = scored[(scored['part'] == 'qa_analyst') & (scored['n_words'] > 40)].copy()
if not analysts.empty:
    with st.expander('Toughest analyst questions'):
        analysts['tone'] = (analysts['lm_pos'] - analysts['lm_neg']) / analysts['n_words'] * 100
        for _, r in analysts.nsmallest(3, 'tone').iterrows():
            st.markdown(f"**{r['speaker']}** · tone {r['tone']:+.2f}")
            st.write(r['clean'][:600] + ('...' if len(r['clean']) > 600 else ''))

with st.expander('Download the scores'):
    out = pd.DataFrame([{'company': company, 'ticker': ticker, 'call_date': call_date, 'sector': detected or '',
                         'compared_with': sector or 'All benchmark calls',
                         **{k: (round(v, 4) if isinstance(v, (float, np.floating)) else v) for k, v in res.items()}}])
    st.dataframe(out.T.rename(columns={0: 'value'}).astype(str), width='stretch')
    st.download_button('Download as CSV', out.to_csv(index=False), file_name=f"sentiment_{ticker or 'transcript'}.csv", mime='text/csv')

# --- Optional bonus section (remove this block, prof_mehmet.py and features.py to delete it) ---
import features
if features.SHOW_PROF_MEHMET:
    import prof_mehmet
    prof_mehmet.render(res, peer_word, lex_sector, reaction)
# --- end of bonus section ---

ui.references()
ui.footer()
