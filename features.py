"""Optional app sections. Switch one off by setting it to False; nothing else needs to change."""

# Light-hearted bonus at the end of "Analyze a call": an imagined take in the spirit of the MMA 823 lectures.
SHOW_PROF_MEHMET = True

# Link to the classic (v1) app, shown on the story page. Paste the v1 Streamlit URL here; None hides the link.
V1_APP_URL = None

# Window shown as "before the call" in the price reaction (trading days). 5 = the week before; 21 = the month before (original design).
PRE_WINDOW_DAYS = 5

# "First reaction vs. readjustment": splits the reaction into the overnight gap and the first trading session after the call.
# Needs data/gap_study.csv (made by .github/workflows/gap-study.yml). False hides it everywhere; nothing else needs to change.
SHOW_GAP_STUDY = True


def pre_window_label():
    """'month before' or 'N days before', following PRE_WINDOW_DAYS."""
    return 'month before' if PRE_WINDOW_DAYS >= 20 else f'{PRE_WINDOW_DAYS} trading days before'

# QR code on the "Analyze a call" page so people can open the app on their phone. False hides it.
SHOW_QR = True
# The address the QR code opens. None = the address the page is being viewed at. Paste the public link here to be safe, e.g.
# 'https://your-app.streamlit.app/analyze'
APP_URL = None

# Benchmark explorer layout. True = team-feedback layout (sectors first, method comparison, change bars, Q&A marker,
# stacked over-time charts). False = the original page (views/explorer_classic.py).
EXPLORER_V2 = True

# "Tone vs. the company's usual": each call compared with the same company's EARLIER calls (no look-ahead).
# Shown on the story page (chapter 5), in Story mode and as a row in the Market reaction strategy table. False hides it.
SHOW_TONE_SURPRISE = True

# Scanned PDFs uploaded on the Analyze page are read with text recognition (OCR, needs packages.txt).
# Set to False to show the "no readable text" message instead.
OCR_UPLOADS = False   # off for the demo: scans show a quick message instead of slowing the app
