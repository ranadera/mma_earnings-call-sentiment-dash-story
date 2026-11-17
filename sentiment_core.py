"""Shared transcript parsing and sentiment scoring, used by the Streamlit app (app.py).

The logic is the same as in sentiment_analysis.ipynb, so a transcript scored here gets
the same numbers as in the notebook.
"""
import os
import re
import unicodedata

import numpy as np
import pandas as pd
from pypdf import PdfReader
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

NEGATORS = {'not', 'no', 'never', 'none', 'neither', 'nor', 'without', "isn't", "wasn't", "aren't",
            "don't", "doesn't", "didn't", "won't", "can't", "couldn't", "shouldn't", "haven't"}
BOILERPLATE = r'forward-looking|safe harbor|differ materially|undue reliance'
QA_MARKERS = ['Questions And Answers', 'QUESTIONS AND ANSWERS', 'Question-and-Answer Session',
              'Question and Answer Session', 'Q&A Session']
SPEAKER_RE = re.compile(r"^(Q - |A - )?([A-Z][\w.'\- ]+?)\s*(\{BIO \d+ <GO>\})?$")

vader = SentimentIntensityAnalyzer()

# Company names as they appear in transcripts (speaker titles, operator welcome, disclaimers) -> Yahoo Finance ticker.
# Used only when the transcript itself does not state the ticker (e.g. transcripts posted on a company's investor-relations site).
COMPANY_TICKERS = {
    'JPMorgan Chase': 'JPM', 'JPMorganChase': 'JPM', 'JPMorgan': 'JPM', 'Bank of America': 'BAC', 'Citigroup': 'C', 'Citi': 'C', 'Citizens': 'CFG',
    'Wells Fargo': 'WFC', 'U.S. Bancorp': 'USB', 'US Bancorp': 'USB', 'PNC Financial': 'PNC', 'PNC': 'PNC', 'Goldman Sachs': 'GS',
    'Morgan Stanley': 'MS', 'Truist': 'TFC', 'Capital One': 'COF', 'Citizens Financial': 'CFG', 'M&T Bank': 'MTB',
    'Fifth Third': 'FITB', 'KeyCorp': 'KEY', 'Regions Financial': 'RF', 'Huntington Bancshares': 'HBAN', 'Zions': 'ZION',
    'Comerica': 'CMA', 'SVB Financial': 'SIVB', 'Silicon Valley Bank': 'SIVB', 'Western Alliance': 'WAL',
    'Royal Bank of Canada': 'RY', 'Toronto-Dominion': 'TD', 'TD Bank': 'TD', 'Bank of Nova Scotia': 'BNS', 'Scotiabank': 'BNS',
    'Bank of Montreal': 'BMO', 'BMO Financial': 'BMO', 'CIBC': 'CM', 'Canadian Imperial Bank': 'CM', 'Rogers Communications': 'RCI.B',
    'Apple': 'AAPL', 'Microsoft': 'MSFT', 'Amazon': 'AMZN', 'Alphabet': 'GOOGL', 'Google': 'GOOGL', 'Meta Platforms': 'META',
    'NVIDIA': 'NVDA', 'Advanced Micro Devices': 'AMD', 'AMD': 'AMD', 'Broadcom': 'AVGO', 'Oracle': 'ORCL', 'Qualcomm': 'QCOM',
    'KLA': 'KLAC', 'Sandisk': 'SNDK', 'Western Digital': 'WDC', 'CoreWeave': 'CRWV', 'Palo Alto Networks': 'PANW',
    'Monolithic Power': 'MPWR', 'Intel': 'INTC', 'Tesla': 'TSLA', 'Netflix': 'NFLX', 'Salesforce': 'CRM',
}
MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'


