"""Quanta-Mentals Earnings Call Sentiment platform (MMA 823), version 2: the story edition.

Run with:  streamlit run app.py
"""
import streamlit as st

import features

st.set_page_config(page_title='Quanta-Mentals · Earnings Call Sentiment', page_icon=':material/insights:', layout='wide')

import ui

ui.setup()

# Version 2: the executive story comes first; every detailed page from version 1 sits under "Details".
pages = {
    'The story': [st.Page('views/story.py', title='The story', icon=':material/auto_stories:', default=True)],
    'Try it': [st.Page('views/analyze.py', title='Analyze a call', icon=':material/upload_file:')],
    'Details': [
        st.Page('views/home.py', title='Overview', icon=':material/home:'),
        st.Page('views/explorer.py' if features.EXPLORER_V2 else 'views/explorer_classic.py', title='Benchmark explorer',
                icon=':material/leaderboard:', url_path='explorer'),
        st.Page('views/market_reaction.py', title='Market reaction', icon=':material/candlestick_chart:'),
        st.Page('views/stocks.py', title='Stock reports', icon=':material/description:'),
        st.Page('views/method.py', title='Method & decisions', icon=':material/menu_book:'),
    ],
}
st.navigation(pages, position='top').run()
