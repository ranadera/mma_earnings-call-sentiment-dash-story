import streamlit as st

import surprise_view
import ui

ui.hero('Beyond the Beat', 'Do the words matter once you know the numbers?',
        'A fair challenge to any study of tone: maybe a confident CEO just reflects a good quarter. Here we put the two side by side: '
        'the <b>earnings surprise</b> (reported earnings per share against what analysts expected) and <b>how management sounded</b>. '
        'Then we ask which one explains how the stock moved, in the first two days and in the month after.')

res, eps = surprise_view.load()
if res is None:
    ui.warn('<b>The earnings-surprise data is not available yet.</b> It is added by the next data update.')
    ui.footer()
    st.stop()

surprise_view.scatter()
surprise_view.page_section('')
ui.footer()
