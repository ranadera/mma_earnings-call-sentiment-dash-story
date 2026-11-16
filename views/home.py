import streamlit as st

import data_access as da
import ui
from ui import term

bench = da.benchmark()
calibrated, counts = da.calibrated_sectors(bench)

ui.hero('Quanta-Mentals · MMA 823 Analytics for Financial Markets',
        'Reading between the lines of earnings calls',
        'A research platform that turns earnings call transcripts into <b>sentiment signals</b> for asset managers and hedge funds, '
        'and tests whether those signals say anything about how the stock moves next.')
ui.team()
ui.tiles([
    ('analyze', 'upload_file', 'Analyze a call', 'Upload any transcript and get its sentiment signal and price reaction in seconds.'),
    ('explorer', 'leaderboard', 'Benchmark explorer', 'Rankings, scripted vs. live tone, analyst pushback.'),
    ('market_reaction', 'show_chart', 'Market reaction', 'Event study, correlations and a long-short test.'),
    ('stocks', 'description', 'Stock reports', 'Business, valuation, price history and risk.'),
    ('method', 'menu_book', 'Method & decisions', 'How it is built, our choices and limits.'),
])
ui.coverage_banner(bench, calibrated, counts)

ui.section('01 · THE BRIEF', 'What our client asked for',
           'Quanta-Mentals builds data-driven research for investment firms. Our client wanted to know whether the <i>language</i> of an '
           f'{term("Earnings call", "earnings call")}, not just the reported numbers, carries information that could support a trading strategy.')
c1, c2, c3 = st.columns(3)
with c1:
    ui.card('The question', 'Can we measure how confident or cautious management sounds, and does that tone line up with how the stock performs after the call?', tag='Why')
with c2:
    ui.card('The data', f'{len(bench)} earnings call transcripts from Bloomberg and LSEG, across {len(calibrated)} sectors '
            f'({", ".join(f"{counts[s]} {s.lower()}" for s in calibrated)}), plus daily stock prices around each call.', tag='What')
with c3:
    ui.card('The output', 'Sentiment indicators, a market-reaction test, one-page stock reports, and this app, which scores any new transcript in seconds.', tag='Deliverables')

ui.section('02 · HOW IT WORKS', 'From transcript to signal in four steps')
st.markdown(f"""<div class="qm-steps">
<div class="qm-step"><span class="n">STEP 1</span><h5>Read</h5><p>Split the call into the {term("Prepared presentation", "prepared presentation")}, analysts' questions and management's answers.</p></div>
<div class="qm-step"><span class="n">STEP 2</span><h5>Score</h5><p>Count upbeat and downbeat finance words with the {term("Loughran-McDonald dictionary", "Loughran-McDonald dictionary")}, cross-checked by {term("VADER")} and {term("TextBlob")}.</p></div>
<div class="qm-step"><span class="n">STEP 3</span><h5>Compare</h5><p>Place the call against the {term("Benchmark", "benchmark")}, ideally within its own sector, and assign a {term("Signal", "signal")}.</p></div>
<div class="qm-step"><span class="n">STEP 4</span><h5>Test</h5><p>Check how the stock moved after the call with an {term("Event study", "event study")} and a {term("Long-short strategy", "long-short strategy")}.</p></div>
</div>""", unsafe_allow_html=True)

ui.section('03 · WHAT WE FOUND', 'Headline findings', 'Hover over any dotted term for a plain-language explanation.')
fell = int((bench['tone_shift'] < 0).sum())
tech, bank = bench[bench['sector'] == 'Tech'], bench[bench['sector'] == 'Bank']
top, bottom = bench.loc[bench['composite'].idxmax()], bench.loc[bench['composite'].idxmin()]
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi(f'{term("Tone change into Q&A", "Tone fell in the Q&A")}', f'{fell} of {len(bench)}',
           'calls: management sounded less positive answering live questions than in its script.')
with k2:
    ui.kpi(f'{term("Tone", "Average tone")}: tech vs. banks', f'{tech["lm_tone"].mean():.2f} vs {bank["lm_tone"].mean():.2f}',
           'net positive finance words per 100. Banks sound more cautious on paper.', color=ui.PUMPKIN)
with k3:
    ui.kpi(f'{term("VADER", "General tool")}: tech vs. banks', f'{tech["vader"].mean():.2f} vs {bank["vader"].mean():.2f}',
           'almost no gap, so much of the bank gap is <b>finance jargon</b>, not pessimism.', color=ui.SKY)
with k4:
    ui.kpi('Most vs. least positive', f'{top["name"]} · {bottom["name"]}',
           f'{top["label"]} led; {bottom["label"]} trailed.', color=ui.OLIVE)

st.write('')
ui.note('<b>Why it matters for an investor.</b> Scripted remarks are polished; the live Q&A is where caution shows. '
        'Comparing the two, and comparing banks with banks rather than with tech, is what turns raw word counts into a usable signal. '
        'Whether that signal predicts returns is tested on the <b>Market reaction</b> page.')

ui.footer()
