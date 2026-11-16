"""Story mode for one uploaded call: the same scores as the full analysis, told in plain language.

Every sentence is a fixed template filled in with numbers computed from the transcript and from Yahoo Finance prices.
No AI or language model writes or changes any of it. Quotes are sentences taken word for word from the uploaded file.
"""
import re
from collections import Counter

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import sentiment_core as sc
import ui
from ui import esc

CSS = f"""<style>
.cs-head {{background:{ui.SMITH_BLUE}; color:#fff; border-radius:14px; padding:24px 28px; margin:10px 0 6px; border-left:8px solid {ui.GOLD};}}
.cs-head .k {{font-size:.72rem; letter-spacing:.14em; font-weight:700; color:{ui.GOLD};}}
.cs-head .h {{font-size:1.65rem; font-weight:800; line-height:1.25; margin:6px 0 0;}}
.cs-ch {{margin:36px 0 8px;}}
.cs-ch .n {{font-size:.72rem; letter-spacing:.14em; font-weight:700; color:{ui.SMITH_BLUE}; background:#FFF3C4; border-radius:4px; padding:3px 9px;}}
.cs-ch h3 {{font-size:1.45rem; font-weight:800; color:{ui.SMITH_BLUE}; margin:10px 0 4px; line-height:1.25;}}
.cs-ch p {{font-size:1.02rem; color:#3D4656; line-height:1.6; margin:0; max-width:900px;}}
.cs-quotes {{display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:10px 0;}}
.cs-q {{background:#fff; border:1px solid #E3E7EE; border-left:5px solid var(--c); border-radius:10px; padding:14px 18px;}}
.cs-q .k {{font-size:.72rem; letter-spacing:.1em; font-weight:700; color:var(--c);}}
.cs-q blockquote {{margin:8px 0 6px; padding:0; border:0; font-size:1.02rem; line-height:1.55; color:#2B3445; font-style:italic;}}
.cs-q .who {{font-size:.85rem; color:#6B7486;}}
.cs-gauge {{position:relative; height:16px; border-radius:999px; margin:20px 0 8px;
  background:linear-gradient(90deg, {ui.ROSE} 0%, #E9C46A 50%, {ui.OLIVE} 100%); opacity:.9;}}
.cs-gauge .m {{position:absolute; top:-9px; width:6px; height:34px; background:{ui.SMITH_BLUE}; border:2px solid #fff; border-radius:3px; transform:translateX(-50%);}}
.cs-gl {{display:flex; justify-content:space-between; font-size:.82rem; color:#6B7486;}}
.cs-num {{display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; margin:10px 0;}}
.cs-num > div {{background:#fff; border:1px solid #E3E7EE; border-radius:10px; padding:14px 16px;}}
.cs-num .v {{font-size:1.7rem; font-weight:800; line-height:1;}}
.cs-num .l {{font-size:.86rem; color:#5B6475; margin-top:6px; line-height:1.4;}}
.cs-bottom {{counter-reset:b; display:grid; gap:10px; margin:12px 0;}}
.cs-bottom div {{background:#fff; border:1px solid #E3E7EE; border-radius:10px; padding:13px 18px 13px 58px; position:relative; line-height:1.55;}}
.cs-bottom div::before {{counter-increment:b; content:counter(b); position:absolute; left:16px; top:12px; width:28px; height:28px; border-radius:50%;
  background:{ui.GOLD}; color:{ui.SMITH_BLUE}; font-weight:800; display:flex; align-items:center; justify-content:center;}}
@media (max-width: 900px) {{ .cs-quotes, .cs-num {{grid-template-columns:1fr;}} }}
</style>"""


def _ch(num, title, body=''):
    st.session_state['_cs_n'] = st.session_state.get('_cs_n', 0) + 1
    num = f"{st.session_state['_cs_n']} · {num.split(' · ', 1)[-1]}"
    st.markdown(f'<div class="cs-ch"><span class="n">{esc(num)}</span><h3>{title}</h3><p>{body}</p></div>', unsafe_allow_html=True)


def _ok(x):
    return x is not None and isinstance(x, (int, float, np.floating)) and np.isfinite(x)


def _trim(sentence, max_words=45):
    words = sentence.split()
    return ' '.join(words[:max_words]) + (' …' if len(words) > max_words else '')


