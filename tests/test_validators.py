from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from utils.validators import (
    CONTRACT_STATUSES,
    normalize_cnpj,
    validate_cnpj,
    validate_contract_dates,
    validate_email,
    validate_horas_manutencao,
    validate_limite_requisicoes,
    validate_modelos_permitidos,
    validate_password_format,
    validate_setup_fee,
    validate_status,
    validate_text_length,
    validate_valor_mensal,
)


# --- CNPJ ---------------------------------------------------------------------

@pytest.mark.parametrize("cnpj", ["12345678000190", "00000000000000"])
def test_cnpj_valido(cnpj):
    assert validate_cnpj(cnpj) == (True, None)


@pytest.mark.parametrize(
    "cnpj", ["1234567800019", "123456780001900", "1234567800019A", "12.345.678/0001-90", "", None, 12345678000190]
)
def test_cnpj_invalido(cnpj):
    ok, err = validate_cnpj(cnpj)
    assert ok is False and err


def test_normalize_cnpj_remove_pontuacao():
    assert normalize_cnpj("12.345.678/0001-90") == "12345678000190"
    assert normalize_cnpj(None) == ""


# --- E-mail e senha -----------------------------------------------------------

@pytest.mark.parametrize("email", ["ana@empresa.com", "a.b+c@sub.dominio.com.br"])
def test_email_valido(email):
    assert validate_email(email) == (True, None)


@pytest.mark.parametrize("email", ["anaempresa.com", "ana@", "ana@empresa", "@empresa.com", "ana @x.com", "", None])
def test_email_invalido(email):
    assert validate_email(email)[0] is False


def test_senha_minimo_8_caracteres():
    assert validate_password_format("1234567")[0] is False
    assert validate_password_format("12345678") == (True, None)
    assert validate_password_format(None)[0] is False


# --- Textos ---------------------------------------------------------------------

def test_texto_obrigatorio_e_tamanho():
    assert validate_text_length("", "Razão social", 255)[0] is False
    assert validate_text_length("   ", "Razão social", 255)[0] is False
    assert validate_text_length("x" * 255, "Razão social", 255) == (True, None)
    assert validate_text_length("x" * 256, "Razão social", 255)[0] is False
    assert validate_text_length("", "Telefone", 20, required=False) == (True, None)
    assert validate_text_length(None, "Telefone", 20, required=False) == (True, None)


# --- Datas ----------------------------------------------------------------------

def test_datas_iguais_invalidas():
    d = date(2026, 1, 1)
    ok, err = validate_contract_dates(d, d)
    assert ok is False and "posterior" in err


def test_data_fim_posterior_valida():
    assert validate_contract_dates(date(2026, 1, 1), date(2026, 1, 2)) == (True, None)


def test_datas_em_string_iso():
    assert validate_contract_dates("2026-01-01", "2026-12-31") == (True, None)


def test_datas_ausentes():
    assert validate_contract_dates(None, date(2026, 1, 1))[0] is False


# --- Valores monetários --------------------------------------------------------

@pytest.mark.parametrize("valor", [0, "0", Decimal("0.00"), Decimal("-1"), Decimal("1000000000.00"), "abc", None, True, Decimal("1.234")])
def test_valor_mensal_invalido(valor):
    assert validate_valor_mensal(valor)[0] is False


@pytest.mark.parametrize("valor", [Decimal("0.01"), "0.01", "0,01", 999999999.99, Decimal("999999999.99"), 1500, Decimal("10.50")])
def test_valor_mensal_valido(valor):
    assert validate_valor_mensal(valor) == (True, None)


def test_setup_fee_aceita_zero():
    assert validate_setup_fee(0) == (True, None)
    assert validate_setup_fee(Decimal("999999999.99")) == (True, None)


@pytest.mark.parametrize("valor", [Decimal("-0.01"), Decimal("1000000000"), Decimal("0.001"), "x", None])
def test_setup_fee_invalido(valor):
    assert validate_setup_fee(valor)[0] is False


