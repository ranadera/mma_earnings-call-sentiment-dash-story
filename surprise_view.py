"""Beyond the numbers: does tone add anything to the earnings surprise?

Reads data/eps_surprise.csv and data/surprise_test.json (written by pipeline/eps_surprise.py).
Shown on the Market reaction page and as a story chapter when SHOW_SURPRISE_TEST is True in
features.py. To remove it, set the switch to False (or delete this file and its two calls).
"""
import json
import os

import altair as alt
import pandas as pd
import streamlit as st

import ui

DATA = os.path.join(os.path.dirname(__file__), 'data')
WINDOWS = {'car_day': 'First 2 days (call day and next day)', 'car_drift': 'After the call (days +2 to +21)'}
TONES = {'composite': 'Overall tone', 'tone_vs_usual': "Tone vs. the company's usual"}


@st.cache_data(ttl=3600, show_spinner=False)
def load():
    p, e, c = (os.path.join(DATA, f) for f in ('surprise_test.json', 'eps_surprise.csv', 'event_returns.csv'))
    if not (os.path.exists(p) and os.path.exists(e)):
        return None, None
    res = json.load(open(p))
    if res.get('status') != 'ok':
        return None, None
    eps = pd.read_csv(e)
    if os.path.exists(c):
        cars = pd.read_csv(c)
        eps = eps.merge(cars[cars['benchmark'] == 'SPY'][['call_id', 'car_day', 'car_drift']], on='call_id', how='left')
    return res, eps


def _best(res, window):
    """The tone measure that adds most beyond the surprise in this window, with its numbers."""
    rows = []
    for tone, label in TONES.items():
        m = res['models'].get(f'{window}|{tone}')
        if m:
            both = m['surprise_and_tone']
            rows.append({'tone': tone, 'label': label, 'n': both['n'], 'r2_s': m['surprise_only']['r2'], 'r2_st': both['r2'],
                         'coef': both['coef']['tone_z'], 'p': both['p']['tone_z'],
                         's_coef': both['coef']['surprise_z'], 's_p': both['p']['surprise_z']})
    return sorted(rows, key=lambda r: r['p'])[0] if rows else None


def _meta_pair(eps):
    m = eps[eps['call_id'].isin(['META_2024-02-01', 'META_2024-04-24'])].dropna(subset=['surprise_pct', 'car_day'])
    return m.sort_values('call_date') if len(m) == 2 else None


def link(label):
    """Link to the Beyond the Beat page (falls back to a plain link when the page is opened on its own)."""
    try:
        st.page_link('views/beyond_beat.py', label=label, icon=':material/arrow_forward:')
    except Exception:
        st.markdown(f'<a href="beyond-the-beat" target="_self" style="font-weight:700">→ {label}</a>', unsafe_allow_html=True)


