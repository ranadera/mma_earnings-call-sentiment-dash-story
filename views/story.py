"""The executive story: one page, read top to bottom, every headline computed from the data shipped with the app.

Nothing on this page is typed in by hand. When the pipeline adds transcripts, the numbers, the headlines and the
verdicts below update themselves; if the data cannot support a claim, the page says so instead of making it.
"""
import math

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import data_access as da
import features
import ui
from ui import esc, term

STAGE_NAMES = ['Prepared remarks', "Management's answers", "Analysts' questions"]

st.markdown(f"""<style>
.qs-chapters {{display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 4px;}}
.qs-chapters a {{font-size:.8rem; font-weight:600; color:{ui.SMITH_BLUE}; text-decoration:none; border:1px solid #D5DBE5;
  border-radius:999px; padding:5px 12px; background:#fff;}}
.qs-chapters a:hover {{border-color:{ui.GOLD}; background:#FFF8E1;}}
.qs-chapters a b {{color:#8A93A3; font-weight:700; margin-right:5px;}}
.qs-answer {{background:{ui.SMITH_BLUE}; color:#fff; border-radius:14px; padding:26px 30px; margin:18px 0 8px; border-left:8px solid {ui.GOLD};}}
.qs-answer .k {{font-size:.72rem; letter-spacing:.14em; font-weight:700; color:{ui.GOLD};}}
.qs-answer .a {{font-size:2.1rem; font-weight:800; line-height:1.15; margin:6px 0 8px;}}
.qs-answer p {{font-size:1.05rem; line-height:1.55; margin:0; color:#E4E9F2; max-width:880px;}}
.qs-ch {{margin:54px 0 10px; scroll-margin-top:80px;}}
.qs-ch .n {{font-size:.75rem; letter-spacing:.16em; font-weight:700; color:{ui.GOLD}; background:{ui.SMITH_BLUE};
  border-radius:4px; padding:3px 9px;}}
.qs-ch h2 {{font-size:1.85rem; font-weight:800; color:{ui.SMITH_BLUE}; margin:12px 0 6px; line-height:1.2; max-width:980px;}}
.qs-ch p {{font-size:1.05rem; color:#3D4656; line-height:1.6; margin:0; max-width:900px;}}
.qs-big {{display:grid; grid-template-columns:repeat(4, 1fr); gap:14px; margin:14px 0;}}
.qs-big > div {{background:#fff; border:1px solid #E3E7EE; border-radius:12px; padding:18px 20px;}}
.qs-big .v {{font-size:2.3rem; font-weight:800; color:{ui.SMITH_BLUE}; line-height:1;}}
.qs-big .l {{font-size:.9rem; color:#5B6475; margin-top:8px; line-height:1.4;}}
.qs-sowhat {{border-left:4px solid {ui.GOLD}; background:#FFFBEF; padding:12px 18px; border-radius:0 10px 10px 0; margin:12px 0 0;
  font-size:1rem; color:#2B3445; line-height:1.55;}}
.qs-sowhat b:first-child {{color:{ui.SMITH_BLUE}; letter-spacing:.06em; font-size:.78rem; display:block; margin-bottom:2px;}}
.qs-pair {{display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:12px 0;}}
.qs-case {{background:#fff; border:1px solid #E3E7EE; border-radius:12px; padding:16px 20px; border-top:5px solid var(--c);}}
.qs-case .k {{font-size:.72rem; letter-spacing:.12em; font-weight:700; color:var(--c);}}
.qs-case h4 {{margin:6px 0 6px; color:{ui.SMITH_BLUE}; font-size:1.15rem;}}
.qs-case p {{margin:0; color:#3D4656; line-height:1.5;}}
.qs-take {{counter-reset:t; display:grid; gap:12px; margin:14px 0;}}
.qs-take div {{background:#fff; border:1px solid #E3E7EE; border-radius:12px; padding:16px 20px 16px 64px; position:relative;
  font-size:1.02rem; line-height:1.55; color:#2B3445;}}
.qs-take div::before {{counter-increment:t; content:counter(t); position:absolute; left:18px; top:14px; width:32px; height:32px;
  border-radius:50%; background:{ui.GOLD}; color:{ui.SMITH_BLUE}; font-weight:800; display:flex; align-items:center; justify-content:center;}}
.qs-verdict {{display:inline-block; font-weight:800; font-size:.85rem; letter-spacing:.06em; border-radius:6px; padding:4px 10px;
  color:#fff; background:var(--c); margin-right:8px;}}
@media (max-width: 900px) {{ .qs-big {{grid-template-columns:1fr 1fr;}} .qs-pair {{grid-template-columns:1fr;}} }}
</style>""", unsafe_allow_html=True)


