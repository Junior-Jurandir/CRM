"""Configurações: perfil do usuário e cadastro de membros (somente Admin) (Req 9.3–9.5, 11)."""

import streamlit as st

from auth.authentication import (
    ROLE_ADMIN,
    ROLE_LABELS,
    ROLE_MEMBER,
    create_team_member,
    get_current_user,
    is_admin,
    render_user_sidebar,
    require_auth,
    update_profile,
)
from utils.ui import flash, setup_page, show_flash

setup_page("Configurações", "⚙️", layout="centered")
require_auth()
render_user_sidebar()

st.title("⚙️ Configurações")
show_flash()

user = get_current_user() or {}

st.subheader("Meu perfil")
st.caption(f"Perfil de acesso: **{ROLE_LABELS.get(user.get('role'), 'Membro')}**")
with st.form("perfil", clear_on_submit=False):
    nome = st.text_input("Nome *", value=user.get("nome", ""), max_chars=150)
    email = st.text_input("E-mail *", value=user.get("email", ""))
    if st.form_submit_button("Salvar perfil", type="primary"):
        ok, error, warning = update_profile(nome, email)
        if error:
            st.error(error)
        else:
            flash("success", "Perfil atualizado.")
            if warning:
                flash("info", warning)
            st.rerun()

st.divider()
st.subheader("Novo membro da equipe")

if not is_admin(user):
    st.info("O cadastro de novos membros é restrito a administradores.")
    st.stop()

st.caption("A credencial é criada com uma senha temporária. Nenhum e-mail de convite é enviado.")
with st.form("novo_membro", clear_on_submit=False):
    novo_nome = st.text_input("Nome *", max_chars=150)
    novo_email = st.text_input("E-mail *")
    novo_perfil = st.selectbox("Perfil", [ROLE_MEMBER, ROLE_ADMIN], format_func=ROLE_LABELS.get)
    submitted = st.form_submit_button("Cadastrar membro", type="primary")

if submitted:
    password, error = create_team_member(novo_nome, novo_email, novo_perfil)
    if error:
        st.error(error)
    else:
        # Exibida uma única vez: não é guardada em session_state (Req 9.4).
        st.success(f"Membro **{novo_email.strip()}** cadastrado como {ROLE_LABELS[novo_perfil]}.")
        st.warning("Copie a senha temporária abaixo e repasse ao novo membro. Ela não será exibida novamente.")
        st.code(password, language=None)