def page_section(num):
    res, eps = load()
    if res is None:
        return
    n = res['calls_with_surprise']
    ui.section(f'{num} · BEYOND THE BEAT' if num else 'THE TEST', 'Do the words matter once you know the numbers?',
               'Before each call, analysts publish a consensus estimate of earnings per share (EPS). The <b>surprise</b> is how far '
               'the reported EPS came in above or below it. If confident tone only reflects a good quarter, tone should add nothing '
               'once we know the surprise. We test that with a regression of the stock\'s move (against the S&amp;P 500) on the '
               'surprise, then on the surprise plus tone.')
    rho = res['rho_composite_surprise']
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.kpi('Beat the estimate', f"{res['beats']} of {n}", f"Median surprise <b>{res['median_surprise_pct']:+.1f}%</b>. "
               'Big, well-covered companies usually beat.', color=ui.AZURE)
    with c2:
        ui.kpi('Tone vs. surprise', f"{rho['rho']:+.2f}", f"Rank correlation (p-value {rho['p']:.2f}). Near zero: tone is "
               '<b>not</b> just echoing the numbers.', color=ui.SKY)
    rows = []
    for w, wl in WINDOWS.items():
        b = _best(res, w)
        if b:
            rows += [{'window': wl, 'model': 'EPS surprise alone', 'r2': b['r2_s']},
                     {'window': wl, 'model': f"Surprise + {b['label'].lower()}", 'r2': b['r2_st']}]
    drift = _best(res, 'car_drift')
    with c3:
        if drift:
            ui.kpi('Tone after the call', f"{drift['coef']:+.1f}%", f"Extra move over days +2 to +21 per 1 standard deviation of "
                   f"{drift['label'].lower()}, holding the surprise fixed (p-value {drift['p']:.3f}).",
                   color=ui.OLIVE if drift['p'] < 0.05 and drift['coef'] > 0 else ui.PUMPKIN)
    if rows:
        df = pd.DataFrame(rows)
        cols = st.columns(len(WINDOWS))
        for col, (w, wl) in zip(cols, WINDOWS.items()):
            sub = df[df['window'] == wl]
            if sub.empty:
                continue
            base = alt.Chart(sub).encode(
                y=alt.Y('model:N', title=None, sort=None, axis=alt.Axis(labelLimit=260, labelFontSize=12)),
                x=alt.X('r2:Q', title='Share of the move explained (R²)', axis=alt.Axis(format='%'),
                        scale=alt.Scale(domain=[0, max(0.12, float(df['r2'].max()) * 1.25)])))
            bars = base.mark_bar(cornerRadiusEnd=4).encode(
                color=alt.Color('model:N', legend=None, scale=alt.Scale(range=[ui.SKY, ui.AZURE])))
            text = base.mark_text(align='left', dx=5, fontWeight='bold', color='#1B2333').encode(text=alt.Text('r2:Q', format='.1%'))
            col.altair_chart((bars + text).properties(height=110, title=wl), width='stretch')
    msg = []
    day = _best(res, 'car_day')
    if day:
        msg.append(f"<b>First 2 days:</b> the surprise explains only {day['r2_s']:.0%} of the move "
                   f"(p-value {day['s_p']:.2f}), and tone adds {'little' if day['p'] >= 0.05 else 'a significant amount'} "
                   f"(p-value {day['p']:.2f}). The first reaction is about something else, mostly the outlook.")
    if drift:
        if drift['p'] < 0.05:
            msg.append(f"<b>After the call:</b> {drift['label'].lower()} predicts the drift even holding the surprise fixed: "
                       f"{drift['r2_s']:.0%} of the move explained by the surprise alone, {drift['r2_st']:.0%} with tone. "
                       'The words carry information the numbers do not, consistent with Price et al. (2012).')
        else:
            msg.append('<b>After the call:</b> tone adds nothing significant beyond the surprise.')
    meta = _meta_pair(eps)
    if meta is not None:
        a, b = meta.iloc[0], meta.iloc[1]
        msg.append(f"<b>Meta shows why the first reaction is about the outlook:</b> it beat by {a['surprise_pct']:+.0f}% in "
                   f"February 2024 and {b['surprise_pct']:+.0f}% in April 2024, yet the stock went {a['car_day']:+.0%} and "
                   f"{b['car_day']:+.0%}. Same beat, opposite reactions: investors were pricing the guidance.")
    ui.note('<br><br>'.join(msg))
    with st.expander('Regression details'):
        det = []
        for key, m in res['models'].items():
            w, t = key.split('|')
            both = m['surprise_and_tone']
            det.append({'Move': WINDOWS[w], 'Tone measure': TONES[t], 'Calls': both['n'],
                        'R² surprise only': f"{m['surprise_only']['r2']:.1%}", 'R² with tone': f"{both['r2']:.1%}",
                        'Surprise effect (per 1 sd)': f"{both['coef']['surprise_z']:+.2f}% (p {both['p']['surprise_z']:.3f})",
                        'Tone effect (per 1 sd)': f"{both['coef']['tone_z']:+.2f}% (p {both['p']['tone_z']:.3f})"})
        st.dataframe(pd.DataFrame(det), hide_index=True, width='stretch')
        st.caption(f"Ordinary least squares with robust (HC1) standard errors. Surprise = (reported EPS − consensus estimate) / "
                   f"|estimate|, capped at ±{res['cap_pct']:.0f}%; surprise and tone standardised so effects are per 1 standard "
                   "deviation. Moves are against the S&P 500. EPS estimates and reported EPS from Yahoo Finance "
                   "(Bloomberg where added). Four regressions were run, so a strict threshold is p < 0.0125.")


