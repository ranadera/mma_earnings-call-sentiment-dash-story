"""Quanta-Mentals design system: colours, CSS, reusable components, glossary and chart theme."""
import html

import altair as alt
import streamlit as st

SMITH_BLUE, AZURE, SKY, OCEAN, MINT = '#002452', '#1D5FB4', '#3B7CC4', '#FABD0F', '#FABD0F'
GOLD, RED = '#FABD0F', '#B90E31'
ROSE, OLIVE, PUMPKIN, INK, MUTED, LINE, TINT = '#B90E31', '#2F7D32', '#C46A00', '#1A2233', '#5B6475', '#E2E6EC', '#F5F7FA'
SIGNAL_COLORS = {'Positive': OLIVE, 'Neutral': '#858E9F', 'Negative': ROSE}
SECTOR_PALETTE = [SMITH_BLUE, '#D19A00', '#6B4FBB', '#0E8A7E', '#A0522D', '#5A6B8C']

GLOSSARY = {
    'Earnings call': 'A quarterly conference call where a company presents its results, followed by questions from analysts who cover the stock.',
    'Transcript': 'The written record of an earnings call, split by speaker.',
    'Sentiment': 'Whether the language used is upbeat or downbeat. Here it is measured from the words management uses.',
    'Tone': 'Positive minus negative finance words for every 100 words spoken. Above 0 means more upbeat than downbeat language.',
    'Sector-adjusted tone': 'Tone after ignoring words that are routine jargon in the sector (e.g. "stress test" for banks, "mission-critical" for tech).',
    'Loughran-McDonald dictionary': 'A word list built by academics from thousands of company filings. Unlike everyday sentiment tools it knows that words like "liability" or "tax" are not bad news in finance.',
    'VADER': 'A rule-based sentiment tool built for everyday text such as social media. Used as a second opinion.',
    'TextBlob': 'A simple general-purpose sentiment tool based mostly on adjectives. Used as a third opinion.',
    'FinBERT': 'An AI language model trained on financial news that reads whole sentences in context. Available in the research notebook; left out of this demo to keep the app small and fast.',
    'Overall score': 'The average of the three methods after putting them on the same scale. 0 is the average benchmark call; +1 is one standard deviation more positive.',
    'Signal': 'Calls are ranked on the overall score and split into thirds: Positive (top third), Neutral, Negative (bottom third).',
    'Prepared presentation': 'The scripted opening part of the call, read by management.',
    'Q&A': 'The live part of the call where analysts ask questions and management answers unscripted.',
    'Tone change into Q&A': 'Management tone in its live answers minus its tone in the prepared presentation. Negative means the message softened under questioning.',
    'Analyst pushback': 'Negative finance words per 100 words in analysts\' questions: a measure of how critical the questions were.',
    'Hedging': 'Use of uncertain words such as "may", "approximately" or "depends". More hedging suggests less confidence.',
    'Management conviction': 'How well management held its message: answers more positive than the questions, little hedging, and tone holding up in the Q&A. 0 = average call.',
    'Benchmark': 'The set of past earnings calls each new call is compared against.',
    'Calibrated': 'The sectors with enough benchmark calls for a fair comparison. Nothing is trained; scores are compared against these calls.',
    'Abnormal return': 'A stock\'s return minus the market\'s return on the same day. It strips out market-wide moves so what is left is the company-specific reaction.',
    'Cumulative abnormal return (CAR)': 'Abnormal returns added up over a window, e.g. the day of the call and the day after.',
    'Event study': 'A standard finance method that measures how a stock moved around an event (here, the earnings call) compared with the market.',
    'Long-short strategy': 'Buy the stocks with a positive signal and short-sell those with a negative one. It makes money if positive calls beat negative ones, whatever the market does.',
    'Correlation': 'How closely two measures move together, from -1 to +1. Spearman correlation uses ranks, so a single extreme stock move cannot dominate.',
    'p-value': 'The chance of seeing a result this strong by luck if there were no real relationship. Below 0.05 is the usual bar for "statistically significant".',
    'AUC': 'Area under the ROC curve: the chance the model ranks a randomly chosen "beat the market" call above a "lagged" one. 0.5 is a coin flip.',
    'Volatility': 'How much a stock\'s price swings, measured as the annualised standard deviation of daily returns.',
    'Maximum drawdown': 'The largest fall from a previous high over the period.',
    'Beta': 'How much the stock tends to move for a 1% move in the S&P 500. Above 1 means more volatile than the market.',
    'P/E ratio': 'Price per share divided by earnings per share: how many dollars investors pay for $1 of annual profit.',
    'Forward P/E': 'Price divided by the earnings analysts expect over the next 12 months.',
    'P/B ratio': 'Price divided by book value (assets minus liabilities) per share. The key valuation ratio for banks.',
    'EV/EBITDA': 'Enterprise value (market value plus net debt) divided by operating earnings before depreciation. Not meaningful for banks, whose debt is part of the business.',
    'Dividend yield': 'Annual dividends per share divided by the share price.',
    'ROE': 'Return on equity: annual profit as a percentage of shareholders\' equity. A core profitability measure for banks.',
    'Market cap': 'Share price times the number of shares: the stock market value of the company.',
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap');
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], .stMarkdown, button, input, textarea, select {{
  font-family: 'Lato', 'Helvetica Neue', Arial, sans-serif !important; }}