# --- Status ---------------------------------------------------------------------

def test_status():
    for status in CONTRACT_STATUSES:
        assert validate_status(status) == (True, None)
    assert validate_status("Ativa")[0] is False
    assert validate_status(None)[0] is False


# --- Escopo -----------------------------------------------------------------------

@pytest.mark.parametrize("limite,esperado", [(0, False), (1, True), (10_000_000, True), (10_000_001, False), (1.5, False), (True, False), ("10", False)])
def test_limite_requisicoes(limite, esperado):
    assert validate_limite_requisicoes(limite)[0] is esperado


@pytest.mark.parametrize(
    "horas,esperado",
    [(0.4, False), (0.5, True), (8760, True), (8760.1, False), (Decimal("10.5"), True), (Decimal("10.55"), False), (None, False)],
)
def test_horas_manutencao(horas, esperado):
    assert validate_horas_manutencao(horas)[0] is esperado


def test_modelos_permitidos():
    assert validate_modelos_permitidos(["claude-opus-5-5"]) == (True, None)
    assert validate_modelos_permitidos(["m"] * 50) == (True, None)
    assert validate_modelos_permitidos([])[0] is False
    assert validate_modelos_permitidos(["m"] * 51)[0] is False
    assert validate_modelos_permitidos(["x" * 101])[0] is False
    assert validate_modelos_permitidos(["x" * 100]) == (True, None)
    assert validate_modelos_permitidos([1])[0] is False
    assert validate_modelos_permitidos(["  "])[0] is False
    assert validate_modelos_permitidos("claude")[0] is False


# --- Property-based -----------------------------------------------------------------

# Feature: crm-agentes-ia, Property 1: Validação de datas de contrato
@given(
    data_inicio=st.dates(min_value=date(1900, 1, 1), max_value=date(2100, 1, 1)),
    delta=st.integers(min_value=-3650, max_value=3650),
)
@settings(max_examples=100)
def test_property_1_validacao_datas(data_inicio, delta):
    data_fim = data_inicio + timedelta(days=delta)
    ok, err = validate_contract_dates(data_inicio, data_fim)
    if delta <= 0:
        assert ok is False and err is not None
    else:
        assert ok is True and err is None


# Feature: crm-agentes-ia, Property 8: Validação de limites numéricos do escopo
@given(limite=st.integers(min_value=-10, max_value=10_000_010))
@settings(max_examples=100)
def test_property_8_limite_requisicoes(limite):
    ok, _ = validate_limite_requisicoes(limite)
    assert ok == (1 <= limite <= 10_000_000)


# Feature: crm-agentes-ia, Property 8: Validação de limites numéricos do escopo
@given(horas=st.decimals(min_value="-10", max_value="9000", places=1))
@settings(max_examples=100)
def test_property_8_horas_manutencao(horas):
    ok, _ = validate_horas_manutencao(horas)
    assert ok == (Decimal("0.5") <= horas <= Decimal("8760"))


# Feature: crm-agentes-ia, Property 10: Valor monetário com duas casas decimais
@given(valor=st.decimals(min_value="0.01", max_value="999999999.99", places=2))
@settings(max_examples=100)
def test_property_10_valor_duas_casas(valor):
    assert validate_valor_mensal(valor) == (True, None)
    assert validate_valor_mensal(str(valor)) == (True, None)
    assert validate_setup_fee(valor) == (True, None)


# Feature: crm-agentes-ia, Property 10: Valor monetário com duas casas decimais
@given(valor=st.decimals(min_value="0.001", max_value="999999.999", places=3))
@settings(max_examples=100)
def test_property_10_rejeita_mais_de_duas_casas(valor):
    ok, _ = validate_valor_mensal(valor)
    assert ok == (valor == valor.quantize(Decimal("0.01")))