def chapter(anchor, num, title, body_html=''):
    st.markdown(f'<div class="qs-ch" id="{anchor}"><span class="n">{esc(num)}</span><h2>{title}</h2><p>{body_html}</p></div>',
                unsafe_allow_html=True)


def so_what(body_html):
    st.markdown(f'<div class="qs-sowhat"><b>SO WHAT</b>{body_html}</div>', unsafe_allow_html=True)


def pct(x, signed=True):
    return f'{x:+.1%}' if signed else f'{abs(x):.1%}'


def at_least_by_luck(k, n):
    """Chance that a fair coin is right at least k times out of n (one-sided binomial)."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


# ---------------------------------------------------------------- data
bench = da.benchmark()
ev = da.event_returns()
data = bench.merge(ev, on='call_id', how='inner') if ev is not None else bench.iloc[0:0]
n_calls, n_cos = len(bench), bench['ticker'].nunique()
sectors = bench['sector'].value_counts()
first, last = bench['call_date'].min(), bench['call_date'].max()

directional = data[data['signal'] != 'Neutral'].dropna(subset=['car_day']).copy()
directional['expected'] = np.where(directional['signal'] == 'Positive', 1, -1)
directional['matched'] = np.sign(directional['car_day']) == directional['expected']
k, n = int(directional['matched'].sum()), len(directional)
hit = k / n if n else float('nan')
luck = at_least_by_luck(k, n) if n else float('nan')

# ---------------------------------------------------------------- the question and the short answer
ui.team()
st.markdown('<p class="qm-kicker" style="margin-top:18px">THE QUESTION OUR CLIENT ASKED</p>', unsafe_allow_html=True)
st.markdown(f'<h1 style="color:{ui.SMITH_BLUE};font-size:2.6rem;font-weight:800;line-height:1.12;margin:0 0 6px;max-width:1000px">'
            'When executives sound confident on an earnings call, does the stock follow?</h1>', unsafe_allow_html=True)
st.markdown('<p style="font-size:1.1rem;color:#3D4656;max-width:900px;line-height:1.6">Every quarter, management reads a script and then takes '
            'live questions from analysts. We measured <i>how</i> they sound, not just what they report, and checked what the stock did next.</p>',
            unsafe_allow_html=True)

if n < 10:
    answer, answer_body = 'Too early to say.', (f'Only {n} calls so far had a clearly positive or negative tone and price data. '
                                                'We need more calls before drawing any conclusion.')
elif hit > 0.5 and luck < 0.05:
    answer, answer_body = 'Yes, more often than chance.', (f'Tone pointed the right way in <b>{k} of {n}</b> calls ({hit:.0%}). A coin flip '
                                                           f'would do at least that well only {luck:.0%} of the time.')
elif hit > 0.5:
    answer, answer_body = 'Sometimes. It is a clue, not a crystal ball.', (
        f'The stock moved the way the tone suggested in <b>{k} of {n}</b> calls ({hit:.0%}) over the next two days. '
        f'That is better than a coin flip, but a coin would do at least that well about <b>{luck:.0%}</b> of the time, '
        'so with this many calls we cannot rule out luck.')
else:
    answer, answer_body = 'Not so far.', (f'The stock moved the way the tone suggested in only {k} of {n} calls ({hit:.0%}), '
                                          'no better than a coin flip.')
st.markdown(f'<div class="qs-answer"><div class="k">THE SHORT ANSWER</div><div class="a">{esc(answer)}</div><p>{answer_body}</p></div>',
            unsafe_allow_html=True)

st.markdown('<div class="qs-chapters">' + ''.join(f'<a href="#{a}" target="_self"><b>{i}</b>{t}</a>' for i, (a, t) in enumerate([
    ('listened', 'What we listened to'), ('script', 'Script vs. live Q&amp;A'), ('language', 'Banks vs. tech'),
    ('market', 'Did the market listen?'), ('trade', 'Can you trade it?'), ('means', 'What it means'), ('next', 'Try it yourself')], 1))
    + '</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 1. what we listened to
chapter('listened', 'CHAPTER 1', f'We listened to {n_calls} earnings calls from {n_cos} companies',
        f'Transcripts from Bloomberg and LSEG, {first:%B %Y} to {last:%B %Y}. Each call was split into the scripted remarks, '
        "management's live answers and the analysts' questions, then scored word by word with a finance dictionary.")
st.markdown('<div class="qs-big">'
            f'<div><div class="v">{n_calls}</div><div class="l">earnings calls read and scored</div></div>'
            f'<div><div class="v">{n_cos}</div><div class="l">companies</div></div>'
            f'<div><div class="v">{len(sectors)}</div><div class="l">sectors: {esc(", ".join(f"{v} {s.lower()}" for s, v in sectors.items()))}</div></div>'
            f'<div><div class="v">{len(data)}</div><div class="l">calls matched to daily stock prices</div></div>'
            '</div>', unsafe_allow_html=True)

timeline = (bench.assign(month=bench['call_date'].dt.to_period('M').dt.to_timestamp())
            .groupby(['sector', 'month']).agg(calls=('call_id', 'size'), names=('name', lambda x: ', '.join(sorted(set(x))))).reset_index())
tbase = alt.Chart(timeline).encode(
    x=alt.X('month:T', title=None, axis=alt.Axis(format='%b %Y', grid=False)),
    y=alt.Y('sector:N', title=None, axis=alt.Axis(labelFontSize=13, labelFontWeight='bold')),
    tooltip=[alt.Tooltip('month:T', title='Month', format='%B %Y'), 'sector', alt.Tooltip('calls:Q', title='Calls'),
             alt.Tooltip('names:N', title='Companies')])
tl = (tbase.mark_circle(opacity=.9, stroke='#fff', strokeWidth=2).encode(
          size=alt.Size('calls:Q', scale=alt.Scale(range=[180, 1100]), legend=None),
          color=alt.Color('sector:N', legend=None, scale=alt.Scale(domain=['Bank', 'Tech'] + sorted(set(sectors.index) - {'Bank', 'Tech'}),
                                                                    range=ui.SECTOR_PALETTE)))
      + tbase.mark_text(color='#fff', fontWeight='bold', fontSize=11).encode(text='calls:Q'))
st.altair_chart(tl.properties(height=70 + 50 * len(sectors), title='Calls per month (number in each circle)'), width='stretch')

# ---------------------------------------------------------------- 2. script vs. Q&A
fell = int((bench['tone_shift'] < 0).sum())
stages = (bench.groupby('sector')[['pres_tone', 'qa_mgmt_tone', 'analyst_tone']].mean()
          .set_axis(STAGE_NAMES, axis=1).reset_index().melt('sector', var_name='stage', value_name='tone'))
majority = fell > n_calls / 2
chapter('script', 'CHAPTER 2',
        f'Confidence fades once the script ends: tone dropped in the Q&amp;A in {fell} of {n_calls} calls' if majority
        else f'Management held its tone into the Q&amp;A in {n_calls - fell} of {n_calls} calls',
        'Prepared remarks are written and rehearsed. The live Q&amp;A is where analysts push and management has to improvise. '
        f'The line shows the average {term("Tone", "tone")} at each stage of the call: net upbeat finance words per 100 words.')
line = alt.Chart(stages).encode(
    x=alt.X('stage:N', sort=STAGE_NAMES, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=13, labelLimit=220)),
    y=alt.Y('tone:Q', title='Tone (net upbeat words per 100)', scale=alt.Scale(zero=True)),
    color=alt.Color('sector:N', scale=alt.Scale(range=ui.SECTOR_PALETTE), legend=alt.Legend(orient='top', title=None)),
    tooltip=['sector', 'stage', alt.Tooltip('tone:Q', format='.2f')])
labels = line.transform_filter(alt.datum.stage == STAGE_NAMES[0]).mark_text(align='right', dx=-12, fontWeight='bold', fontSize=13).encode(
    text=alt.Text('tone:Q', format='.2f'))
labels_end = line.transform_filter(alt.datum.stage == STAGE_NAMES[-1]).mark_text(align='left', dx=12, fontWeight='bold', fontSize=13).encode(
    text=alt.Text('tone:Q', format='.2f'))
st.altair_chart((line.mark_line(strokeWidth=3) + line.mark_point(size=110, filled=True, stroke='#fff', strokeWidth=2) + labels + labels_end)
                .properties(height=320), width='stretch')
so_what('Read the Q&amp;A, not just the press release. A call that stays upbeat under questioning is a stronger sign than polished '
        'prepared remarks.' if majority else 'Management mostly kept its tone under questioning, so the script was a fair guide in this sample.')

# ---------------------------------------------------------------- 3. banks vs. tech language
if {'Bank', 'Tech'} <= set(sectors[sectors >= 3].index):
    t, b = bench[bench['sector'] == 'Tech'], bench[bench['sector'] == 'Bank']
    lm_gap = 1 - b['lm_tone'].mean() / t['lm_tone'].mean()
    va_gap = 1 - b['vader'].mean() / t['vader'].mean()
    vocab = lm_gap > 0.25 and abs(va_gap) < lm_gap / 2
    chapter('language', 'CHAPTER 3',
            'Banks sound gloomier on paper, but it is mostly their vocabulary' if vocab else
            ('Banks really do sound more cautious than tech' if lm_gap > 0 else 'Banks sound as upbeat as tech'),
            'Bank calls are full of words like <i>loss</i>, <i>risk</i>, <i>default</i> and <i>provision</i>. For a bank these are routine; '
            'a finance dictionary still counts them as negative. So we checked with a general-language tool too.')
    comp = pd.DataFrame([
        {'tool': 'Finance dictionary (Loughran-McDonald)', 'sector': 'Tech', 'v': t['lm_tone'].mean()},
        {'tool': 'Finance dictionary (Loughran-McDonald)', 'sector': 'Bank', 'v': b['lm_tone'].mean()},
        {'tool': 'General-language tool (VADER)', 'sector': 'Tech', 'v': t['vader'].mean()},
        {'tool': 'General-language tool (VADER)', 'sector': 'Bank', 'v': b['vader'].mean()}])
    c1, c2 = st.columns(2)
    for col, tool, gap in [(c1, comp['tool'][0], lm_gap), (c2, comp['tool'][2], va_gap)]:
        d = comp[comp['tool'] == tool]
        bars = alt.Chart(d).encode(y=alt.Y('sector:N', title=None, sort=['Tech', 'Bank'], axis=alt.Axis(labelFontSize=13, labelFontWeight='bold')),
                                   x=alt.X('v:Q', title='Average score', axis=alt.Axis(grid=False, labels=False, ticks=False)),
                                   color=alt.Color('sector:N', legend=None, scale=alt.Scale(domain=['Bank', 'Tech'], range=ui.SECTOR_PALETTE[:2])))
        with col:
            st.markdown(f'**{tool}**  \nBanks score **{abs(gap):.0%} {"lower" if gap >= 0 else "higher"}** than tech')
            st.altair_chart((bars.mark_bar(size=34, cornerRadiusEnd=4) + bars.mark_text(align='left', dx=6, fontWeight='bold', fontSize=14)
                             .encode(text=alt.Text('v:Q', format='.2f'))).properties(height=130), width='stretch')
    so_what('Compare banks with banks. Judged against tech, almost every bank call looks negative. That is why the app scores each call '
            'against its own sector and sets routine sector jargon aside.' if vocab else
            'Sector matters: compare each call with its own peers, not with the whole market.')
else:
    chapter('language', 'CHAPTER 3', 'Every sector has its own vocabulary',
            'We compare each call with calls from its own sector. This chapter fills in once there are at least three bank and three tech calls.')

# ---------------------------------------------------------------- 4. did the market listen?
chapter('market', 'CHAPTER 4',
        f'Did the market listen? The stock followed the tone in {k} of {n} calls' if n else 'Did the market listen?',
        'Each dot is a call. Left to right: how positive management sounded compared with the other calls. Bottom to top: how the stock did '
        f'over the call day and the next, <b>after taking out the market\'s own move</b> (S&amp;P 500). Dots in the shaded corners went the way '
        'the tone suggested. Grey dots had a neutral tone.')
if len(data):
    pts = data.assign(move=data['car_day'],
                      outcome=np.select([data['signal'] == 'Neutral',
                                         np.sign(data['car_day']) == np.where(data['signal'] == 'Positive', 1, -1)],
                                        ['Neutral tone', 'Went the way the tone suggested'], 'Went the other way'))
    lim_y = max(abs(pts['move']).max() * 1.1, .05)
    lim_x = max(abs(pts['composite']).max() * 1.1, 1)
    quad = pd.DataFrame([{'x1': 0, 'x2': lim_x, 'y1': 0, 'y2': lim_y}, {'x1': -lim_x, 'x2': 0, 'y1': -lim_y, 'y2': 0}])
    shade = alt.Chart(quad).mark_rect(color=ui.OLIVE, opacity=.07).encode(x='x1:Q', x2='x2', y='y1:Q', y2='y2')
    corner = pd.DataFrame([{'x': lim_x * .97, 'y': lim_y * .93, 't': 'Upbeat call, stock beat the market', 'a': 'right'},
                           {'x': -lim_x * .97, 'y': -lim_y * .93, 't': 'Cautious call, stock lagged the market', 'a': 'left'}])
    ctext = (alt.Chart(corner.iloc[[0]]).mark_text(fontSize=12, fontWeight='bold', color=ui.OLIVE, align='right').encode(x='x:Q', y='y:Q', text='t:N')
             + alt.Chart(corner.iloc[[1]]).mark_text(fontSize=12, fontWeight='bold', color=ui.OLIVE, align='left').encode(x='x:Q', y='y:Q', text='t:N'))
    rules = (alt.Chart(pd.DataFrame({'v': [0]})).mark_rule(color='#9AA5B8').encode(y='v:Q')
             + alt.Chart(pd.DataFrame({'v': [0]})).mark_rule(color='#9AA5B8').encode(x='v:Q'))
    dom = ['Went the way the tone suggested', 'Went the other way', 'Neutral tone']
    dots = alt.Chart(pts).mark_circle(size=170, opacity=.95, stroke='#fff', strokeWidth=2).encode(
        x=alt.X('composite:Q', title='← More cautious than other calls        Tone        More upbeat than other calls →',
                scale=alt.Scale(domain=[-lim_x, lim_x]), axis=alt.Axis(labels=False, ticks=False, grid=False)),
        y=alt.Y('move:Q', title='Stock vs. market, call day and next day', axis=alt.Axis(format='+.0%', grid=False),
                scale=alt.Scale(domain=[-lim_y, lim_y])),
        color=alt.Color('outcome:N', scale=alt.Scale(domain=dom, range=[ui.OLIVE, ui.ROSE, '#A3ABB9']),
                        legend=alt.Legend(orient='top', title=None, labelLimit=320)),
        tooltip=[alt.Tooltip('label:N', title='Call'), alt.Tooltip('signal:N', title='Tone'),
                 alt.Tooltip('move:Q', title='Stock vs. market (2 days)', format='+.1%'), alt.Tooltip('outcome:N', title='Result')])
    st.altair_chart((shade + rules + ctext + dots).properties(height=440), width='stretch')

    if n:
        hits, misses = directional[directional['matched']], directional[~directional['matched']]
        cases = []
        if len(hits):
            h = hits.loc[hits['car_day'].abs().idxmax()]
            cases.append((ui.OLIVE, 'WHEN IT WORKED', h,
                          f'Management sounded <b>{h["signal"].lower()}</b>, and the stock {"beat" if h["car_day"] > 0 else "lagged"} '
                          f'the market by <b>{pct(h["car_day"], False)}</b> over the next two days.'))
        if len(misses):
            m = misses.loc[misses['car_day'].abs().idxmax()]
            cases.append((ui.ROSE, 'WHEN IT DIDN\'T', m,
                          f'Management sounded <b>{m["signal"].lower()}</b>, yet the stock {"beat" if m["car_day"] > 0 else "lagged"} '
                          f'the market by <b>{pct(m["car_day"], False)}</b>. Investors were reacting to something other than the tone.'))
        st.markdown('<div class="qs-pair">' + ''.join(
            f'<div class="qs-case" style="--c:{c}"><div class="k">{k_}</div><h4>{esc(r["label"])}</h4><p>{body}</p></div>'
            for c, k_, r, body in cases) + '</div>', unsafe_allow_html=True)
        so_what(f'Tone is one input among many. In this sample it called the direction {hit:.0%} of the time. Useful as a flag to look closer, '
                'not as a reason to trade on its own.')
else:
    ui.note('Stock prices have not been loaded yet, so this chapter is waiting for the pipeline to run.')

# ---------------------------------------------------------------- 4b. first reaction vs. readjustment (optional add-on)
if features.SHOW_GAP_STUDY:
    import gap_view
    gap_view.story_chapter(chapter, so_what)

# ---------------------------------------------------------------- 5. can you trade it?
mr = da.model_results() or {}
trained = mr.get('status') == 'ok' and any(t.get('status') == 'ok' for t in mr.get('targets', {}).values())
pos, neg = data[data['signal'] == 'Positive']['car_drift'].dropna(), data[data['signal'] == 'Negative']['car_drift'].dropna()
ls = pos.mean() - neg.mean() if len(pos) and len(neg) else float('nan')
model_lift = (max(t['accuracy'] - t['baseline_accuracy'] for t in mr['targets'].values() if t.get('status') == 'ok')
              if trained else float('nan'))
# "early signs" only when BOTH the simple long-short and the out-of-sample model beat their baselines
edge = trained and ls > 0 and model_lift > 0
chapter('trade', 'CHAPTER 5',
        ('Can you trade it? There are early signs' if edge else 'Can you trade it? Not on tone alone' if trained else 'Can you trade it? Not yet'),
        'The real test for an investor: if you only act <b>after</b> the call is over, is there anything left to earn? We bought the upbeat calls '
        'and sold the cautious ones from the second day after the call to about a month later (days +2 to +21).')
c1, c2 = st.columns(2)
with c1:
    if not math.isnan(ls):
        ui.kpi('Upbeat minus cautious calls, days +2 to +21', pct(ls),
               f'Average over {len(pos)} upbeat and {len(neg)} cautious calls, before trading costs. '
               + ('Upbeat calls kept doing better after the call.' if ls > 0 else 'Cautious calls actually did better afterwards.'),
               color=ui.OLIVE if ls > 0 else ui.ROSE)
with c2:
    if trained:
        best = max((t for t in mr['targets'].values() if t.get('status') == 'ok'), key=lambda t: t['accuracy'] - t['baseline_accuracy'])
        lift = best['accuracy'] - best['baseline_accuracy']
        ui.kpi(f'Prediction model, tested on {mr["test_year"]}', f'{best["accuracy"]:.0%} right',
               f'vs. <b>{best["baseline_accuracy"]:.0%}</b> by always guessing the most common outcome '
               f'({"better" if lift > 0 else "no better"}). Trained on {", ".join(map(str, mr["train_years"]))}.',
               color=ui.OLIVE if lift > 0 else ui.ROSE)
    else:
        ui.kpi('Prediction model', 'Waiting for data',
               'A fair test needs one year of calls to learn from and a later year to test on. It trains itself once the '
               '2023–2024 transcripts are loaded.', color=ui.PUMPKIN)
so_what('By the time an investor can act, most of the reaction has already happened. Any edge from tone alone is small and not yet '
        'proven, so treat it as research, not a strategy.' if not edge else
        'There is a hint of an edge after the call, but it needs more years of data and trading costs before anyone should rely on it.')

# ---------------------------------------------------------------- 6. what it means
chapter('means', 'CHAPTER 6', 'What this means for an investor')
takes = [
    f'<b>Listen to the live Q&amp;A.</b> In {fell} of {n_calls} calls, management sounded less positive once analysts started asking '
    'questions. The unscripted part of the call tells you more.' if majority else
    f'<b>The script held up.</b> Management kept its tone into the Q&amp;A in {n_calls - fell} of {n_calls} calls.',
    '<b>Compare like with like.</b> A bank call will always sound more negative than a tech call because of its vocabulary. '
    'Judge each call against its own sector.',
    (f'<b>Tone is a clue, not a crystal ball.</b> The stock followed the tone in {k} of {n} calls, but other news, the numbers themselves '
     'and the wider market often matter more.' if n else '<b>Tone is a clue, not a crystal ball.</b> We still need price data to test it.')]
st.markdown('<div class="qs-take">' + ''.join(f'<div>{t}</div>' for t in takes) + '</div>', unsafe_allow_html=True)
st.markdown(f"""<div class="qm-limits"><b>What we are not claiming.</b> We measure words, not intent, and we compare each stock with the market
only. Earnings surprises, guidance, interest rates, sector news and the wider economy also move stocks and are not modelled here.
With {n_calls} calls the results are a first look, not proof. This is a student research project, <b>not financial advice</b>.</div>""",
            unsafe_allow_html=True)

# ---------------------------------------------------------------- 7. try it yourself / go deeper
chapter('next', 'CHAPTER 7', 'Try it yourself, or go deeper',
        'Upload any earnings call transcript and the app tells its story in seconds. Every number on this page can be checked in the detailed views.')
ui.tiles([
    ('analyze', 'upload_file', 'Analyze a call', 'Upload a transcript: tone, top 3 takeaways and the price reaction.'
     + (" Bonus: Prof. Mehmet's take." if features.SHOW_PROF_MEHMET else '')),
    ('explorer', 'leaderboard', 'Benchmark explorer', 'Every call ranked and compared with its peers.'),
    ('market_reaction', 'show_chart', 'Market reaction', 'The full event study, correlations and the model.'),
    ('stocks', 'description', 'Stock reports', 'One-page profile of each stock.'),
    ('method', 'menu_book', 'Method & decisions', 'How it is built, our choices and limits.'),
])
if features.V1_APP_URL:
    st.markdown(f'<p style="margin-top:10px">Prefer the full analyst view? <a href="{esc(features.V1_APP_URL)}" target="_blank">'
                'Open the classic dashboard (version 1)</a>.</p>', unsafe_allow_html=True)

with st.expander('Where every number on this page comes from'):
    st.markdown(f"""
- **Calls and tone:** `data/call_sentiment.csv`, made by the pipeline from the transcripts, scored with the Loughran-McDonald
  finance dictionary (tone = net positive words per 100) plus VADER and TextBlob. No AI model writes or changes these numbers.
- **Stock vs. market:** `data/event_returns.csv`, from Yahoo Finance daily closes; each day's stock return minus the S&P 500 ETF (SPY) return,
  added up over the window shown.
- **"Followed the tone":** a positive call where the stock beat the market over days 0 to +1, or a negative call where it lagged. Neutral calls are left out.
- **"A coin would do that well":** the chance of at least {k} heads in {n} fair coin flips (one-sided binomial test).
- **Model:** `data/model_results.json`, a logistic regression trained on earlier years and tested on a later year.
- Every headline on this page is computed when the page loads. When new transcripts are added, the story updates itself.
""")
ui.references()
ui.footer()
