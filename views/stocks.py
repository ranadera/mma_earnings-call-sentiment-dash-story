import textwrap

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import data_access as da
import market as mk
import ui
from ui import esc, term

bench = da.benchmark()
sector_map = da.sector_map()

ui.hero('Stock reports', 'One-page profile of each stock',
        'Business, sector, two years of price history against the market (S&amp;P 500, or S&amp;P/TSX 60 for Toronto listings), risk, and the latest valuation ratios, '
        'with the sentiment of each earnings call marked on the price chart. Data is pulled live from Yahoo Finance.')

known = sorted(bench['ticker'].unique())
c1, c2 = st.columns([2, 1])
pick = c1.selectbox('Stock', known + ['Other ticker...'], format_func=lambda t: t if t == 'Other ticker...' else f'{da.SHORT_NAMES.get(t, t)} ({t})')
typed = c2.text_input('Ticker', placeholder='e.g. BAC, RY or RCI.B',
                      help='US tickers as listed (BAC). Toronto listings work as RCI.B, RCI-B.TO or RCI/B; the app finds the Yahoo Finance symbol.').strip().upper() if pick == 'Other ticker...' else pick
if not typed:
    st.stop()
ticker = typed
if pick == 'Other ticker...':
    with st.spinner(f'Looking up {typed}...'):
        ticker = mk.resolve_ticker(typed)
    if not ticker:
        ui.warn(f'No price data found for <b>{esc(typed)}</b> under any of these Yahoo Finance symbols: '
                f'{esc(", ".join(mk.ticker_candidates(typed)))}. Check the symbol on finance.yahoo.com.')
        ui.footer()
        st.stop()
    if ticker != typed:
        st.caption(f'Showing Yahoo Finance symbol {ticker} for "{typed}".')
mkt, mkt_label = mk.benchmark_for(ticker)

with st.spinner(f'Loading {ticker}...'):
    info = mk.company_info(ticker)
    end = pd.Timestamp.today().strftime('%Y-%m-%d')
    start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime('%Y-%m-%d')
    px, source = mk.prices((ticker, mkt), start, end)

if px is None or ticker not in px.columns or px[ticker].dropna().empty:
    ui.warn(f'Price data for <b>{esc(ticker)}</b> could not be loaded. {esc(source or "")} Check the ticker or try again in a minute.')
    ui.footer()
    st.stop()

s = mk.stock_stats(px, ticker, mkt)
cur = info.get('currency') or ('CAD' if ticker.endswith(('.TO', '.V')) else 'USD')
sym = 'C$' if cur == 'CAD' else '$' if cur == 'USD' else cur + ' '
name = info.get('longName') or da.SHORT_NAMES.get(ticker, ticker)
sector = sector_map.get(ticker)
is_bank = sector == 'Bank'
st.markdown(f'<div class="qm-company"><h3>{esc(name)}</h3><div class="meta">'
            + ' · '.join(esc(x) for x in [ticker, info.get('sector'), info.get('industry'), f'Our sector group: {sector}' if sector else None,
                                          f'Close {s["as_of"]:%d %b %Y}: {sym}{s["price"]:,.2f} ({cur})'] if x)
            + '</div></div>', unsafe_allow_html=True)

ui.section('01 · BUSINESS', 'What the company does')
summary = info.get('longBusinessSummary') or 'Business description not available from the data source.'
st.markdown(f'<div class="qm-card"><p style="font-size:15px;color:{ui.INK}">{esc(textwrap.shorten(summary, 1100, placeholder="..."))}</p></div>', unsafe_allow_html=True)

ui.section('02 · VALUATION', 'Latest key ratios', 'Hover over each ratio for what it means. For banks, price-to-book and return on equity are the ratios to watch.')


def fmt(v, f, suffix=''):
    return 'n/a' if v is None or (isinstance(v, float) and not np.isfinite(v)) else format(v, f) + suffix


mcap = info.get('marketCap')
ratios = [('Market cap', fmt(mcap / 1e9 if mcap else None, ',.0f', ' bn')),
          ('P/E ratio', fmt(info.get('trailingPE'), '.1f', 'x')),
          ('Forward P/E', fmt(info.get('forwardPE'), '.1f', 'x')),
          ('P/B ratio', fmt(info.get('priceToBook'), '.2f', 'x')),
          ('EV/EBITDA', 'n/a (bank)' if is_bank else fmt(info.get('enterpriseToEbitda'), '.1f', 'x')),
          ('Dividend yield', fmt(info.get('trailingAnnualDividendYield') * 100 if info.get('trailingAnnualDividendYield') is not None else None, '.2f', '%')),
          ('ROE', fmt(info.get('returnOnEquity') * 100 if info.get('returnOnEquity') is not None else None, '.1f', '%')),
          ('Beta', fmt(s['beta'], '.2f'))]
