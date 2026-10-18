from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from services.dashboard_service import (
    EXPIRATION_BUCKETS,
    calculate_mrr,
    count_by_status,
    expiration_distribution,
)

HOJE = date(2026, 10, 18)
STATUSES = ["Ativo", "Em Implantação", "Renovação Pendente", "Cancelado"]


def test_mrr_lista_vazia():
    assert calculate_mrr([]) == Decimal("0")


def test_mrr_apenas_cancelados():
    assert calculate_mrr([{"status": "Cancelado", "valor_mensal": "100.00"}]) == Decimal("0")


def test_mrr_soma_apenas_ativos_com_valores_do_postgrest():
    contratos = [
        {"status": "Ativo", "valor_mensal": "1500.50"},  # string (NUMERIC via PostgREST)
        {"status": "Ativo", "valor_mensal": 99.99},      # float
        {"status": "Ativo", "valor_mensal": 10},         # int
        {"status": "Em Implantação", "valor_mensal": "1000.00"},
        {"status": "Renovação Pendente", "valor_mensal": "1000.00"},
    ]
    assert calculate_mrr(contratos) == Decimal("1610.49")


def test_count_by_status_sempre_quatro_chaves():
    assert count_by_status([]) == dict.fromkeys(STATUSES, 0)
    contratos = [{"status": s} for s in ["Ativo", "Ativo", "Cancelado", "Desconhecido"]]
    assert count_by_status(contratos) == {"Ativo": 2, "Em Implantação": 0, "Renovação Pendente": 0, "Cancelado": 1}
    assert list(count_by_status([])) == STATUSES


def test_expiration_distribution_bordas_e_cancelados():
    deltas = [-3, 0, 1, 7, 8, 15, 16, 30, 31, 400]
    contratos = [{"status": "Ativo", "data_fim": HOJE + timedelta(days=d)} for d in deltas]
    contratos.append({"status": "Cancelado", "data_fim": HOJE})
    contratos.append({"status": "Em Implantação", "data_fim": (HOJE + timedelta(days=5)).isoformat()})
    assert expiration_distribution(contratos, HOJE) == {
        "Vencidos": 2,
        "1-7 dias": 3,
        "8-15 dias": 2,
        "16-30 dias": 2,
        "> 30 dias": 2,
    }
    assert list(expiration_distribution([], HOJE)) == list(EXPIRATION_BUCKETS)


# Feature: crm-agentes-ia, Property 4: MRR é soma apenas de contratos ativos
@given(
    contracts=st.lists(
        st.fixed_dictionaries(
            {
                "status": st.sampled_from(STATUSES),
                "valor_mensal": st.decimals(min_value="0.01", max_value="999999999.99", places=2),
            }
        ),
        max_size=50,
    )
)
@settings(max_examples=100)
def test_property_4_mrr_soma_apenas_ativos(contracts):
    expected = sum((c["valor_mensal"] for c in contracts if c["status"] == "Ativo"), Decimal("0"))
    assert calculate_mrr(contracts) == expected
    as_strings = [{**c, "valor_mensal": str(c["valor_mensal"])} for c in contracts]
    assert calculate_mrr(as_strings) == expected
