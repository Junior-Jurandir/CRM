"""Clientes: busca, listagem, cadastro, edição e inativação (Req 2)."""

import pandas as pd
import streamlit as st

from auth.authentication import render_user_sidebar, require_auth
from services import client_service, contract_service
from utils.formatters import format_cnpj, format_date
from utils.ui import handle_result, load_or_stop, setup_page, show_flash

setup_page("Clientes", "🏢")
sb = require_auth()
render_user_sidebar()

st.title("🏢 Clientes")
show_flash()


@st.dialog("Inativar cliente")
def confirm_deactivation(client: dict, open_contracts: int) -> None:
    st.write(f"Confirma a inativação de **{client['razao_social']}**?")
    st.caption("O registro é mantido no histórico e não poderá receber novos contratos.")
    if open_contracts:
        st.warning(f"{open_contracts} contrato(s) Ativo(s) ou Em Implantação serão alterados para **Cancelado**.")
    confirm, back = st.columns(2)
    if confirm.button("Inativar", type="primary", width="stretch"):
        result = client_service.deactivate_client(sb, client["id"])
        if handle_result(result, f"Cliente inativado. {result.data or 0} contrato(s) cancelado(s)."):
            st.rerun()
    if back.button("Voltar", width="stretch"):
        st.rerun()


# --- Novo cliente --------------------------------------------------------------------

with st.expander("➕ Novo cliente"):
    with st.form("novo_cliente", clear_on_submit=False):  # preserva os dados em caso de erro (Req 2.3)
        c1, c2 = st.columns(2)
        razao_social = c1.text_input("Razão social *", max_chars=255)
        cnpj = c2.text_input("CNPJ *", placeholder="00.000.000/0000-00")
        contato_nome = c1.text_input("Nome do contato *", max_chars=150)
        email = c2.text_input("E-mail *")
        telefone = c1.text_input("Telefone", max_chars=20)
        if st.form_submit_button("Cadastrar", type="primary"):
            result = client_service.create_client(
                sb,
                {"razao_social": razao_social, "cnpj": cnpj, "contato_nome": contato_nome, "email": email, "telefone": telefone},
            )
            if handle_result(result, "Cliente cadastrado com sucesso."):
                st.rerun()

# --- Listagem -----------------------------------------------------------------------------

search = st.text_input("Buscar", placeholder="Razão social (parcial) ou CNPJ (exato)", label_visibility="collapsed")
clients = load_or_stop(client_service.list_clients, sb, search.strip())

if not clients:
    st.info("Nenhum cliente encontrado." if search else "Nenhum cliente cadastrado ainda.")
    st.stop()

table = pd.DataFrame(
    [
        {
            "Razão social": c["razao_social"],
            "CNPJ": format_cnpj(c["cnpj"]),
            "Contato": c["contato_nome"],
            "E-mail": c["email"],
            "Telefone": c.get("telefone") or "",
            "Status": "Ativo" if c["ativo"] else "Inativo",
            "Cadastro": format_date(c["created_at"]),
        }
        for c in clients
    ]
)
event = st.dataframe(
    table,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key=f"tabela_clientes_{search}",
)
st.caption(f"{len(clients)} cliente(s). Selecione uma linha para editar ou inativar.")

selected_rows = event.selection.rows
if not selected_rows:
    st.stop()
client = clients[selected_rows[0]]

# --- Detalhes do cliente selecionado ------------------------------------------------------

st.divider()
st.subheader(client["razao_social"])
if not client["ativo"]:
    st.info(f"Cliente **Inativo** desde {format_date(client.get('inativado_em'))}. Novos contratos não são permitidos.")

with st.form(f"editar_cliente_{client['id']}", clear_on_submit=False):
    c1, c2 = st.columns(2)
    razao_social = c1.text_input("Razão social *", value=client["razao_social"], max_chars=255)
    c2.text_input("CNPJ", value=format_cnpj(client["cnpj"]), disabled=True, help="O CNPJ não pode ser alterado.")
    contato_nome = c1.text_input("Nome do contato *", value=client["contato_nome"], max_chars=150)
    email = c2.text_input("E-mail *", value=client["email"])
    telefone = c1.text_input("Telefone", value=client.get("telefone") or "", max_chars=20)
    if st.form_submit_button("Salvar alterações", type="primary"):
        result = client_service.update_client(
            sb,
            client["id"],
            {"razao_social": razao_social, "contato_nome": contato_nome, "email": email, "telefone": telefone},
        )
        if handle_result(result, "Cliente atualizado."):
            st.rerun()

if client["ativo"] and st.button("Inativar cliente", icon="⛔"):
    client_contracts = load_or_stop(contract_service.list_contracts, sb, client["id"])
    open_contracts = sum(1 for c in client_contracts if c["status"] in ("Ativo", "Em Implantação"))
    confirm_deactivation(client, open_contracts)
