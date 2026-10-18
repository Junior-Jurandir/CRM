"""Dashboard: MRR, contagens por status, vencimentos e alertas (Req 5, 6)."""

import pandas as pd
import streamlit as st

from auth.authentication import render_user_sidebar, require_auth
from services import contract_service
from services.alert_service import alert_badge, get_expiring_contracts
from services.cache_utils import clear_all_caches
from services.dashboard_service import calculate_mrr, count_by_status, expiration_distribution
from utils.formatters import format_currency, format_date
from utils.ui import flash, load_or_stop, setup_page, show_flash

setup_page("Dashboard", "📊")
sb = require_auth()
render_user_sidebar()

header, refresh = st.columns([5, 1], vertical_alignment="bottom")
header.title("📊 Dashboard")
if refresh.button("Atualizar dados", width="stretch"):
    if warning := clear_all_caches():
        flash("warning", warning)
    st.rerun()
show_flash()

contracts = load_or_stop(contract_service.list_contracts, sb)
counts = count_by_status(contracts)

col_mrr, col_ativos, col_total = st.columns(3)
col_mrr.metric("MRR total", format_currency(calculate_mrr(contracts)), border=True, help="Soma do valor mensal dos contratos Ativos")
col_ativos.metric("Contratos ativos", counts["Ativo"], border=True)
col_total.metric("Total de contratos", len(contracts), border=True)

st.subheader("Contratos por status")
for column, (status, total) in zip(st.columns(4), counts.items()):
    column.metric(status, total, border=True)

left, right = st.columns([3, 2])

with left:
    st.subheader("Vencimentos")
    distribution = expiration_distribution(contracts)
    chart = pd.DataFrame({"Faixa": list(distribution), "Contratos": list(distribution.values())})
    st.bar_chart(chart, x="Faixa", y="Contratos", sort=False, x_label="Dias até o término", y_label="Contratos")
    st.caption("Considera todos os contratos, exceto os cancelados.")

with right:
    st.subheader("Alertas de vencimento")
    expiring = get_expiring_contracts(contracts)
    if not expiring:
        st.success("Nenhum contrato Ativo ou em Renovação Pendente vence nos próximos 30 dias.")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Alerta": alert_badge(c["alert_level"], c["days_remaining"]),
                        "Contrato": c["titulo_projeto"],
                        "Cliente": (c.get("clientes") or {}).get("razao_social", ""),
                        "Término": format_date(c["data_fim"]),
                    }
                    for c in expiring
                ]
            ),
            hide_index=True,
        )
        st.caption("🟡 16–30 dias · 🟠 8–15 dias · 🔴 até 7 dias · ⛔ vencido")
