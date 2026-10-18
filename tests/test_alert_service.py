from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from services.alert_service import (
    AlertLevel,
    alert_badge,
    days_remaining,
    get_alert_level,
    get_expiring_contracts,
)

HOJE = date(2026, 10, 18)


def contrato(delta: int, status: str = "Ativo") -> dict:
    return {"status": status, "data_fim": HOJE + timedelta(days=delta)}


@pytest.mark.parametrize(
    "delta,nivel",
    [
        (-10, AlertLevel.EXPIRED),
        (0, AlertLevel.EXPIRED),
        (1, AlertLevel.CRITICAL),
        (7, AlertLevel.CRITICAL),
        (8, AlertLevel.URGENT),
        (15, AlertLevel.URGENT),
        (16, AlertLevel.ATTENTION),
        (30, AlertLevel.ATTENTION),
        (31, AlertLevel.NONE),
    ],
)
@pytest.mark.parametrize("status", ["Ativo", "Renovação Pendente"])
def test_niveis_por_faixa(delta, nivel, status):
    assert get_alert_level(contrato(delta, status), HOJE) == nivel


@pytest.mark.parametrize("status", ["Cancelado", "Em Implantação"])
def test_status_nao_elegiveis_nao_alertam(status):
    assert get_alert_level(contrato(1, status), HOJE) == AlertLevel.NONE
    assert get_alert_level(contrato(-5, status), HOJE) == AlertLevel.NONE


def test_data_em_string_iso():
    assert get_alert_level({"status": "Ativo", "data_fim": "2026-10-25"}, HOJE) == AlertLevel.CRITICAL
    assert days_remaining({"data_fim": "2026-10-25"}, HOJE) == 7


def test_data_ausente():
    assert get_alert_level({"status": "Ativo"}, HOJE) == AlertLevel.NONE


def test_usa_data_do_servidor_quando_sem_referencia():
    assert get_alert_level({"status": "Ativo", "data_fim": date.today()}) == AlertLevel.EXPIRED


def test_get_expiring_contracts_filtra_e_ordena():
    contratos = [contrato(20, "Ativo"), contrato(3, "Renovação Pendente"), contrato(2, "Cancelado"), contrato(60), contrato(-1)]
    resultado = get_expiring_contracts(contratos, HOJE)
    assert [c["days_remaining"] for c in resultado] == [-1, 3, 20]
    assert [c["alert_level"] for c in resultado] == [AlertLevel.EXPIRED, AlertLevel.CRITICAL, AlertLevel.ATTENTION]
    assert "alert_level" not in contratos[0]  # não altera a entrada


def test_badges_distintos_com_texto():
    badges = {
        alert_badge(AlertLevel.ATTENTION, 20),
        alert_badge(AlertLevel.URGENT, 10),
        alert_badge(AlertLevel.CRITICAL, 1),
        alert_badge(AlertLevel.EXPIRED, -2),
    }
    assert len({b.split()[0] for b in badges}) == 4  # ícones distintos
    assert alert_badge(AlertLevel.CRITICAL, 1) == "🔴 Crítico · 1 dia"
    assert alert_badge(AlertLevel.URGENT, 10) == "🟠 Urgente · 10 dias"
    assert alert_badge(AlertLevel.EXPIRED, 0) == "⛔ Vencido"
    assert alert_badge(AlertLevel.NONE, 90) == ""


def esperado(days: int) -> AlertLevel:
    if days <= 0:
        return AlertLevel.EXPIRED
    if days <= 7:
        return AlertLevel.CRITICAL
    if days <= 15:
        return AlertLevel.URGENT
    if days <= 30:
        return AlertLevel.ATTENTION
    return AlertLevel.NONE


# Feature: crm-agentes-ia, Property 2: Nível de alerta é função determinística e correta da data
@given(data_fim=st.dates(), ref=st.dates(), status=st.sampled_from(["Ativo", "Renovação Pendente"]))
@settings(max_examples=100)
def test_property_2_alerta_deterministico_e_correto(data_fim, ref, status):
    c = {"data_fim": data_fim, "status": status}
    nivel = get_alert_level(c, ref)
    assert nivel == get_alert_level(c, ref)
    assert nivel == esperado((data_fim - ref).days)


# Feature: crm-agentes-ia, Property 3: Contratos não elegíveis não geram alertas
@given(data_fim=st.dates(), ref=st.dates(), status=st.sampled_from(["Cancelado", "Em Implantação"]))
@settings(max_examples=100)
def test_property_3_nao_elegiveis_sem_alerta(data_fim, ref, status):
    assert get_alert_level({"data_fim": data_fim, "status": status}, ref) == AlertLevel.NONE
