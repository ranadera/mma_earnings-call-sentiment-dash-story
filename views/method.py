import pandas as pd
import streamlit as st

import data_access as da
import ui
from ui import esc, term

bench = da.benchmark()
lex = da.lexicon()

ui.hero('Method & decisions', 'How every number is built',
        'The methods behind each measure, the decisions we made along the way, the assumptions they rest on, '
        'what the analysis cannot tell us yet, and where we would take it next.')

ui.section('01 · SENTIMENT METHODS', 'Three ways to measure tone',
           'We tried several methods because no single one is perfect. Each reads the same text differently; agreement between them gives confidence.')
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.card('Loughran-McDonald dictionary', 'Counts positive, negative and uncertainty words from a list built for financial filings. '
            'Transparent and finance-aware. <b>Our main measure.</b>', tag='Primary')
with c2:
    ui.card('VADER', 'Rule-based tool for everyday text. Handles "not", "very" and punctuation. '
            'A useful second opinion, but it misreads finance terms.', tag='Cross-check')
with c3:
    ui.card('TextBlob', 'Scores adjectives for polarity. Simple and fast; a third opinion on the same text.', tag='Cross-check')
with c4:
    ui.card('FinBERT', 'An AI model trained on financial news that reads sentences in context. Included in the research notebook, '
            'but left out of this app to keep it small and fast enough to run anywhere.', tag='Notebook only')
st.write('')
ui.note(f'<b>How they combine.</b> Each method is put on a common scale (a z-score: how far a call is from the average, in standard deviations). '
        f'The {term("Overall score", "overall score")} is their average. Calls are then ranked and split into thirds to give the {term("Signal", "signal")}.')

ui.section('02 · MEASURES', 'What each number means')
defs = [
    ('Tone', 'Positive minus negative finance words, per 100 words.', 'Is the language upbeat?'),
    ('Sector-adjusted tone', 'Tone after setting aside routine sector jargon.', 'Is it upbeat once jargon is ignored?'),
    ('Tone change into Q&A', 'Tone of management answers minus tone of the presentation.', 'Does the message hold up under questioning?'),
    ('Analyst pushback', 'Negative finance words per 100 words in analyst questions.', 'How critical are investors?'),
    ('Hedging', 'Uncertainty words in the Q&A minus the presentation.', 'Does management become less certain live?'),
    ('Management conviction', 'Average of: answers more positive than questions, tone change, less hedging, less pushback (each standardised).', 'Does management convince?'),
    ('Tone through the call', 'Tone of each tenth of the call, in order.', 'Does sentiment fade or build as the call goes on?'),
]
st.dataframe(pd.DataFrame(defs, columns=['Measure', 'How it is calculated', 'Question it answers']), hide_index=True, width='stretch')

ui.section('03 · SECTOR DICTIONARIES', 'Teaching the model each sector\'s language',
           'A general finance dictionary misreads some everyday sector jargon. We keep a small, transparent list of terms that are routine in each sector '
           'and set them aside in the sector-adjusted tone. Any sector can be added by adding rows to this list.')
st.dataframe(lex.rename(columns={'sector': 'Sector', 'term': 'Term set aside', 'reason': 'Why'}), hide_index=True, width='stretch')
ui.note('<b>Effect:</b> the bank-tech tone gap narrows by about a tenth, and rankings barely change. Jargon is part of the story, not all of it, '
        'so we also compare each call with its own sector.')