def _key_sentences(scored, lm, neutral, part_filter):
    """Most upbeat and most cautious sentence (net finance words) in the chosen turns."""
    rows = []
    for _, r in scored[part_filter(scored)].iterrows():
        for s in sc.split_sentences(r['clean']):
            if len(s.split()) < 8:
                continue
            c = sc.lm_counts(s, lm, neutral)
            negated = bool(set(re.findall(r"[a-z]+(?:'[a-z]+)?", s.lower())) & set(sc.NEGATORS))
            rows.append({'s': s, 'who': r['speaker'], 'net': c['lm_pos'] - c['lm_neg'], 'pos': c['lm_pos'], 'neg': c['lm_neg'], 'negated': negated})
    if not rows:
        return None, None
    d = pd.DataFrame(rows)
    up = d[d['pos'] > 0].sort_values(['net', 'pos'], ascending=False)
    down = d[(d['neg'] > 0) & ~d['negated']]  # 'no bottlenecks' is not a cautious remark.sort_values(['net', 'neg'], ascending=[True, False])
    return (up.iloc[0] if len(up) else None), (down.iloc[0] if len(down) else None)


def _percentile_words(p):
    return ('one of the most upbeat calls in our benchmark' if p >= .85 else 'more upbeat than most calls' if p >= .6 else
            'about as upbeat as a typical call' if p >= .4 else 'more cautious than most calls' if p >= .15 else
            'one of the most cautious calls in our benchmark')