for row in (ratios[:4], ratios[4:]):
    cols = st.columns(4)
    for col, (label, value) in zip(cols, row):
        with col:
            ui.kpi(term(label), value, color=ui.SKY)
    st.write('')

ui.section('03 · PRICE HISTORY', 'Two years against the market',
           'Both lines start at 100. Dashed lines mark earnings calls in our data set, coloured by their sentiment signal.')
p = px[[ticker, mkt]].dropna()
idx = (p / p.iloc[0] * 100).reset_index().melt(p.index.name or 'index', var_name='series', value_name='value')
idx = idx.rename(columns={idx.columns[0]: 'date'})
mkt_name = f'{mkt_label} ({mkt.replace(".TO", "")})'
idx['series'] = idx['series'].map({ticker: name, mkt: mkt_name})
lines = alt.Chart(idx).mark_line(strokeWidth=2).encode(
    x=alt.X('date:T', title=None), y=alt.Y('value:Q', title='Indexed to 100', scale=alt.Scale(zero=False)),
    color=alt.Color('series:N', scale=alt.Scale(domain=[name, mkt_name], range=[ui.AZURE, '#9AA5B8'])),
    tooltip=['series', alt.Tooltip('date:T', format='%d %b %Y'), alt.Tooltip('value:Q', format='.1f')])
mycalls = bench[(bench['ticker'] == ticker) & (bench['call_date'] >= p.index[0])]
layers = [lines]
if not mycalls.empty:
    layers.append(alt.Chart(mycalls).mark_rule(strokeDash=[5, 4], strokeWidth=2).encode(
        x='call_date:T', color=alt.Color('signal:N', scale=alt.Scale(domain=list(ui.SIGNAL_COLORS), range=list(ui.SIGNAL_COLORS.values())), legend=None),
        tooltip=[alt.Tooltip('call_date:T', title='Earnings call', format='%d %b %Y'), 'signal', alt.Tooltip('lm_tone:Q', format='.2f', title='Tone')]))
st.altair_chart(alt.layer(*layers).resolve_scale(color='independent').properties(height=300), width='stretch')

ui.section('04 · RISK', 'Return and risk over the last 12 months')
r = st.columns(4)
with r[0]:
    ui.kpi('1-year return', f'{s["ret_1y"]:+.1%}', f'{mkt_label}: {s["mkt_1y"]:+.1%}', color=ui.OLIVE if s['ret_1y'] >= s['mkt_1y'] else ui.ROSE)
with r[1]:
    ui.kpi(term('Volatility'), f'{s["vol_1y"]:.1%}', f'Last 30 days: <b>{s["vol_30d"]:.1%}</b>', color=ui.PUMPKIN)
with r[2]:
    ui.kpi(term('Maximum drawdown'), f'{s["max_dd"]:.1%}', 'Largest fall from a peak', color=ui.ROSE)
with r[3]:
    ui.kpi('52-week range', f'{sym}{s["low"]:,.0f} – {sym}{s["high"]:,.0f}', f'Now {sym}{s["price"]:,.2f}', color=ui.SKY)

ui.section('05 · SENTIMENT', 'Earnings call sentiment for this stock')
mine = bench[bench['ticker'] == ticker].sort_values('call_date')
if mine.empty:
    ui.note('This stock is not in the benchmark yet. Upload one of its transcripts on the <b>Analyze a call</b> page to score it.')
else:
    st.dataframe(mine[['call_date', 'signal', 'lm_tone', 'composite', 'tone_shift', 'conviction_score']], hide_index=True, width='stretch',
                 column_config={'call_date': st.column_config.DateColumn('Call date', format='DD MMM YYYY'), 'signal': 'Signal',
                                'lm_tone': st.column_config.NumberColumn('Tone', format='%.2f'),
                                'composite': st.column_config.NumberColumn('Overall score', format='%+.2f'),
                                'tone_shift': st.column_config.NumberColumn('Change into Q&A', format='%+.2f'),
                                'conviction_score': st.column_config.NumberColumn('Conviction', format='%+.2f')})
st.caption(f'Sources: prices ({source}); company data from Yahoo Finance; sentiment from the Quanta-Mentals benchmark. '
           'The project notebook can also pull these figures from Bloomberg.')
ui.footer()
