"""Text recognition (OCR) for scanned transcript PDFs uploaded on the Analyze page.

A scanned PDF holds pictures of pages, so there are no words to score. When the server has
tesseract and poppler (installed from packages.txt), the pages are read with OCR and the
Bloomberg layout is tidied so the normal reader can split speakers. Results are kept in memory
by file content, so a second upload of the same file is instant. To switch this off, set
OCR_UPLOADS = False in features.py.
"""
import glob
import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from pypdf import PdfReader

MAX_PAGES = 60


def available():
    return bool(shutil.which('tesseract') and shutil.which('pdftoppm'))


def is_scanned(name, data):
    if not name.lower().endswith('.pdf'):
        return False
    try:
        pages = PdfReader(io.BytesIO(data)).pages
        text = ''.join((p.extract_text() or '') for p in pages[:3])
    except Exception:
        return False
    return len(text.strip()) < 300


def page_count(data):
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return 0


def fix(text):
    """Tidy OCR of Bloomberg transcripts: speaker tags and participant names."""
    lines = text.split('\n')
    names, inlist = [], False
    for l in lines:
        s = l.strip()
        if s in ('Company Participants', 'Other Participants'):
            inlist = True; continue
        if s == 'Presentation':
            inlist = False
        if inlist and s:
            s = re.sub(r'^[¢e«•*°©@\-]+\s*', '', s)
            if s: names.append(s.split(',')[0].strip())
    canon = {re.sub(r'\W', '', n).lower(): n for n in names}
    out = []
    for l in lines:
        s = l.rstrip()
        s = re.sub(r'\{\s*B[\|Il1!]\s*[O0]\s+', '{BIO ', s)
        s = re.sub(r'<\s*G\s*[O0]\s*>\s*\}', '<GO>}', s)
        m = re.match(r'^\s*(?:([QA])\s*-\s*)?(.+?)\s*(\{BIO \d+ <GO>\})\s*$', s)
        if m:
            name = canon.get(re.sub(r'\W', '', m.group(2)).lower(), m.group(2).strip())
            s = (f'{m.group(1)} - ' if m.group(1) else '') + f'{name} {m.group(3)}'
        elif re.match(r'^[¢e«•*°©@]\s+\S', s) and len(s) < 90:
            s = '• ' + s[2:].strip()
        out.append(s)
    return '\n'.join(out)


@st.cache_resource
def _shared():
    # finished results by file hash, and a limit of two OCR jobs at once so a class of users does not overload the server
    return {'done': {}, 'gate': threading.Semaphore(2)}


def _page(png):
    env = dict(os.environ, OMP_THREAD_LIMIT='1')
    return subprocess.run(['tesseract', png, '-'], capture_output=True, text=True, env=env).stdout


def to_text(data, progress=None):
    """OCR every page; progress(done, total) is called as pages finish. Returns the tidied text."""
    key = hashlib.sha256(data).hexdigest()
    shared = _shared()
    if key in shared['done']:
        return shared['done'][key]
    with shared['gate']:
        if key in shared['done']:
            return shared['done'][key]
        with tempfile.TemporaryDirectory() as d:
            pdf = os.path.join(d, 'in.pdf')
            open(pdf, 'wb').write(data)
            subprocess.run(['pdftoppm', '-r', '200', '-l', str(MAX_PAGES), '-png', pdf, os.path.join(d, 'p')], check=True)
            pages = sorted(glob.glob(os.path.join(d, 'p-*.png')), key=lambda p: int(re.findall(r'(\d+)\.png$', p)[0]))
            texts, done = [None] * len(pages), 0
            with ThreadPoolExecutor(max(1, min(4, os.cpu_count() or 1))) as ex:
                futs = {ex.submit(_page, p): i for i, p in enumerate(pages)}
                from concurrent.futures import as_completed
                for f in as_completed(futs):
                    texts[futs[f]] = f.result()
                    done += 1
                    if progress:
                        progress(done, len(pages))
        text = fix('\n'.join(texts))
        shared['done'][key] = text
        return text
