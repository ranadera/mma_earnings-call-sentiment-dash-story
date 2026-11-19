"""Optional, light-hearted bonus section: "Prof. Mehmet's take" on the Analyze page.

A student-written, imagined take inspired by themes from the MMA 823 lectures.
To switch it off, set SHOW_PROF_MEHMET = False in features.py.
To remove it completely, delete this file, features.py and the marked block at the end of views/analyze.py.
"""
import numpy as np

import features
import streamlit as st

import ui
from ui import esc

CSS = """<style>
.pm-head { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin:34px 0 4px; }
.pm-head .k { color:#5B6475; font-weight:900; font-size:11.5px; letter-spacing:.12em; }
.pm-sub { display:inline-block; background:#B90E31; color:#fff; font-weight:900; font-size:10.5px; letter-spacing:.12em;
  padding:3px 8px; border-radius:3px; }
.pm-card { background:#002452; border-radius:10px; padding:18px 20px; border-bottom:4px solid #FABD0F; color:#E8EDF6; }
.pm-top { display:flex; align-items:center; gap:14px; margin-bottom:12px; }
.pm-av { width:52px; height:52px; border-radius:50%; background:#FABD0F; color:#002452; font-weight:900; font-size:18px;
  display:flex; align-items:center; justify-content:center; flex:none; }
.pm-top h4 { margin:0; color:#fff; font-size:19px; font-weight:900; padding:0; }
.pm-top .s { color:#AFC0DA; font-size:12.5px; }
.pm-verdict { background:rgba(255,255,255,.07); border-left:4px solid #FABD0F; border-radius:0 6px 6px 0; padding:10px 14px;
  font-size:16px; line-height:1.5; color:#fff; margin-bottom:12px; }
.pm-card ul { margin:0 0 10px 18px; padding:0; }
.pm-card li { font-size:14.3px; line-height:1.55; margin-bottom:6px; color:#E8EDF6; }
.pm-card b { color:#FABD0F; }
.pm-meter { margin:8px 0 12px; }
.pm-meter .lbl { font-size:11.5px; font-weight:900; letter-spacing:.1em; color:#AFC0DA; margin-bottom:4px; }
.pm-bar { position:relative; height:12px; border-radius:6px; background:linear-gradient(90deg,#3B7CC4 0%,#FABD0F 60%,#B90E31 100%); }
.pm-pin { position:absolute; top:-5px; width:4px; height:22px; background:#fff; border-radius:2px; box-shadow:0 0 0 2px #002452; }
.pm-scale { display:flex; justify-content:space-between; font-size:11.5px; color:#AFC0DA; margin-top:4px; }
.pm-hw { background:rgba(250,189,15,.12); border-radius:6px; padding:9px 12px; font-size:13.8px; color:#fff; }
.pm-disc { color:#5B6475; font-size:12px; margin-top:8px; line-height:1.45; }
</style>"""

def _benchmark_evidence():
    """Correlation of the overall score with the day 0 to +1 reaction across the benchmark, if the saved event study exists."""
    try:
        import pandas as pd
        from scipy.stats import spearmanr
        import data_access as da
        r = pd.read_csv('data/event_returns.csv')
        d = da.benchmark().merge(r[r['benchmark'] == 'SPY'], on='call_id').dropna(subset=['composite', 'car_day'])
        if len(d) < 8:
            return None
        rho, p = spearmanr(d['composite'], d['car_day'])
        return len(d), rho, p
    except Exception:
        return None