def _norm(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def ticker_from_company(name):
    """Ticker for a company name, matching the longest known alias inside it; '' if none matches."""
    n, spaced = _norm(name), ' ' + re.sub(r'[^a-z0-9]+', ' ', name.lower()) + ' '
    # long aliases may match inside a run-together name (JPMorganChase); short ones only as whole words (AMD, not Amdocs)
    hits = [(len(_norm(a)), t) for a, t in COMPANY_TICKERS.items()
            if (len(_norm(a)) >= 6 and _norm(a) in n) or (' ' + re.sub(r'[^a-z0-9]+', ' ', a.lower()).strip() + ' ') in spaced]
    return max(hits)[1] if hits else ''


SEPARATOR_RE = re.compile(r'^\.{10,}$')
TITLE_RE = re.compile(r'^(?P<title>[^,]{2,90}),\s*(?P<firm>.+?)(?:\s+(?P<qa>[QA]))?$')


CS_HEADINGS = {'MANAGEMENTDISCUSSIONSECTION': 'MANAGEMENT DISCUSSION SECTION', 'QUESTIONANDANSWERSECTION': 'QUESTION AND ANSWER SECTION'}


def _cs_heading(l):
    return CS_HEADINGS.get(l.replace(' ', ''), l)


def is_callstreet(lines):
    return any(l.replace(' ', '') in CS_HEADINGS for l in lines)


def parse_callstreet(lines):
    """Transcripts in the CallStreet/FactSet layout used on many investor-relations sites: a dotted rule, the speaker's
    name on one line, 'Title, Company' on the next (with Q or A in the Q&A), then the text. Operator lines are inline."""
    lines = [_cs_heading(l) for l in lines]
    out, section, speaker, role, buf = [], 'presentation', None, None, []
    after_rule = False

    def flush():
        if speaker and buf:
            out.append([section, speaker, role, ' '.join(buf)])

    i = 0
    while i < len(lines):
        l = lines[i]
        if l == 'Disclaimer':
            break
        if SEPARATOR_RE.match(l):
            after_rule = True
            i += 1
            continue
        if after_rule and l.isdigit():          # page number between the rule and the next speaker
            i += 1
            continue
        if l in ('MANAGEMENT DISCUSSION SECTION', 'QUESTION AND ANSWER SECTION'):
            flush(); buf, speaker = [], None
            section = 'qa' if l.startswith('QUESTION') else 'presentation'
        elif l.startswith('Operator:'):
            flush(); speaker, role, buf = 'Operator', 'operator', [l.split(':', 1)[1].strip()]
        elif (after_rule or (i > 0 and lines[i - 1].isdigit())) and i + 1 < len(lines) and TITLE_RE.match(lines[i + 1]) \
                and 1 <= len(l.split()) <= 6 and not l.endswith(('.', '?', ':')) and not any(ch.isdigit() for ch in l):
            m = TITLE_RE.match(lines[i + 1])
            new_role = 'analyst' if m.group('qa') == 'Q' or m.group('title').strip().startswith('Analyst') else 'management'
            if not (l == speaker and new_role == role):  # a page break repeats the header: keep one turn
                flush(); buf = []
            speaker, role = l, new_role
            i += 2
            after_rule = False
            continue
        elif speaker:
            buf.append(l)
        after_rule = False
        i += 1
    flush()
    return out


def callstreet_meta(lines):
    firms = [TITLE_RE.match(lines[i + 1]).group('firm') for i in range(len(lines) - 1)
             if TITLE_RE.match(lines[i + 1]) and not lines[i + 1].startswith('Analyst')
             and (TITLE_RE.match(lines[i + 1]).group('qa') in (None, 'A'))]
    company = max(set(firms), key=firms.count) if firms else ''
    return company


def lm_path(path='LM_MasterDictionary.csv'):
    """Local copy of the Loughran-McDonald dictionary if present, otherwise the copy shipped with pysentiment2."""
    if path and os.path.exists(path):
        return path
    import importlib.util
    spec = importlib.util.find_spec('pysentiment2')
    if spec is None:
        raise FileNotFoundError('LM_MasterDictionary.csv not found and pysentiment2 is not installed (pip install pysentiment2).')
    return os.path.join(list(spec.submodule_search_locations)[0], 'static', 'LM.csv')


def load_sector_map(path='data/sector_map.csv'):
    if not os.path.exists(path):
        return {}
    m = pd.read_csv(path, dtype=str).dropna()
    return dict(zip(m['ticker'].str.strip().str.upper(), m['sector'].str.strip()))


def load_lm(path='LM_MasterDictionary.csv'):
    lm = pd.read_csv(lm_path(path))
    return {
        'pos': set(lm.loc[lm['Positive'] > 0, 'Word'].str.lower()),
        'neg': set(lm.loc[lm['Negative'] > 0, 'Word'].str.lower()) - {'question', 'questions', 'questioned', 'questioning'},
        'unc': set(lm.loc[lm['Uncertainty'] > 0, 'Word'].str.lower()),
    }


def read_text(uploaded_name, data):
    if uploaded_name.lower().endswith('.pdf'):
        import io
        raw = '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(data)).pages)
    else:
        raw = data.decode('utf-8', errors='ignore')
    return unicodedata.normalize('NFKC', raw)


def get_meta(raw):
    ticker = re.search(r'\((\w+) US Equity\)', raw)
    date = re.search(r'FINAL TRANSCRIPT\s+(\d{4}-\d{2}-\d{2})', raw)
    company = re.search(r'\n(.+?) \(\w+ US Equity\)', raw)
    meta = {'ticker': ticker.group(1) if ticker else '',
            'call_date': date.group(1) if date else '',
            'company': re.sub(r'\s+', ' ', company.group(1)).replace('Amaz on', 'Amazon').strip() if company else ''}
    first = raw.strip().split('\n')[0] if raw.strip() else ''
    m = re.match(r'(\d{2})(\d{2})(\d{2})([A-Z]+)', first)
    if not meta['ticker'] and m:
        meta['ticker'] = m.group(4)
        meta['call_date'] = '20' + m.group(3) + '-' + m.group(1) + '-' + m.group(2)
    if not meta['ticker']:
        # No ticker in the text (e.g. investor-relations transcripts): find the company name, then look up its ticker.
        lines = [l.strip() for l in raw.split('\n') if l.strip()]
        names = []
        if is_callstreet(lines):
            names.append(callstreet_meta(lines))
        w = re.search(r"[Ww]elcome to (?:the )?(.{2,60}?)(?:'s|’s)?\s+(?:First|Second|Third|Fourth|Q[1-4]|Fiscal|Full[- ]Year|\d{4})", raw[:6000])
        if w:
            names.append(w.group(1))
        for name in names:
            t = ticker_from_company(name) if name else ''
            if t:
                meta['ticker'] = t
                meta['company'] = meta['company'] or name.strip()
                break
    if not meta['call_date']:
        d = re.search(rf'({MONTHS})\s+(\d{{1,2}}),\s+(\d{{4}})', raw[:3000])
        if d:
            meta['call_date'] = pd.to_datetime(' '.join(d.groups())).strftime('%Y-%m-%d')
    return meta


def clean_lines(raw):
    lines = [l.strip() for l in raw.split('\n')]
    return [l for l in lines if l
            and 'COPYRIGHT' not in l
            and not re.match(r'^P\s*r\s*i\s*n\s*t\s*e\s*d', l)
            and not l.startswith('FINAL TRANSCRIPT')
            and 'US Equity)' not in l
            and not l.startswith('This document is being provided')
            and l != 'for redistribution.'
            and l != 'Bloomberg Automated Summary'
            and not l.startswith('Bloomberg ®')
            and not l.startswith('TOTAL PAGES')]


def parse_bloomberg(lines):
    out, analysts = [], set()
    if 'Other Participants' in lines:
        i = lines.index('Other Participants') + 1
        while i < len(lines) and lines[i] not in ('Presentation', 'Questions And Answers'):
            analysts.add(lines[i].split(',')[0].strip())
            i += 1
    section, speaker, role, buf = 'presentation', None, None, []
    for l in lines:
        m = SPEAKER_RE.match(l)
        is_tag = l == 'Operator' or (m is not None and (m.group(1) or m.group(3)))
        if l == 'Questions And Answers' or is_tag:
            if speaker:
                out.append([section, speaker, role, ' '.join(buf)])
            buf = []
            if l == 'Questions And Answers':
                section, speaker = 'qa', None
            elif l == 'Operator':
                speaker, role = 'Operator', 'operator'
            else:
                speaker = m.group(2).strip()
                role = 'analyst' if (m.group(1) == 'Q - ' or speaker in analysts) else 'management'
        elif speaker:
            buf.append(l)
    if speaker:
        out.append([section, speaker, role, ' '.join(buf)])
    return out


def parse_inline(lines):
    out = []
    i_corp, i_part, i_pres = lines.index('CORPORATE SPEAKERS:'), lines.index('PARTICIPANTS:'), lines.index('PRESENTATION:')
    management = set(lines[i_corp + 1:i_part:2])
    analysts = set(lines[i_part + 1:i_pres:2])
    names = '|'.join(re.escape(n) for n in management | analysts | {'Operator'})
    tag_re = re.compile(r'^(' + names + r'):\s*(.*)$')
    section, speaker, role, buf = 'presentation', None, None, []
    for l in lines[i_pres + 1:]:
        m = tag_re.match(l)
        if m:
            if speaker:
                out.append([section, speaker, role, ' '.join(buf)])
            speaker = m.group(1)
            role = 'operator' if speaker == 'Operator' else 'analyst' if speaker in analysts else 'management'
            if role == 'analyst':
                section = 'qa'
            buf = [m.group(2)]
        elif speaker:
            buf.append(l)
    if speaker:
        out.append([section, speaker, role, ' '.join(buf)])
    return out


def parse_plain(lines):
    text = '\n'.join(lines)
    for marker in QA_MARKERS:
        if marker in text:
            pres, qa = text.split(marker, 1)
            return [['presentation', 'Management', 'management', pres.replace('\n', ' ')],
                    ['qa', 'Q&A (speakers not identified)', 'management', qa.replace('\n', ' ')]]
    return [['presentation', 'Full text', 'management', text.replace('\n', ' ')]]


LABEL_RE = re.compile(r"^(?P<name>OPERATOR|[A-Z][A-Z.'\-]+(?: [A-Z][A-Z.'\-]+){1,4}):\s*(?P<text>.*)$")
QUESTION_RE = re.compile(r'(first|next|following|last) question|question (comes|will come|is from|today)', re.I)
END_RE = re.compile(r'^(Certain statements in this (transcript|document)|(Forward[- ]Looking Statements|FORWARD[- ]LOOKING STATEMENTS|Disclaimer|DISCLAIMER|IMPORTANT DISCLOSURES)\s*$)')


def is_caps_labels(lines):
    labels = [m.group('name') for l in lines for m in [LABEL_RE.match(l)] if m]
    return 'OPERATOR' in labels and len(set(labels)) >= 3 and len(labels) >= 8


def parse_caps_labels(lines):
    """Company-published transcripts where each turn starts 'JANE FRASER: ...' (e.g. Citi). Management is taken from the
    header ('Host' / 'Speakers' lists) and anyone who speaks before the first analyst; page headers repeated on every page are dropped."""
    from collections import Counter
    counts = Counter(lines)
    body = [l for l in lines if not (counts[l] >= 3 and len(l) < 100) and not l.lower().startswith('copyright')]
    first = next((i for i, l in enumerate(body) if LABEL_RE.match(l)), 0)
    mgmt = {re.split(r',', l)[0].strip().upper() for l in body[:first] if ',' in l and len(l.split(',')[0].split()) in (2, 3, 4)}
    out, section, speaker, role, buf, qa_started = [], 'presentation', None, None, [], False

    def flush():
        if speaker and buf:
            out.append([section, speaker, role, ' '.join(buf)])

    for l in body[first:]:
        if END_RE.match(l):
            break
        m = LABEL_RE.match(l)
        if m:
            flush()
            name = m.group('name').strip()
            if name == 'OPERATOR':
                speaker, role = 'Operator', 'operator'
            else:
                asked = bool(out and out[-1][1] == 'Operator' and QUESTION_RE.search(out[-1][3]))
                is_mgmt = name in mgmt or (not qa_started and not asked)
                if not is_mgmt and not qa_started:
                    qa_started, section = True, 'qa'
                    if out and out[-1][1] == 'Operator':
                        out[-1][0] = 'qa'
                if is_mgmt and name not in mgmt and not qa_started:
                    mgmt.add(name)
                speaker, role = name.title(), 'management' if (name in mgmt) else 'analyst'
            buf = [m.group('text')]
        elif speaker:
            buf.append(l)
    flush()
    return out


def parse(raw):
    lines = clean_lines(raw)
    if 'CORPORATE SPEAKERS:' in lines and 'PRESENTATION:' in lines:
        header = set(lines[2:4])
        lines = [l for l in lines if l not in header]
        fmt, rows = 'LSEG (inline speakers)', parse_inline(lines)
    elif 'Questions And Answers' in lines and any('<GO>}' in l for l in lines):
        fmt, rows = 'Bloomberg', parse_bloomberg(lines)
    elif is_callstreet(lines) and parse_callstreet(lines):
        fmt, rows = 'Investor-relations (CallStreet layout)', parse_callstreet(lines)
    elif is_caps_labels(lines) and parse_caps_labels(lines):
        fmt, rows = 'Investor-relations (named speakers)', parse_caps_labels(lines)
    else:
        fmt, rows = 'Plain text (speakers not identified)', parse_plain(lines)
    turns = pd.DataFrame(rows, columns=['section', 'speaker', 'role', 'text'])
    turns['text'] = turns['text'].str.split('This transcript may not be 100 percent accurate').str[0]
    turns['turn'] = range(len(turns))
    return fmt, turns


def split_sentences(text):
    return [s for s in re.split(r'(?<=[.!?])\s+', text) if len(s.split()) > 2]


def drop_boilerplate(text):
    return ' '.join(s for s in split_sentences(text) if not re.search(BOILERPLATE, s, re.I))


def load_sector_lexicon(path='data/sector_lexicon.csv'):
    """Sector-specific neutral terms: words (or two-word phrases) that the finance dictionary
    counts as positive or negative but are routine jargon in that sector."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=['sector', 'term', 'reason'])
    return pd.read_csv(path)


def neutral_terms(lexicon, sector):
    rows = lexicon[lexicon['sector'].isin(['All', sector])] if sector else lexicon[lexicon['sector'] == 'All']
    words = {t.lower() for t in rows['term'] if ' ' not in t}
    pairs = {tuple(t.lower().split()) for t in rows['term'] if len(t.split()) == 2}
    return {'words': words, 'pairs': pairs}


def lm_counts(text, lm, neutral=None):
    tokens = re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())
    pos = neg = unc = 0
    pos_words, neg_words = [], []
    for i, w in enumerate(tokens):
        if neutral and (w in neutral['words'] or (i > 0 and (tokens[i - 1], w) in neutral['pairs'])):
            continue
        if w in lm['pos']:
            if any(t in NEGATORS for t in tokens[max(0, i - 3):i]):
                neg += 1
                neg_words.append('not ' + w)
            else:
                pos += 1
                pos_words.append(w)
        elif w in lm['neg']:
            neg += 1
            neg_words.append(w)
        if w in lm['unc']:
            unc += 1
    return {'n_words': len(tokens), 'lm_pos': pos, 'lm_neg': neg, 'lm_unc': unc,
            'pos_words': pos_words, 'neg_words': neg_words}


def score_turns(turns, lm, neutral=None):
    turns = turns.copy()
    turns['clean'] = turns['text'].apply(drop_boilerplate)
    turns = turns[(turns['role'] != 'operator') & (turns['clean'].str.split().str.len() > 0)].reset_index(drop=True)
    counts = pd.DataFrame([lm_counts(t, lm) for t in turns['clean']])
    turns = pd.concat([turns, counts], axis=1)
    if neutral is not None:
        adj = pd.DataFrame([lm_counts(t, lm, neutral) for t in turns['clean']])
        turns['adj_pos'], turns['adj_neg'] = adj['lm_pos'], adj['lm_neg']
    sents = turns['clean'].apply(split_sentences)
    turns['n_sent'] = sents.str.len()
    turns['vader'] = sents.apply(lambda s: np.mean([vader.polarity_scores(x)['compound'] for x in s]) if s else 0)
    turns['textblob'] = sents.apply(lambda s: np.mean([TextBlob(x).sentiment.polarity for x in s]) if s else 0)
    turns['part'] = np.where(turns['section'] == 'presentation', 'presentation',
                             np.where(turns['role'] == 'analyst', 'qa_analyst', 'qa_management'))
    return turns


def summarise(g):
    words = g['n_words'].sum()
    if words == 0:
        return {'words': 0, 'lm_tone': np.nan, 'lm_uncertainty': np.nan, 'lm_neg_rate': np.nan, 'vader': np.nan, 'textblob': np.nan}
    w = g['n_sent'].clip(lower=1)
    return {'words': words,
            'lm_tone': (g['lm_pos'].sum() - g['lm_neg'].sum()) / words * 100,
            'lm_uncertainty': g['lm_unc'].sum() / words * 100,
            'lm_neg_rate': g['lm_neg'].sum() / words * 100,
            'vader': np.average(g['vader'], weights=w),
            'textblob': np.average(g['textblob'], weights=w)}


def segments(turns, lm, n=10):
    words, is_qa = [], []
    for _, r in turns.sort_values('turn').iterrows():
        w = r['clean'].split()
        words += w
        is_qa += [r['section'] == 'qa'] * len(w)
    rows = []
    for k, idx in enumerate(np.array_split(np.arange(len(words)), n)):
        c = lm_counts(' '.join(words[i] for i in idx), lm)
        rows.append({'segment': k + 1, 'lm_tone': (c['lm_pos'] - c['lm_neg']) / max(c['n_words'], 1) * 100})
    qa_start = np.argmax(is_qa) / len(words) * n if any(is_qa) else None
    return pd.DataFrame(rows), qa_start


def zscore(value, sample):
    return (value - sample.mean()) / sample.std()


def score_call(turns, benchmark, sector=None):
    """Call-level scores. benchmark is call_sentiment.csv (transcripts only), used to put this call on the same scale."""
    overall = summarise(turns)
    parts = {p: summarise(g) for p, g in turns.groupby('part')}
    pres = parts.get('presentation', {}).get('lm_tone', np.nan)
    qa_m = parts.get('qa_management', {}).get('lm_tone', np.nan)
    ana = parts.get('qa_analyst', {}).get('lm_tone', np.nan)

    z = [zscore(overall['lm_tone'], benchmark['lm_tone']),
         zscore(overall['vader'], benchmark['vader']),
         zscore(overall['textblob'], benchmark['textblob'])]
    composite = float(np.mean(z))
    q1, q2 = benchmark['composite'].quantile([1 / 3, 2 / 3])
    signal = 'Negative' if composite <= q1 + 1e-9 else 'Neutral' if composite <= q2 + 1e-9 else 'Positive'

    peers = benchmark[benchmark['sector'] == sector] if sector else benchmark
    sector_score = float(zscore(composite, peers['composite'])) if len(peers) > 2 else np.nan

    if 'adj_pos' in turns.columns and overall['words']:
        adj_tone = (turns['adj_pos'].sum() - turns['adj_neg'].sum()) / overall['words'] * 100
    else:
        adj_tone = np.nan
    res = {'words': overall['words'], 'lm_tone': overall['lm_tone'], 'lm_tone_sector': adj_tone, 'vader': overall['vader'],
           'textblob': overall['textblob'], 'lm_uncertainty': overall['lm_uncertainty'],
           'composite': composite, 'signal': signal, 'sector_score': sector_score,
           'pres_tone': pres, 'qa_mgmt_tone': qa_m, 'analyst_tone': ana,
           'tone_shift': qa_m - pres, 'conviction_gap': qa_m - ana,
           'analyst_neg_rate': parts.get('qa_analyst', {}).get('lm_neg_rate', np.nan),
           'hedging': parts.get('qa_management', {}).get('lm_uncertainty', np.nan) - parts.get('presentation', {}).get('lm_uncertainty', np.nan)}

    needed = ['conviction_gap', 'tone_shift', 'hedging', 'analyst_neg_rate']
    if all(np.isfinite(res[k]) for k in needed):
        res['conviction_score'] = float((zscore(res['conviction_gap'], benchmark['conviction_gap'])
                                         + zscore(res['tone_shift'], benchmark['tone_shift'])
                                         - zscore(res['hedging'], benchmark['hedging'])
                                         - zscore(res['analyst_neg_rate'], benchmark['analyst_neg_rate'])) / 4)
    else:
        res['conviction_score'] = np.nan
    return res