def render(*, company, ticker, call_date, scored, res, peers, peer_word, lm, neutral, reaction):
    """reaction: dict from market.call_reaction (may contain 'error')."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state['_cs_n'] = 0
    pct = float((peers['composite'] < res['composite']).mean())
    signal = res['signal']
    mood = {'Positive': 'upbeat', 'Neutral': 'measured', 'Negative': 'cautious'}[signal]
    shift = res.get('tone_shift')
    held = _ok(shift) and shift >= 0
    has_qa = (scored['part'] != 'presentation').any()
    r = reaction or {}
    has_px = 'error' not in r and _ok(r.get('day'))

    # ---- one-sentence headline, built from the parts below
    head = f'{esc(company)} sounded <span style="color:{ui.GOLD}">{mood}</span>'
    if has_qa and _ok(shift):
        head += ((', kept that tone under questioning' if signal == 'Positive' else ', did not get gloomier under questioning' if signal == 'Negative'
                  else ', held steady under questioning') if held else ', got more careful once analysts started asking questions')
    if has_px:
        clash = (signal == 'Positive' and r['day'] < 0) or (signal == 'Negative' and r['day'] >= 0)
        head += (', yet' if clash else ', and') + (f' the stock {"beat" if r["day"] >= 0 else "lagged"} the market by '
                                                    f'{abs(r["day"]):.1%} over the next two days')
    headline = head
    st.markdown(f'<div class="cs-head"><div class="k">THE STORY OF THIS CALL IN ONE SENTENCE</div><div class="h">{headline}.</div></div>',
                unsafe_allow_html=True)

    # ---- 1. what happened
    words = int(scored['n_words'].sum())
    by_part = scored.groupby('part')['n_words'].sum()
    mgmt = scored[scored['role'] == 'management']
    top_speaker = mgmt.groupby('speaker')['n_words'].sum().sort_values(ascending=False)
    n_q = int((scored['part'] == 'qa_analyst').sum())
    n_analysts = scored.loc[scored['part'] == 'qa_analyst', 'speaker'].nunique()
    lead = (f'<b>{esc(top_speaker.index[0])}</b> did most of the talking for the company '
            f'({top_speaker.iloc[0] / max(words, 1):.0%} of all words). ') if len(top_speaker) and top_speaker.index[0] not in (None, 'Management', 'Full text') else ''
    _ch('1 · WHAT HAPPENED', 'What happened on this call',
        f'About <b>{words:,} words</b>, roughly <b>{words / 150:.0f} minutes</b> of talking. {lead}'
        + (f'{n_analysts} analyst{"s" if n_analysts != 1 else ""} asked <b>{n_q} question{"s" if n_q != 1 else ""}</b>.' if n_q else
           'We could not tell the analysts\' questions apart from management\'s answers in this file.'))
    parts = pd.DataFrame([{'part': n, 'share': by_part.get(k, 0) / max(words, 1)} for k, n in
                          [('presentation', 'Prepared remarks'), ('qa_management', "Management's answers"), ('qa_analyst', "Analysts' questions")]])
    parts = parts[parts['share'] > 0]
    colors = {'Prepared remarks': (ui.SMITH_BLUE, '#fff'), "Management's answers": (ui.AZURE, '#fff'), "Analysts' questions": (ui.GOLD, ui.SMITH_BLUE)}
    segs = ''.join(f'<div title="{esc(p)}: {v:.0%}" style="flex:{v:.4f};background:{colors[p][0]};color:{colors[p][1]};padding:10px 12px;'
                   f'font-weight:700;font-size:.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{v:.0%}</div>'
                   for p, v in zip(parts['part'], parts['share']))
    legend = ''.join(f'<span style="margin-right:18px"><span style="display:inline-block;width:11px;height:11px;border-radius:2px;'
                     f'background:{colors[p][0]};margin-right:6px"></span>{esc(p)}</span>' for p in parts['part'])
    st.markdown(f'<div style="font-weight:700;color:{ui.SMITH_BLUE};margin:12px 0 6px">How the call was split (share of words)</div>'
                f'<div style="display:flex;gap:2px;border-radius:8px;overflow:hidden">{segs}</div>'
                f'<div style="font-size:.86rem;color:#5B6475;margin-top:8px">{legend}</div>', unsafe_allow_html=True)

    # ---- 2. in their own words
    up, down = _key_sentences(scored, lm, neutral, lambda d: d['role'] == 'management')
    if up is not None or down is not None:
        _ch('2 · IN THEIR OWN WORDS', 'The most upbeat and most cautious moments',
            'Two sentences from management, picked by counting upbeat and downbeat finance words. Quoted word for word from the file you uploaded.')
        cards = ''
        for row, k, c in [(up, 'MOST UPBEAT', ui.OLIVE), (down, 'MOST CAUTIOUS', ui.ROSE)]:
            if row is not None:
                cards += (f'<div class="cs-q" style="--c:{c}"><div class="k">{k}</div><blockquote>“{esc(_trim(row["s"]))}”</blockquote>'
                          f'<div class="who">{esc(row["who"] or "Management")}</div></div>')
        st.markdown(f'<div class="cs-quotes">{cards}</div>', unsafe_allow_html=True)

    # ---- 3. overall mood
    _ch('3 · THE MOOD', f'Overall, this call was {_percentile_words(pct)}',
        (f'Compared with {esc(peer_word)}, it was less positive than every one of them. ' if pct == 0 else f'Compared with {esc(peer_word)}, it was more positive than every one of them. ' if pct == 1 else f'Compared with {esc(peer_word)}, this call was more positive than <b>{pct:.0%}</b> of them. ')
        + 
        'We count upbeat and downbeat finance words (such as <i>growth</i>, <i>strong</i> versus <i>decline</i>, <i>loss</i>) '
        'and compare the balance with other calls.')
    st.markdown(f'<div class="cs-gauge"><div class="m" style="left:{min(max(pct, .01), .99) * 100:.0f}%"></div></div>'
                '<div class="cs-gl"><span>More cautious than other calls</span><span>Typical</span><span>More upbeat than other calls</span></div>',
                unsafe_allow_html=True)

    # ---- 4. script vs Q&A
    if has_qa and _ok(shift):
        fell_share = float((peers['tone_shift'] < 0).mean()) if 'tone_shift' in peers else np.nan
        _ch('4 · UNDER PRESSURE', 'Management kept its confidence in the live Q&amp;A' if held else 'Confidence slipped once the script ended',
            f'The prepared remarks scored <b>{res["pres_tone"]:.2f}</b>; management\'s live answers scored <b>{res["qa_mgmt_tone"]:.2f}</b> '
            '(net upbeat words per 100). '
            + ('Holding up under questioning is a good sign: the confidence was not only in the script.' if held else
               'A drop is common, scripts are polished, but it shows where management was less sure.')
            + (f' For comparison, tone dropped in {fell_share:.0%} of {esc(peer_word)}.' if _ok(fell_share) else ''))

    # ---- 5. analysts
    an = scored[(scored['part'] == 'qa_analyst') & (scored['n_words'] > 20)]
    if len(an) and _ok(res.get('analyst_neg_rate')):
        a_avg = peers['analyst_neg_rate'].mean() if 'analyst_neg_rate' in peers else np.nan
        tough = _ok(a_avg) and res['analyst_neg_rate'] > a_avg
        worries = Counter(w for ws in an['neg_words'] for w in ws if not w.startswith('not ')).most_common(5)
        _ch('5 · THE ANALYSTS', 'Analysts pushed harder than usual' if tough else 'Analysts were relatively friendly',
            'Analysts ask the questions investors care about. Their wording shows what worried them.'
            + (f' Words that came up in their questions: <b>{esc(", ".join(w for w, _ in worries))}</b>.' if worries else ''))
        toughest = an.assign(rate=an['lm_neg'] / an['n_words']).sort_values('rate', ascending=False).iloc[0]
        if toughest['lm_neg'] > 0:
            sents = sc.split_sentences(toughest['clean'])
            best = max(sents, key=lambda s: sc.lm_counts(s, lm)['lm_neg']) if sents else toughest['clean']
            st.markdown(f'<div class="cs-quotes" style="grid-template-columns:1fr"><div class="cs-q" style="--c:{ui.PUMPKIN}">'
                        f'<div class="k">THE TOUGHEST QUESTION</div><blockquote>“{esc(_trim(best))}”</blockquote>'
                        f'<div class="who">{esc(toughest["speaker"] or "Analyst")}</div></div></div>', unsafe_allow_html=True)

    # ---- 6. the market
    _ch('6 · THE MARKET', 'How the stock reacted' if has_px else 'How the stock reacted: not available',
        '' if has_px else esc(r.get('error') or 'The call is too recent: at least two trading days after the call are needed.'))
    if has_px:
        lbl = r['market_label']
        nums = [('Month before the call', r['pre'], 'Was the stock already moving?'),
                ('Call day and next day', r['day'], 'The reaction to the call'),
                ('Month after the call', r['month'], 'Did it last?')]
        st.markdown('<div class="cs-num">' + ''.join(
            f'<div><div class="v" style="color:{ui.MUTED if not _ok(v) else ui.OLIVE if v >= 0 else ui.ROSE}">'
            f'{f"{v:+.1%}" if _ok(v) else "n/a"}</div><div class="l"><b>{l}</b><br>{n}</div></div>' for l, v, n in nums)
            + '</div>', unsafe_allow_html=True)
        st.caption(f'Each number is the stock\'s move minus the {lbl}\'s move over the same days, so a market-wide rally or sell-off is not '
                   f'credited to the call. Prices: {r["source"]}.')
        big = _ok(r['size']) and r['size'] >= 1.96
        match = (signal == 'Positive' and r['day'] >= 0) or (signal == 'Negative' and r['day'] < 0)
        if not big:
            verdict = ('The move was within the stock\'s normal day-to-day swings, so we cannot say the call itself moved the stock.')
        elif signal == 'Neutral':
            verdict = 'The move was unusually large, but the call\'s tone was neutral, so the tone does not explain it.'
        elif match:
            verdict = (f'The move was unusually large <b>and went the way the {mood} tone suggested</b>. The call and the market reaction agree, '
                       'though other news from the same day (such as the earnings numbers) may also have played a part.')
        else:
            verdict = (f'The move was unusually large <b>but went the opposite way</b> from what the {mood} tone suggested. Investors were '
                       'reacting to something other than the tone, such as the numbers or guidance.')
        ui.note(f'<b>Our read:</b> {verdict}')

    # ---- 7. bottom line
    _ch('7 · THE BOTTOM LINE', 'What to take away')
    takes = [f'<b>Tone:</b> management sounded {mood}; compared with {esc(peer_word)}, this call was {_percentile_words(pct)}.']
    if has_qa and _ok(shift):
        takes.append('<b>Under questioning:</b> ' + ('the confidence held up in the live Q&amp;A.' if held else
                                                     'the tone softened once analysts started asking questions; worth reading those answers closely.'))
    if has_px:
        takes.append(f'<b>Market:</b> the stock {"beat" if r["day"] >= 0 else "lagged"} the {r["market_label"]} by {abs(r["day"]):.1%} over two days'
                     + (', an unusually large move.' if _ok(r['size']) and r['size'] >= 1.96 else ', within its normal range.'))
    else:
        takes.append('<b>Market:</b> add the ticker and call date in the left panel to see how the stock reacted.')
    st.markdown('<div class="cs-bottom">' + ''.join(f'<div>{t}</div>' for t in takes) + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="qm-limits">Tone is one clue among many. Earnings versus expectations, guidance, interest rates and the wider market '
                'also move stocks and are not considered here. This is a student research project, <b>not financial advice</b>. '
                'Switch to <b>Full analysis</b> at the top of the page for every number, chart and the method.</div>', unsafe_allow_html=True)
