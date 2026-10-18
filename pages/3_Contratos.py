"""Contratos: filtros, alertas, cadastro, edição, cancelamento e escopo do agente (Req 3, 4, 5)."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from auth.authentication import render_user_sidebar, require_auth
from services import client_service, contract_service, scope_service
from services.alert_service import alert_badge, days_remaining, get_alert_level
from utils.converters import to_date, to_decimal
from utils.formatters import format_currency, format_date
from utils.ui import handle_result, load_or_stop, setup_page, show_flash
from utils.validators import CONTRACT_STATUSES

setup_page("Contratos", "📄")
sb = require_auth()
render_user_sidebar()

st.title("📄 Contratos")
show_flash()


def money_input(container, label: str, value, key: str, min_value: float = 0.0):
    amount = to_decimal(value)
    return container.number_input(
        label,
        min_value=min_value,
        max_value=999_999_999.99,
        value=float(amount) if amount is not None else None,
        step=100.0,
        format="%.2f",
        key=key,
    )


@st.dialog("Cancelar contrato")
def confirm_cancellation(contract: dict) -> None:
    st.write(f"Confirma o cancelamento de **{contract['titulo_projeto']}**?")
    st.caption("O status passa a Cancelado; o registro é mantido no histórico.")
    confirm, back = st.columns(2)
    if confirm.button("Cancelar contrato", type="primary", width="stretch"):
        if handle_result(contract_service.cancel_contract(sb, contract["id"]), "Contrato cancelado."):
            st.rerun()
    if back.button("Voltar", width="stretch"):
        st.rerun()


clients = load_or_stop(client_service.list_clients, sb, "")
clients_by_id = {c["id"]: c for c in clients}
active_clients = [c for c in clients if c["ativo"]]

# --- Novo contrato ---------------------------------------------------------------------

with st.expander("➕ Novo contrato"):
    if not active_clients:
        st.info("Cadastre um cliente ativo antes de criar contratos.")
    else:
        with st.form("novo_contrato", clear_on_submit=False):  # preserva os dados em caso de erro (Req 3.4)
            c1, c2 = st.columns(2)
            cliente_id = c1.selectbox(
                "Cliente *",
                [c["id"] for c in active_clients],
                format_func=lambda cid: clients_by_id[cid]["razao_social"],
                index=None,
                placeholder="Selecione um cliente ativo",
            )
            titulo = c2.text_input("Título do projeto *", max_chars=255)
            status = c1.selectbox("Status *", CONTRACT_STATUSES, index=1)
            c3, c4 = c2.columns(2)
            data_inicio = c3.date_input("Início *", value=date.today(), format="DD/MM/YYYY")
            data_fim = c4.date_input("Término *", value=date.today() + timedelta(days=365), format="DD/MM/YYYY")
            valor_mensal = money_input(c1, "Valor mensal (MRR) R$ *", None, "novo_valor", min_value=0.0)
            setup_fee = money_input(c2, "Setup fee R$", 0, "novo_setup")
            if st.form_submit_button("Cadastrar contrato", type="primary"):
                result = contract_service.create_contract(
                    sb,
                    {
                        "cliente_id": cliente_id,
                        "titulo_projeto": titulo,
                        "status": status,
                        "data_inicio": data_inicio,
                        "data_fim": data_fim,
                        "valor_mensal": valor_mensal,
                        "setup_fee": setup_fee if setup_fee is not None else 0,
                    },
                )
                if handle_result(result, "Contrato cadastrado com sucesso."):
                    st.rerun()

# --- Filtros e listagem -------------------------------------------------------------------

f1, f2 = st.columns(2)
filter_client = f1.selectbox(
    "Cliente",
    [None] + [c["id"] for c in clients],
    format_func=lambda cid: "Todos os clientes" if cid is None else clients_by_id[cid]["razao_social"],
)
filter_status = f2.selectbox("Status", [None, *CONTRACT_STATUSES], format_func=lambda s: s or "Todos os status")

contracts = load_or_stop(contract_service.list_contracts, sb, filter_client)
if filter_status:
    contracts = [c for c in contracts if c["status"] == filter_status]

if not contracts:
    st.info("Nenhum contrato encontrado para os filtros selecionados.")
    st.stop()

today = date.today()
table = pd.DataFrame(
    [
        {
            "Alerta": alert_badge(get_alert_level(c, today), days_remaining(c, today)),
            "Projeto": c["titulo_projeto"],
            "Cliente": (c.get("clientes") or {}).get("razao_social", ""),
            "Status": c["status"],
            "Início": format_date(c["data_inicio"]),
            "Término": format_date(c["data_fim"]),
            "Valor mensal": format_currency(c["valor_mensal"]),
            "Setup fee": format_currency(c["setup_fee"]),
        }
        for c in contracts
    ]
)
event = st.dataframe(
    table,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key=f"tabela_contratos_{filter_client}_{filter_status}",
)
st.caption(f"{len(contracts)} contrato(s). 🟡 16–30 dias · 🟠 8–15 dias · 🔴 até 7 dias · ⛔ vencido. Selecione uma linha para detalhes.")

if not event.selection.rows:
    st.stop()
contract = contracts[event.selection.rows[0]]

# --- Contrato selecionado -------------------------------------------------------------------

st.divider()
st.subheader(contract["titulo_projeto"])
st.caption((contract.get("clientes") or {}).get("razao_social", ""))

tab_details, tab_scope = st.tabs(["Detalhes do contrato", "Escopo do agente"])

with tab_details:
    with st.form(f"editar_contrato_{contract['id']}", clear_on_submit=False):
        c1, c2 = st.columns(2)
        titulo = c1.text_input("Título do projeto *", value=contract["titulo_projeto"], max_chars=255)
        status = c2.selectbox("Status *", CONTRACT_STATUSES, index=CONTRACT_STATUSES.index(contract["status"]))
        c3, c4 = c1.columns(2)
        data_inicio = c3.date_input("Início *", value=to_date(contract["data_inicio"]), format="DD/MM/YYYY")
        data_fim = c4.date_input("Término *", value=to_date(contract["data_fim"]), format="DD/MM/YYYY")
        valor_mensal = money_input(c2, "Valor mensal (MRR) R$ *", contract["valor_mensal"], f"valor_{contract['id']}")
        setup_fee = money_input(c2, "Setup fee R$", contract["setup_fee"], f"setup_{contract['id']}")
        if st.form_submit_button("Salvar alterações", type="primary"):
            result = contract_service.update_contract(
                sb,
                contract["id"],
                {
                    "titulo_projeto": titulo,
                    "status": status,
                    "data_inicio": data_inicio,
                    "data_fim": data_fim,
                    "valor_mensal": valor_mensal,
                    "setup_fee": setup_fee if setup_fee is not None else 0,
                },
            )
            if handle_result(result, "Contrato atualizado."):
                st.rerun()

    if contract["status"] != "Cancelado" and st.button("Cancelar contrato", icon="🚫"):
        confirm_cancellation(contract)

with tab_scope:
    scope = load_or_stop(scope_service.get_scope_by_contract, sb, contract["id"])
    if scope is None:
        st.info("Este contrato ainda não possui escopo técnico cadastrado.")

    with st.form(f"escopo_{contract['id']}", clear_on_submit=False):
        tipo = st.text_input("Tipo de arquitetura *", value=(scope or {}).get("tipo_arquitetura", ""), placeholder="Ex.: RAG com agente orquestrador")
        c1, c2 = st.columns(2)
        limite = c1.number_input(
            "Limite de requisições *", min_value=None, value=(scope or {}).get("limite_requisicoes"), step=1,
            help="Inteiro entre 1 e 10.000.000",
        )
        horas_atual = to_decimal((scope or {}).get("horas_manutencao"))
        horas = c2.number_input(
            "Horas de manutenção *", value=float(horas_atual) if horas_atual is not None else None, step=0.5, format="%.1f",
            help="Entre 0,5 e 8.760",
        )
        modelos = st.text_area(
            "Modelos permitidos * (um por linha)",
            value="\n".join((scope or {}).get("modelos_permitidos") or []),
            placeholder="claude-opus-5-5\nclaude-sonnet-5-5",
        )
        if st.form_submit_button("Salvar escopo" if scope else "Cadastrar escopo", type="primary"):
            payload = {
                "tipo_arquitetura": tipo,
                "limite_requisicoes": int(limite) if limite is not None and float(limite).is_integer() else limite,
                "horas_manutencao": horas,
                "modelos_permitidos": scope_service.parse_models(modelos),
            }
            if scope:
                result = scope_service.update_scope(sb, scope["id"], payload)
            else:
                result = scope_service.create_scope(sb, {**payload, "contrato_id": contract["id"]})
            if handle_result(result, "Escopo salvo."):
                st.rerun()
