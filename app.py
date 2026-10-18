"""Página de Login (ponto de entrada da aplicação)."""

import streamlit as st

from auth.authentication import is_session_valid, login
from utils.ui import setup_page

setup_page("Login", "🤖", layout="centered")

if is_session_valid():
    st.switch_page("pages/1_Dashboard.py")

st.markdown("<div style='height: 8vh'></div>", unsafe_allow_html=True)
st.title("🤖 CRM para Agentes de IA")
st.caption("Acesso restrito à equipe interna.")

with st.form("login", border=True):
    email = st.text_input("E-mail", placeholder="nome@empresa.com.br")
    password = st.text_input("Senha", type="password")
    submitted = st.form_submit_button("Entrar", type="primary", width="stretch")

if submitted:
    with st.spinner("Autenticando..."):
        user, error = login(email, password)
    if error:
        st.error(error)
    else:
        st.switch_page("pages/1_Dashboard.py")
