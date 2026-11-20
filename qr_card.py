"""QR code card for the Analyze page (switch: features.SHOW_QR). Removable: delete this file and its call site."""
import io

import streamlit as st

import features
import ui


def app_url():
    if features.APP_URL:
        return features.APP_URL
    try:
        url = st.context.url or ''
    except Exception:
        return ''
    return url.replace('/~/+', '').split('?')[0]


def render():
    if not features.SHOW_QR:
        return
    url = app_url()
    if not url.startswith('http'):
        return
    try:
        import segno
    except ImportError:
        return
    buf = io.BytesIO()
    segno.make(url, error='m').save(buf, kind='png', scale=8, border=2, dark=ui.SMITH_BLUE, light='#ffffff')
    with st.container(border=True):
        st.markdown(f'<div style="text-align:center;font-size:.74rem;letter-spacing:.12em;font-weight:700;color:{ui.SMITH_BLUE}">'
                    'TRY IT ON YOUR PHONE</div>', unsafe_allow_html=True)
        st.image(buf.getvalue(), width='stretch')
        st.markdown('<div style="text-align:center;font-size:.86rem;color:#3D4656;line-height:1.45">Scan with your camera, then tap '
                    '<b>Try a sample call</b>.</div>'
                    f'<div style="text-align:center;font-size:.72rem;color:#8A93A3;margin-top:4px;word-break:break-all">{ui.esc(url)}</div>',
                    unsafe_allow_html=True)