.qm-ic {{ width: 28px; height: 28px; fill: currentColor; flex: none; }}
[data-testid="stAppViewContainer"] {{ background: #FFFFFF; }}
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], footer {{ display: none !important; }}

/* top navigation bar */
header[data-testid="stHeader"] {{ background: {SMITH_BLUE}; border-bottom: 4px solid {GOLD}; height: 62px; }}
header[data-testid="stHeader"] [data-testid="stToolbar"] {{ height: 58px; }}
header[data-testid="stHeader"] [data-testid="stToolbar"]::before {{ content: "QUANTA-MENTALS"; color: #fff; font-weight: 900; letter-spacing: .14em;
  font-size: 14px; padding: 0 18px 0 20px; margin-right: 4px; border-right: 1px solid rgba(255,255,255,.22); white-space: nowrap; align-self: center; }}
[data-testid="stTopNavLink"] {{ border-radius: 4px; padding: 6px 10px !important; }}
[data-testid="stTopNav"] span, [data-testid="stTopNav"] svg {{ color: #C9D3E6 !important; fill: #C9D3E6; }}
[data-testid="stTopNavLink"] span {{ font-weight: 700; font-size: 13.5px; }}
[data-testid="stTopNavLink"]:hover {{ background: rgba(255,255,255,.08) !important; }}
[data-testid="stTopNavLink"]:hover span {{ color: #fff !important; }}
[data-testid="stTopNavLink"][aria-current="page"], [data-testid="stTopNavLink"].active {{ background: rgba(250,189,15,.14) !important; box-shadow: inset 0 -3px 0 {GOLD}; }}
[data-testid="stTopNavLink"][aria-current="page"] span {{ color: {GOLD} !important; }}
[data-testid="stSidebarCollapsedControl"] button, [data-testid="stExpandSidebarButton"] {{ color: #fff !important; }}

.block-container {{ padding-top: 5.2rem; max-width: 1240px; }}
h1, h2, h3 {{ color: {SMITH_BLUE}; font-weight: 900 !important; letter-spacing: -0.01em; }}

/* page header */
.qm-hero {{ padding: 6px 0 20px; margin-bottom: 18px; border-bottom: 1px solid {LINE}; position: relative; }}
.qm-hero::after {{ content: ""; position: absolute; left: 0; bottom: -1px; width: 120px; height: 3px; background: {GOLD}; }}
.qm-kicker {{ color: {RED}; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; margin: 0 0 6px; }}
.qm-hero h1 {{ color: {SMITH_BLUE} !important; font-size: clamp(28px, 3.2vw, 38px); line-height: 1.12; margin: 0 0 8px; padding: 0; }}
.qm-hero p.qm-sub {{ color: {MUTED}; font-size: 16.5px; margin: 0; max-width: 54em; line-height: 1.55; }}
.qm-hero b {{ color: {SMITH_BLUE}; }}

.qm-banner {{ border: 1px solid {LINE}; border-left: 4px solid {GOLD}; background: #FFFCF2; padding: 11px 16px; margin: 4px 0 18px;
  color: {INK}; border-radius: 0 6px 6px 0; font-size: 14px; line-height: 1.5; }}
.qm-banner b {{ color: {SMITH_BLUE}; }}

/* section titles */
.qm-section {{ margin: 34px 0 12px; }}
.qm-section .qm-num {{ color: {MUTED}; font-weight: 900; font-size: 11.5px; letter-spacing: .12em; display: flex; align-items: center; gap: 8px; }}
.qm-section .qm-num::before {{ content: ""; width: 14px; height: 14px; background: {GOLD}; display: inline-block; }}
.qm-section h2 {{ margin: 4px 0 6px; font-size: 23px; padding: 0 0 8px; border-bottom: 1px solid {LINE}; }}
.qm-section p {{ color: {MUTED}; font-size: 15px; margin: 6px 0 0; max-width: 58em; line-height: 1.55; }}

.qm-card {{ background: #fff; border: 1px solid {LINE}; border-radius: 6px; padding: 16px 18px; height: 100%; }}
.qm-card h4 {{ margin: 0 0 6px; color: {SMITH_BLUE}; font-size: 16px; font-weight: 900; }}
.qm-card p {{ margin: 0; color: {MUTED}; font-size: 14.2px; line-height: 1.5; }}
.qm-card .qm-tag {{ display: inline-block; font-size: 10.5px; font-weight: 900; letter-spacing: .1em; color: {SMITH_BLUE}; background: #FFF3CC;
  padding: 2px 7px; border-radius: 3px; text-transform: uppercase; margin-bottom: 8px; }}

.qm-kpi {{ background: #fff; border: 1px solid {LINE}; border-left: 4px solid {AZURE}; border-radius: 6px; padding: 12px 14px 11px; height: 100%; }}
.qm-kpi .lbl {{ color: {MUTED}; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }}
.qm-kpi .lbl .qm-term {{ white-space: normal; }}
.qm-kpi .val {{ color: {SMITH_BLUE}; font-size: 27px; font-weight: 900; line-height: 1.15; margin: 5px 0 3px; font-variant-numeric: tabular-nums; }}
.qm-kpi .note {{ color: {MUTED}; font-size: 12.5px; line-height: 1.4; }}
.qm-kpi .note b {{ color: {INK}; }}

/* rating box, Seeking Alpha style */
.qm-signal {{ display: flex; align-items: center; gap: 20px; background: #fff; border: 1px solid {LINE}; border-radius: 6px; padding: 14px 18px; margin: 8px 0 16px; }}
.qm-signal .pill {{ font-size: 20px; font-weight: 900; color: #fff; border-radius: 4px; padding: 10px 18px; white-space: nowrap; letter-spacing: .02em; text-transform: uppercase; }}
.qm-signal .txt {{ color: {INK}; font-size: 15px; line-height: 1.5; }}

.qm-term {{ border-bottom: 1.5px dotted {AZURE}; cursor: help; position: relative; white-space: nowrap; }}
.qm-term:hover::after, .qm-term:focus::after {{ content: attr(data-tip); position: absolute; left: 0; top: 135%; z-index: 50; width: 280px; white-space: normal;
  background: {SMITH_BLUE}; color: #fff; font-size: 13px; font-weight: 400; line-height: 1.45; padding: 10px 12px; border-radius: 6px;
  border-top: 3px solid {GOLD}; box-shadow: 0 8px 24px rgba(0,36,82,.25); text-transform: none; letter-spacing: 0; }}
.qm-note {{ background: {TINT}; border-radius: 6px; padding: 12px 16px; color: {INK}; font-size: 14px; line-height: 1.55; margin: 8px 0; }}
.qm-note b {{ color: {SMITH_BLUE}; }}
.qm-warn {{ background: #FFF8E6; border-left: 4px solid {GOLD}; border-radius: 0 6px 6px 0; padding: 11px 15px; color: {INK}; font-size: 14px; margin: 8px 0; }}
.qm-warn b {{ color: {SMITH_BLUE}; }}

.qm-steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
.qm-step {{ background: #fff; border: 1px solid {LINE}; border-radius: 6px; padding: 14px 16px; }}
.qm-step .n {{ color: {RED}; font-weight: 900; font-size: 11.5px; letter-spacing: .1em; }}
.qm-step h5 {{ margin: 4px 0 4px; color: {SMITH_BLUE}; font-size: 15px; font-weight: 900; }}
.qm-step p {{ margin: 0; color: {MUTED}; font-size: 13.5px; line-height: 1.45; }}

/* navigation tiles */
.qm-tiles {{ display: grid; grid-template-columns: 1.35fr repeat(4, 1fr); gap: 12px; margin: 4px 0 8px; }}
@media (max-width: 1000px) {{ .qm-tiles {{ grid-template-columns: repeat(2, 1fr); }} }}
a.qm-tile {{ display: flex; flex-direction: column; gap: 6px; background: {SMITH_BLUE}; color: #fff !important; text-decoration: none !important;
  border-radius: 8px; padding: 16px 16px 14px; position: relative; border-bottom: 4px solid transparent;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease; min-height: 128px; }}
a.qm-tile:hover {{ transform: translateY(-3px); box-shadow: 0 10px 22px rgba(0,36,82,.22); border-bottom-color: {GOLD}; }}
a.qm-tile .qm-ic {{ color: {GOLD}; }}
a.qm-tile .t {{ font-weight: 900; font-size: 16px; color: #fff; }}
a.qm-tile .d {{ font-size: 12.8px; line-height: 1.4; color: #C9D3E6; }}
a.qm-tile .go {{ position: absolute; right: 14px; top: 14px; color: #C9D3E6; width: 20px; height: 20px; transition: transform .15s ease; }}
a.qm-tile:hover .go {{ transform: translateX(3px); color: {GOLD}; }}
a.qm-tile.primary {{ background: {GOLD}; }}
a.qm-tile.primary .t, a.qm-tile.primary .go {{ color: {SMITH_BLUE}; }}
a.qm-tile.primary .d {{ color: #3A3200; }}
a.qm-tile.primary .qm-ic {{ color: {SMITH_BLUE}; }}
a.qm-tile.primary:hover {{ border-bottom-color: {SMITH_BLUE}; }}
a.qm-tile .badge {{ align-self: flex-start; font-size: 10.5px; font-weight: 900; letter-spacing: .1em; background: {SMITH_BLUE}; color: {GOLD};
  padding: 2px 7px; border-radius: 3px; }}

.qm-chip {{ display: inline-block; padding: 2px 10px; border-radius: 3px; font-size: 12px; font-weight: 900; margin: 2px 4px 2px 0; text-transform: uppercase; letter-spacing: .04em; }}
.qm-pos {{ background: #E5F1E5; color: #1F5E22; }} .qm-neg {{ background: #F8E1E6; color: #8C0A25; }} .qm-neu {{ background: #ECEFF4; color: #4A5468; }}
.qm-company {{ background: #fff; border: 1px solid {LINE}; border-top: 3px solid {SMITH_BLUE}; border-radius: 6px; padding: 14px 18px; margin: 12px 0 4px; }}
.qm-company h3 {{ margin: 0; font-size: 26px; padding: 0; }}
.qm-company .meta {{ color: {MUTED}; font-size: 13.5px; margin-top: 4px; }}
.qm-empty {{ text-align: center; border: 2px dashed #C7CFDB; border-radius: 8px; padding: 34px 20px; margin: 6px 0 18px; background: {TINT}; }}
.qm-empty .qm-ic {{ width: 44px; height: 44px; color: {SMITH_BLUE}; }}
.qm-empty h3 {{ margin: 6px 0 4px; padding: 0; font-size: 21px; }}
.qm-empty p {{ color: {MUTED}; margin: 0; }}

/* sidebar panel */
[data-testid="stSidebar"] {{ background: {TINT}; border-right: 1px solid {LINE}; }}
[data-testid="stSidebarUserContent"] {{ padding-top: 0.5rem; }}
[data-testid="stSidebarHeader"] {{ height: 3.2rem; }}
.qm-side-brand {{ background: {SMITH_BLUE}; color: #fff; font-weight: 900; letter-spacing: .12em; font-size: 13px; padding: 12px 14px;
  border-radius: 6px; border-bottom: 3px solid {GOLD}; margin-bottom: 14px; }}
.qm-side-brand span {{ display: block; color: {GOLD}; letter-spacing: .04em; font-size: 15.5px; margin-top: 2px; }}
.qm-side-h {{ color: {SMITH_BLUE}; font-weight: 900; font-size: 13px; letter-spacing: .08em; text-transform: uppercase;
  border-bottom: 2px solid {GOLD}; padding-bottom: 4px; margin: 16px 0 8px; display: inline-block; }}
.qm-side-foot {{ color: {MUTED}; font-size: 12.3px; border-top: 1px solid {LINE}; padding-top: 10px; margin-top: 16px; line-height: 1.45; }}
[data-testid="stFileUploaderDropzone"] {{ background: #fff; border: 1.5px dashed #9FB0C8; border-radius: 6px; }}

/* top takeaways */
.qm-takes {{ background: {SMITH_BLUE}; border-radius: 8px; padding: 16px 18px 18px; margin: 4px 0 18px; border-bottom: 4px solid {GOLD}; }}
.qm-takes-h {{ color: {GOLD}; font-weight: 900; font-size: 12.5px; letter-spacing: .14em; text-transform: uppercase; margin-bottom: 12px; }}
.qm-takes-g {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
.qm-take {{ background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.14); border-radius: 6px; padding: 12px 14px; position: relative; }}
.qm-take .n {{ position: absolute; top: 10px; right: 12px; color: {GOLD}; font-weight: 900; font-size: 22px; opacity: .9; }}
.qm-take h5 {{ color: #fff; margin: 0 28px 6px 0; font-size: 15.5px; font-weight: 900; padding: 0; }}
.qm-take p {{ color: #D5DDEB; margin: 0; font-size: 13.6px; line-height: 1.5; }}
.qm-take b {{ color: #fff; }}
.qm-team {{ border: 1px solid {LINE}; border-top: 4px solid {GOLD}; border-radius: 8px; padding: 16px 20px; margin: 0 0 18px; background: #fff; }}
.qm-team-h {{ display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
.qm-team-h .k {{ color: {RED}; font-weight: 900; font-size: 12px; letter-spacing: .12em; }}
.qm-team-h .t {{ color: {SMITH_BLUE}; font-weight: 900; font-size: 21px; margin-top: 2px; }}
.qm-team-h .s {{ color: {MUTED}; font-size: 13.5px; }}
.qm-team-g {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
@media (max-width: 700px) {{ .qm-team-g {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.qm-member {{ display: flex; align-items: center; gap: 10px; background: {TINT}; border-radius: 6px; padding: 9px 12px; }}
.qm-member .av {{ width: 36px; height: 36px; border-radius: 50%; background: {SMITH_BLUE}; color: {GOLD}; font-weight: 900; font-size: 13px;
  display: flex; align-items: center; justify-content: center; flex: none; letter-spacing: .03em; }}
.qm-member .nm {{ color: {INK}; font-weight: 700; font-size: 14.5px; }}
.qm-verdict {{ background: #fff; border: 1px solid {LINE}; border-left: 6px solid {SMITH_BLUE}; border-radius: 0 8px 8px 0; padding: 14px 18px; margin: 10px 0; }}
.qm-verdict .lbl {{ color: {RED}; font-weight: 900; font-size: 11.5px; letter-spacing: .12em; }}
.qm-verdict h4 {{ margin: 3px 0 8px; color: {SMITH_BLUE}; font-size: 20px; font-weight: 900; padding: 0; }}
.qm-verdict p {{ color: {INK}; font-size: 14.5px; line-height: 1.55; margin: 0 0 6px; }}
.qm-verdict p.small {{ color: {MUTED}; font-size: 12.5px; margin-top: 8px; }}
.qm-limits {{ background: #FFF8E6; border: 1px solid #F3DFA6; border-radius: 8px; padding: 14px 18px; margin: 10px 0; }}
.qm-limits h4 {{ margin: 0 0 6px; color: {SMITH_BLUE}; font-size: 16px; font-weight: 900; padding: 0; }}
.qm-limits p, .qm-limits li {{ color: {INK}; font-size: 14px; line-height: 1.55; }}
.qm-limits ul {{ margin: 4px 0 8px 18px; padding: 0; }}
.qm-limits p.disc {{ border-top: 1px solid #F3DFA6; padding-top: 8px; margin-top: 8px; font-weight: 700; color: {SMITH_BLUE}; }}
.qm-foot {{ color: {MUTED}; font-size: 12.5px; border-top: 1px solid {LINE}; margin-top: 40px; padding-top: 12px; }}
div[data-testid="stExpander"] details {{ background: #fff; border-radius: 6px; border: 1px solid {LINE}; }}
div[data-testid="stExpander"] summary p {{ font-weight: 700; color: {SMITH_BLUE}; }}
[data-testid="stMetricValue"] {{ color: {SMITH_BLUE}; }}
</style>
"""


def setup():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text):
    return html.escape(str(text))


def term(word, label=None):
    tip = GLOSSARY.get(word, '')
    return f'<span class="qm-term" tabindex="0" data-tip="{esc(tip)}">{esc(label or word)}</span>'


def hero(kicker, title, subtitle_html):
    st.markdown(f'<div class="qm-hero"><p class="qm-kicker">{esc(kicker)}</p><h1>{esc(title)}</h1>'
                f'<p class="qm-sub">{subtitle_html}</p></div>', unsafe_allow_html=True)


def section(num, title, intro_html=''):
    st.markdown(f'<div class="qm-section"><span class="qm-num">{esc(num)}</span><h2>{esc(title)}</h2>'
                f'<p>{intro_html}</p></div>', unsafe_allow_html=True)


def card(title, body_html, tag=None):
    tag_html = f'<span class="qm-tag">{esc(tag)}</span><br>' if tag else ''
    st.markdown(f'<div class="qm-card">{tag_html}<h4>{esc(title)}</h4><p>{body_html}</p></div>', unsafe_allow_html=True)


def kpi(label_html, value, note_html='', color=AZURE):
    st.markdown(f'<div class="qm-kpi" style="border-top-color:{color}"><div class="lbl">{label_html}</div>'
                f'<div class="val">{esc(value)}</div><div class="note">{note_html}</div></div>', unsafe_allow_html=True)


def note(body_html):
    st.markdown(f'<div class="qm-note">{body_html}</div>', unsafe_allow_html=True)


def warn(body_html):
    st.markdown(f'<div class="qm-warn">{body_html}</div>', unsafe_allow_html=True)


def coverage_banner(bench, calibrated, counts):
    covered = ' and '.join(calibrated) if len(calibrated) <= 2 else ', '.join(calibrated[:-1]) + ' and ' + calibrated[-1]
    detail = ', '.join(f'{counts[s]} {s.lower()}' for s in calibrated)
    st.markdown(
        f'<div class="qm-banner"><b>Works with earnings calls from any sector.</b> The {term("Benchmark", "benchmark")} is currently '
        f'{term("Calibrated", "calibrated")} on <b>{esc(covered)}</b> calls ({esc(detail)}), so comparisons for those sectors are the most '
        f'reliable. Calls from other sectors are scored the same way but compared with all {len(bench)} benchmark calls, and should be read '
        f'with care. <b>Next step:</b> extend the benchmark and the sector dictionaries to more sectors.</div>', unsafe_allow_html=True)


ICONS = {
    'arrow_forward': 'M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z',
    'upload_file': 'M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm4 18H6V4h7v5h5v11zM8 15.01l1.41 1.41L11 14.84V19h2v-4.16l1.59 1.59L16 15.01 12.01 11z',
    'leaderboard': 'M7.5 21H2V9h5.5v12zm7.25-18h-5.5v18h5.5V3zM22 11h-5.5v10H22V11z',
    'show_chart': 'M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z',
    'description': 'M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
    'menu_book': 'M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z',
}


def icon(name, cls='qm-ic'):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="{ICONS[name]}"/></svg>'


def tiles(items):
    """items: list of (url_path, icon, title, description); the first is highlighted."""
    html_ = '<div class="qm-tiles">'
    for i, (url, ic, title, desc) in enumerate(items):
        badge = '<span class="badge">LIVE DEMO</span>' if i == 0 else ''
        html_ += (f'<a class="qm-tile{" primary" if i == 0 else ""}" href="{url}" target="_self">{badge}'
                  f'{icon(ic)}<span class="t">{esc(title)}</span>'
                  f'<span class="d">{esc(desc)}</span>{icon("arrow_forward", "qm-ic go")}</a>')
    st.markdown(html_ + '</div>', unsafe_allow_html=True)


TEAM = [('Tanushi', 'Khanna'), ('Hannah', 'Kwan'), ('Joanna', 'McFarlane'), ('Shalini', 'Prakash'), ('Rushi', 'Ranade'), ('Jordan', 'Sherwood')]


def team():
    cards = ''.join(f'<div class="qm-member"><span class="av">{esc(f[0] + l[0])}</span><span class="nm">{esc(f)} {esc(l)}</span></div>' for f, l in TEAM)
    st.markdown(f'<div class="qm-team"><div class="qm-team-h"><div><div class="k">GROUP 9 · QUANTA-MENTALS</div>'
                f'<div class="t">MMA 823: Analytics for Financial Markets</div></div>'
                f'<div class="s">Smith School of Business, Queen\'s University</div></div><div class="qm-team-g">{cards}</div></div>',
                unsafe_allow_html=True)


REFERENCES = [
    ('Bernard, V. L., &amp; Thomas, J. K. (1989). Post-earnings-announcement drift: Delayed price response or risk premium? '
     '<i>Journal of Accounting Research</i>, 27, 1–36.', 'https://doi.org/10.2307/2491062'),
    ('Brown, S. J., &amp; Warner, J. B. (1985). Using daily stock returns: The case of event studies. '
     '<i>Journal of Financial Economics</i>, 14(1), 3–31.', 'https://doi.org/10.1016/0304-405X(85)90042-X'),
    ('Hutto, C., &amp; Gilbert, E. (2014). VADER: A parsimonious rule-based model for sentiment analysis of social media text. '
     '<i>Proceedings of the International AAAI Conference on Web and Social Media</i>, 8(1), 216–225.', 'https://doi.org/10.1609/icwsm.v8i1.14550'),
    ('Loughran, T., &amp; McDonald, B. (2011). When is a liability not a liability? Textual analysis, dictionaries, and 10-Ks. '
     '<i>Journal of Finance</i>, 66(1), 35–65.', 'https://doi.org/10.1111/j.1540-6261.2010.01625.x'),
    ('Loughran-McDonald Master Dictionary with Sentiment Word Lists. Notre Dame Software Repository for Accounting and Finance.',
     'https://sraf.nd.edu/loughranmcdonald-master-dictionary/'),
    ('MacKinlay, A. C. (1997). Event studies in economics and finance. <i>Journal of Economic Literature</i>, 35(1), 13–39.',
     'https://www.jstor.org/stable/2729691'),
    ('TextBlob: Simplified text processing (software documentation).', 'https://textblob.readthedocs.io'),
    ('Yahoo Finance, historical prices, accessed through yfinance (Aroussi, R.), open-source Python library.', 'https://github.com/ranaroussi/yfinance'),
]


FINBERT = ('Araci, D. (2019). FinBERT: Financial sentiment analysis with pre-trained language models. arXiv:1908.10063.',
           'https://doi.org/10.48550/arXiv.1908.10063')


def references(extra=()):
    refs = sorted(list(REFERENCES) + list(extra), key=lambda r: r[0])
    items = ''.join(f'<li>{t} <a href="{u}" target="_blank">{u}</a></li>' for t, u in refs)
    st.markdown(f'<div class="qm-section"><span class="qm-num">REFERENCES</span><h2>Sources and references</h2>'
                f'<p>Methods and data used on this page. All links were checked by the team.</p></div>'
                f'<ol style="font-size:13.5px;color:{INK};line-height:1.6;padding-left:20px">{items}</ol>', unsafe_allow_html=True)


def footer():
    st.markdown('<div class="qm-foot">Quanta-Mentals · Group 9 · MMA 823: Analytics for Financial Markets · Smith School of Business, Queen\'s University. '
                'Student research project, not financial advice. Transcripts are not stored or published; only derived scores are used.</div>',
                unsafe_allow_html=True)


def signal_chip(signal):
    cls = {'Positive': 'qm-pos', 'Negative': 'qm-neg'}.get(signal, 'qm-neu')
    return f'<span class="qm-chip {cls}">{esc(signal)}</span>'


@alt.theme.register('quanta', enable=True)
def quanta_theme():
    font = 'Lato, Helvetica Neue, Arial, sans-serif'
    return alt.theme.ThemeConfig({
        'config': {
            'background': 'white',
            'font': font,
            'view': {'stroke': None},
            'axis': {'labelColor': MUTED, 'titleColor': MUTED, 'gridColor': '#E9EDF3', 'domainColor': LINE, 'tickColor': LINE,
                     'labelFontSize': 12, 'titleFontSize': 12.5, 'titleFontWeight': 'normal'},
            'legend': {'labelColor': INK, 'titleColor': MUTED, 'labelFontSize': 12.5, 'orient': 'bottom', 'title': None},
            'title': {'color': SMITH_BLUE, 'fontSize': 15, 'anchor': 'start', 'fontWeight': 'bold'},
            'range': {'category': SECTOR_PALETTE},
            'axisX': {'grid': False},
        }
    })
