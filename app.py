"""Quanta-Mentals Earnings Call Sentiment platform (MMA 823), version 2: the story edition.

Run with:  streamlit run app.py
"""
import streamlit as st

import importlib

import features

# Streamlit Cloud can keep an older copy of features.py in memory after an update; reload it so new switches are always seen.
importlib.reload(features)

st.set_page_config(page_title='Quanta-Mentals · Earnings Call Sentiment', page_icon=':material/insights:', layout='wide')

import ui

ui.setup()

# Version 2: the executive story comes first; every detailed page from version 1 sits under "Details".
analyze_page = st.Page('views/analyze.py', title='Analyze a call', icon=':material/upload_file:')


def new_analysis():
    """Menu item: clear the current call and every input, then open a fresh Analyze page."""
    nonce = st.session_state.get('nonce', 0) + 1
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state['nonce'] = nonce
    st.switch_page(analyze_page)


pages = {
    '': [st.Page('views/story.py', title='The story', icon=':material/auto_stories:', default=True),
         *([st.Page('views/beyond_beat.py', title='Beyond the Beat', icon=':material/insights:', url_path='beyond-the-beat')]
           if getattr(features, 'SHOW_SURPRISE_TEST', False) else []),
         analyze_page,
         st.Page(new_analysis, title='New analysis', icon=':material/restart_alt:', url_path='new')],
    'Details': [
        st.Page('views/home.py', title='Overview', icon=':material/home:'),
        st.Page('views/explorer.py' if getattr(features, 'EXPLORER_V2', True) else 'views/explorer_classic.py', title='Benchmark explorer',
                icon=':material/leaderboard:', url_path='explorer'),
        st.Page('views/market_reaction.py', title='Market reaction', icon=':material/candlestick_chart:'),
        st.Page('views/stocks.py', title='Stock reports', icon=':material/description:'),
        st.Page('views/method.py', title='Method & decisions', icon=':material/menu_book:'),
    ],
}
st.navigation(pages, position='top').run()