VERDICTS = {
    'none': [
        'No prices, no story. And even with prices, we only ever observe <b>one history</b>: we cannot rewind the tape and replay this call with different words.',
        'Without a price series there is nothing to test. Remember: a transcript tells you what was said, the market tells you what was believed.',
        'No market data, so no verdict. A good analyst says "I do not know" before inventing a story.',
    ],
    'small': [
        'The market more or less shrugged ({day} vs. the S&amp;P 500). "Nothing unusual happened" is a perfectly respectable research finding. Write it down; do not torture the data until it confesses.',
        'A {day} move against the market: that is an ordinary day for this stock. If you build a story on this, you are fitting noise.',
        'The reaction ({day}) sits inside the normal day-to-day wobble. The call may have mattered, but this data cannot tell us that, and saying so is the honest answer.',
        'Very little happened ({day}). Before you blame or credit the CEO\'s adjectives, ask whether the market had already heard everything it needed to hear.',
    ],
    'match': [
        'Tone and price agreed ({day} vs. the market). Before celebrating, ask the uncomfortable question: <b>how many calls and measures did we try before finding one that lines up?</b>',
        'The words and the price pointed the same way ({day}). Nice, but one agreeing case is an anecdote. Show me it working on calls you did not choose.',
        'A clean match ({day}). The temptation now is to say the model "predicted" it. It described the call; whether description becomes prediction needs many more calls and a test year.',
        'Tone and market agreed ({day}). Be careful with the causal arrow: the results released with the call probably drove both the language and the price.',
    ],
    'clash': [
        'The words said one thing, the price ({day}) said another. The market did not read our dictionary; it read the numbers, the guidance and the headlines of that week.',
        'Upbeat or downbeat language, and the price went the other way ({day}). Management talks to the room; the market listens to the whole world.',
        'A clash ({day}). This is the most interesting kind of result: it tells you what the language model <b>cannot</b> see, such as expectations, rates and positioning.',
        'Tone and price disagreed ({day}). Do not rush to "fix" the model until it agrees. Sometimes the right conclusion is that tone was not the story.',
    ],
    'neutral': [
        'A sizeable move ({day}) after a call with a neutral tone. The language did not tell this story, so the explanation is in the context: results, guidance, rates, sector news.',
        'Neutral words, big reaction ({day}). If the transcript is calm and the stock is not, look at what the transcript does not contain: the numbers versus expectations.',
        'The call sounded ordinary, the stock did not ({day}). That is a reminder that sentiment is one input among many, and not always the loudest one.',
    ],
}

NOISE = {
    'none': ['no prices to judge', 'nothing to measure'],
    'small': ['mostly noise', 'an ordinary day', 'well inside normal'],
    'mid': ['some signal, plenty of noise', 'noticeable, not conclusive'],
    'big': ['signal... or a very loud coincidence', 'front-page move, still one observation'],
}

HOMEWORK = [
    'Read the financial headlines from the week of this call, then decide whether the transcript or the macro moved the stock. Running the model is not the skill; spotting the fluke is.',
    'Find two other companies in the same sector that reported that week. Did they move the same way? If so, the call may not be the story.',
    'Write down, before looking at any more data, what result would convince you the model is wrong. Then go and look for it.',
    'Compare this call with the company\'s previous call. A change in tone usually says more than the level of tone.',
    'Check the earnings surprise (actual vs. expected EPS) for this quarter. If it explains the move, our sentiment measure needs to earn its place on top of it.',
]

GENERAL = [
    ['Where does this result sit between a <b>roulette wheel</b> (pure chance, no memory) and <b>Halley\'s Comet</b> (predictable to the day)? One call is a single spin; finance usually lives somewhere in between.',
     'Is this a roulette table or an astronomy problem? Earnings reactions have some memory and some context, but a lot of randomness. Decide which before trusting the result.'],
    ['We only get to run history <b>once</b>. We cannot replay this quarter with a gloomier CEO and see what the stock would have done, so be humble about causes.',
     'There is exactly one version of this quarter. Machine learning likes thousands of repetitions; markets give us one. That is why <b>many features, few outcomes</b> is dangerous.'],
    ['If you test enough sentiment measures, one of them will always "explain" the move. That is <b>seeing faces in the clouds</b>: count your trials and discount the result accordingly.',
     'How many versions of the score did we try before this one? Every extra trial makes a good-looking result a little less impressive.'],
    ['The stock did not "go down" on its own: on those days there were simply <b>more sellers than buyers</b>. Markets are people, not machines.',
     'Prices are an agreement between people. A move after the call tells you what the crowd decided, not what the company is "worth".'],
    ['Finance is closer to the <b>humanities</b> than to physics. The reaction is a story about context and beliefs, and our model reads only one chapter of it.',
     'Do not expect Newtonian laws here. Earnings calls are social events, and the market reaction is a social response.'],
    ['Valuation is partly a <b>belief system</b>: if enough investors believe the story told on the call, the price follows for a while. The question is how long the belief lasts.',
     'There is no single "true value" this call revealed. It shifted expectations, and expectations are what prices are made of.'],
    ['Watch for <b>look-ahead bias</b>: make sure every number used to judge this call was actually available on the call date, not filled in later.',
     'If we later build a strategy from calls like this, check <b>survivorship bias</b>: companies that disappeared also held earnings calls once.'],
    ['Compare this with a <b>central bank press conference</b>: there the market reacts within minutes to a single word. Earnings calls are slower, noisier and full of jargon.',
     'Try the same exercise on a central bank press conference after a rate decision. The daily and weekly reaction there is a useful benchmark for how much words can move markets.'],
    ['A model that happened to work once can make someone a star, and if it fails there is always an excuse. Ask who benefits if this result is believed.',
     'Be wary of the incentive to find a result. A striking chart gets attention; a careful "inconclusive" protects your reputation in five years.'],
]