def story_chapter(chapter, so_what):
    res, eps = load()
    if res is None:
        return
    n = res['calls_with_surprise']
    day, drift = _best(res, 'car_day'), _best(res, 'car_drift')
    if not day:
        return
    chapter('beat', 'CHAPTER 4 · PART 3 · BEYOND THE BEAT',
            f"Beyond the beat: {res['beats']} of {n} calls beat the earnings estimate, but the beat explained only "
            f"{day['r2_s']:.0%} of the two-day move",
            'A fair challenge: maybe a confident CEO just reflects a good quarter. So we added the <b>earnings surprise</b>: reported '
            'earnings per share against what analysts expected. Tone and the surprise turn out to be nearly unrelated '
            f"(correlation {res['rho_composite_surprise']['rho']:+.2f}), so tone is not just echoing the numbers.")
    meta = _meta_pair(eps)
    if meta is not None:
        a, b = meta.iloc[0], meta.iloc[1]
        c1, c2 = st.columns(2)
        with c1:
            ui.kpi('Meta, February 2024', f"{a['car_day']:+.0%}", f"Beat the estimate by <b>{a['surprise_pct']:+.0f}%</b>. "
                   'Stock against the market over two days.', color=ui.OLIVE)
        with c2:
            ui.kpi('Meta, April 2024', f"{b['car_day']:+.0%}", f"Beat the estimate by <b>{b['surprise_pct']:+.0f}%</b>. "
                   'Same beat, opposite reaction: the outlook drove it.', color=ui.ROSE)
    if drift and drift['p'] < 0.05:
        so_what(f"In the first two days, neither the beat nor the tone explains much: the market prices the outlook. After that, "
                f"<b>{drift['label'].lower()}</b> predicts how the stock drifts over the next month, even holding the surprise "
                f"fixed (p-value {drift['p']:.3f}). The words carry information the numbers do not.")
    else:
        so_what('In the first two days, neither the beat nor the tone explains much: the market prices the outlook, not last '
                'quarter\'s numbers.')
    link('See the full test: Beyond the Beat')


def headline():
    """One sentence for the top of the story page, or None."""
    res, eps = load()
    if res is None:
        return None
    drift = _best(res, 'car_drift')
    if drift and drift['p'] < 0.05 and drift['coef'] > 0:
        return (f"Beating the estimate explained little of the first reaction ({res['beats']} of {res['calls_with_surprise']} calls beat). "
                f"But in the month after the call, a company sounding more upbeat than its usual self predicted a better stock "
                f"move, even holding the earnings surprise fixed (p-value {drift['p']:.3f}). The words carry information the numbers do not.")
    return (f"Beating the estimate explained little of the first reaction ({res['beats']} of {res['calls_with_surprise']} calls beat), "
            'and tone added little beyond it.')


def scatter():
    """Each call: earnings surprise vs. the two-day move, Meta's two 2024 calls labelled."""
    res, eps = load()
    if res is None:
        return
    d = eps.dropna(subset=['surprise_pct', 'car_day']).copy()
    d['surprise'] = d['surprise_pct'].clip(-res['cap_pct'], res['cap_pct'])
    d['move'] = d['car_day'] * 100
    d['label'] = d['ticker'] + ' ' + pd.to_datetime(d['call_date']).dt.strftime('%b %Y')
    d['meta'] = d['call_id'].isin(['META_2024-02-01', 'META_2024-04-24'])
    base = alt.Chart(d).encode(
        x=alt.X('surprise:Q', title='Earnings surprise: reported EPS vs. the estimate (%, capped at ±50%)'),
        y=alt.Y('move:Q', title='Stock vs. the market, call day and next day (%)'),
        tooltip=[alt.Tooltip('label:N', title='Call'), alt.Tooltip('surprise_pct:Q', title='Surprise (%)', format='+.1f'),
                 alt.Tooltip('move:Q', title='2-day move (%)', format='+.1f')])
    dots = base.mark_circle(size=70, opacity=0.75).encode(
        color=alt.condition('datum.meta', alt.value(ui.ROSE), alt.value(ui.AZURE)))
    labels = base.transform_filter('datum.meta').mark_text(align='left', dx=8, fontWeight='bold', color=ui.ROSE).encode(text='label:N')
    zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='#9AA3B2', strokeDash=[4, 4]).encode(y='y:Q')
    st.altair_chart((zero + dots + labels).properties(height=360, title='Each dot is a call: a bigger beat did not mean a bigger jump'),
                    width='stretch')