ui.section('04 · EXECUTIVE DECISIONS', 'Choices we made, and why')
decisions = [
    ('Finance dictionary as the main measure', 'General tools treat words like "liability" and "tax" as negative. A finance-specific word list reads earnings calls more accurately.'),
    ('Remove legal disclaimers', 'Every call opens with a near-identical "forward-looking statements" warning full of negative words. It carries no information, so it is removed.'),
    ('Treat "question" as neutral', 'The dictionary counts "question" as negative (as in "called into question"). On a call it means "my question is...". It was the most frequent "negative" word, so we removed it.'),
    ('Relative signal, not absolute thresholds', 'There is no natural cut-off for "positive". Ranking calls into thirds is transparent and robust in a small sample.'),
    ('Compare within sectors', 'Banks use more words the dictionary counts as negative. Comparing banks with banks avoids penalising a whole sector for its vocabulary.'),
    ('Market-adjusted returns, entry the day after', 'Abnormal returns remove market-wide moves. The strategy trades only after the call is public, so it never uses information early.'),
    ('Keep the model light', 'Dictionary methods run in seconds, need no GPU and are easy to explain and extend to new sectors. FinBERT stays as an optional upgrade.'),
    ('Exclude summaries', 'One file (NVIDIA) was a Bloomberg summary, not a transcript: Bloomberg\'s words, not management\'s. It is scored but not ranked.'),
]
for i in range(0, len(decisions), 2):
    cols = st.columns(2)
    for col, (t, b) in zip(cols, decisions[i:i + 2]):
        with col:
            ui.card(t, b, tag=f'Decision {i + decisions[i:i + 2].index((t, b)) + 1}')
    st.write('')

ui.section('05 · ASSUMPTIONS', 'What the analysis takes as given')
st.markdown(f"""<div class="qm-card"><p style="color:{ui.INK}">
• Transcripts are accurate and speaker labels are correct.<br>
• The Q&amp;A starts at the "Questions And Answers" heading, or at the first analyst question when there is no heading.<br>
• Speakers who are not analysts or the operator are management.<br>
• ±21 trading days is about one calendar month; day 0 is the call date (or the next trading day).<br>
• The S&amp;P 500 (or a sector ETF) is a fair benchmark for each stock, moving one-for-one with it.<br>
• No transaction costs, borrowing costs or position limits in the long-short test.<br>
• Tone is measured from text only, not voice.</p></div>""", unsafe_allow_html=True)

ui.section('06 · LIMITATIONS', 'What this cannot tell us yet')
lim = st.columns(3)
with lim[0]:
    ui.card('Small sample', f'{len(bench)} calls, few per sector, mostly from the same quarters. Results describe this sample; they are not yet a proven signal.')
with lim[1]:
    ui.card('Words, not meaning', 'Dictionaries miss context, sarcasm and most negation. The sector dictionary and FinBERT address part of this.')
with lim[2]:
    ui.card('Tone is not the whole story', 'Prices react to the numbers and guidance too. Tone should be read alongside the earnings surprise.')

ui.section('07 · NEXT STEPS', 'Where we would take this next')
nxt = [
    ('More sectors and quarters', 'Grow the benchmark (more banks, more sectors, several years) so each sector has its own calibrated comparison group.'),
    ('Change in tone', 'Compare each company with its own previous call. Research suggests a change in tone is a stronger signal than its level.'),
    ('Central bank press conferences', 'Apply the same method to central bank press conferences after rate decisions, and compare the market\'s daily and weekly reaction with earnings calls.'),
    ('Separate tone from results', 'Add the earnings surprise (actual vs. expected EPS) so tone is judged beyond the headline numbers.'),
    ('Context-aware models', 'Run FinBERT or a large language model alongside the dictionary to capture meaning, not just word counts.'),
    ('Voice and news', 'Add audio features (pauses, hesitation) and news and analyst-note sentiment around each call.'),
]
for i in range(0, len(nxt), 3):
    cols = st.columns(3)
    for col, (t, b) in zip(cols, nxt[i:i + 3]):
        with col:
            ui.card(t, b)
    st.write('')

ui.section('08 · GLOSSARY', 'Plain-language definitions')
st.dataframe(pd.DataFrame(sorted(ui.GLOSSARY.items()), columns=['Term', 'Meaning']), hide_index=True, width='stretch', height=460)

ui.section('09 · CODE & DATA', 'Reproducibility')
ui.note('The full analysis lives in the project\'s Jupyter notebooks: <b>sentiment_analysis</b> (Parts 2 and 3), <b>event_study</b> (Part 4) and '
        '<b>stock_reports</b> (Part 1). This app uses the same scoring code. Bloomberg transcripts are licensed and are not published; '
        'only derived scores are included in the repository.')
ui.references(extra=[ui.FINBERT])
ui.footer()