SECTOR = {
    'Bank': ['For a bank, check the <b>yield curve and credit spreads</b> that week before blaming the CEO\'s adjectives. Rates move bank stocks more than vocabulary does.',
             'Banks live on <b>leverage and trust</b>. If funding costs or deposit worries moved that week, they will dominate whatever was said about the quarter.',
             'Bank calls are full of words like "stress", "provisions" and "losses" that are routine accounting. That is why we compare banks with banks.'],
    'Tech': ['For tech, the story this year is the <b>AI build-out</b>: is the market starting to charge a higher risk premium for all that capital spending? That can swamp anything said on one call.',
             'Heavily invested tech companies are also <b>bond market stories</b>. When borrowing costs rise, equity holders get nervous, whatever the CEO says.',
             'In tech, expectations run ahead of results. A good quarter can still disappoint if the market had priced in a great one.'],
}


def render(res, peer_word, sector, reaction):
    """res: scored call; reaction: dict from the market section (or None if no prices)."""
    import random
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="pm-head"><span class="k">F · BONUS</span><span class="pm-sub">SUBSCRIBERS ONLY</span></div>',
                unsafe_allow_html=True)
    with st.expander("Prof. Mehmet's take on how the market moved", expanded=False, icon=':material/school:'):
        shuffle = st.session_state.get('pm_shuffle', 0)
        key = f"{res.get('lm_tone', 0):.4f}|{res.get('composite', 0):.4f}|{sector}|{shuffle}"
        rng = random.Random(key)
        signal = res.get('signal', 'Neutral')
        cond = []

        size, case, day = np.nan, 'none', np.nan
        if reaction and np.isfinite(reaction.get('day', np.nan)):
            day, size, up = reaction['day'], reaction['size'], reaction['day'] >= 0
            if not np.isfinite(size) or size < 1.96:
                case = 'small'
            elif (signal == 'Positive' and up) or (signal == 'Negative' and not up):
                case = 'match'
            elif signal in ('Positive', 'Negative'):
                case = 'clash'
            else:
                case = 'neutral'
            pre, week = reaction.get('pre', np.nan), reaction.get('week', np.nan)
            if np.isfinite(pre) and abs(pre) > 0.03:
                cond.append(rng.choice([
                    f'The stock had already moved <b>{pre:+.1%}</b> against the market in the ' + features.pre_window_label() + ' the call. Was the market reading the transcript, or had it already priced in the news?',
                    f'A <b>{pre:+.1%}</b> run against the market <i>before</i> the call. Some of the news was probably in the price already; the call may only have confirmed it.']))
            if np.isfinite(week):
                if np.sign(week) != np.sign(day):
                    cond.append(rng.choice([
                        'The first-day move <b>reversed within a week</b>. On the day there were more sellers (or buyers); a week later the crowd changed its mind.',
                        f'Day one said {day:+.1%}, the first week said {week:+.1%}. First reactions are often overreactions; patience is also a data point.']))
                elif abs(week) > abs(day) * 1.3:
                    cond.append(rng.choice([
                        f'The move <b>kept going</b> through the first week ({week:+.1%}). Slow digestion of news is exactly where a tradable signal could hide, if it repeats across many calls.',
                        f'Drift: {day:+.1%} on the reaction days, {week:+.1%} by the end of the week. If that pattern holds across calls, it is worth a strategy; if not, it is a story.']))
        verdict = rng.choice(VERDICTS[case]).format(day=f'{day:+.1%}' if np.isfinite(day) else '')

        ts = res.get('tone_shift', np.nan)
        if np.isfinite(ts) and ts < 0:
            cond.append(rng.choice([
                'Management sounded better in the script than live. Naturally: the script was rehearsed. The Q&amp;A is where you hear <b>the sound in the room</b>.',
                'The tone dropped once analysts started asking questions. Prepared remarks are marketing; the Q&amp;A is the negotiation.']))
        elif np.isfinite(ts) and ts > 0:
            cond.append(rng.choice([
                'Management sounded <b>more</b> confident live than in the script. Either they were well prepared, or the analysts were too polite. Which one?',
                'The Q&amp;A went better than the script. Ask whether the questions were tough enough to test anything.']))
        ev = _benchmark_evidence()
        if ev:
            n, rho, p = ev
            cond.append(rng.choice([
                f'Across our {n} benchmark calls the overall score and the next-day reaction have a correlation of <b>{rho:+.2f}</b> (p-value {p:.2f}). With a sample this small, the honest answer is "we do not know yet", and that is a respectable answer.',
                f'Benchmark check: correlation <b>{rho:+.2f}</b> between tone and next-day return across {n} calls (p-value {p:.2f}). One call cannot outvote {n}.']))

        bullets = cond[:3]
        if sector in SECTOR:
            bullets.append(rng.choice(SECTOR[sector]))
        general = [rng.choice(g) for g in rng.sample(GENERAL, len(GENERAL))]
        bullets += general[:max(2, 6 - len(bullets))]

        if case == 'none':
            noise_key, pin = 'none', 5
        else:
            noise_key = 'small' if not np.isfinite(size) or size < 1.96 else 'mid' if size < 2.58 else 'big'
            pin = 5 if not np.isfinite(size) else float(np.clip(size / 3 * 100, 2, 98))
        noise_txt = rng.choice(NOISE[noise_key])
        title = rng.choice(["Prof. Mehmet's office hours", 'Prof. Mehmet takes the floor', 'A word from Prof. Mehmet', 'Prof. Mehmet, after the bell'])
        intro = rng.choice(['Questions he would probably ask in class', 'What he would push us on', 'Before you write the report, consider'])

        st.markdown(f"""<div class="pm-card">
<div class="pm-top"><div class="pm-av">PM</div><div><h4>{esc(title)}</h4>
<div class="s">An imagined take on {esc(peer_word.removeprefix('all '))}, written by Group 9 in the spirit of the MMA 823 lectures</div></div></div>
<div class="pm-verdict">{verdict}</div>
<div class="pm-meter"><div class="lbl">NOISE-O-METER (|t| OF THE REACTION): {esc(noise_txt.upper())}</div>
<div class="pm-bar"><div class="pm-pin" style="left:{pin:.0f}%"></div></div>
<div class="pm-scale"><span>|t| 0 · normal noise</span><span>1</span><span>2 · unusual (5% level)</span><span>3+ · front-page news</span></div></div>
<p style="margin:6px 0 6px;font-weight:900;color:#fff;font-size:14px">{esc(intro)}</p>
<ul>{''.join(f'<li>{b}</li>' for b in bullets)}</ul>
<div class="pm-hw"><b>Homework:</b> {rng.choice(HOMEWORK)}</div></div>
<div class="pm-disc">Light-hearted bonus written by the students of Group 9, inspired by themes from the MMA 823 lectures. It is not written,
reviewed or endorsed by the professor and does not quote him. Not financial advice.</div>""", unsafe_allow_html=True)
        if st.button('Ask him another question', key='pm_more', icon=':material/refresh:'):
            st.session_state['pm_shuffle'] = shuffle + 1
            st.rerun()
