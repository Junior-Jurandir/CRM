from datetime import date, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from utils.formatters import format_cnpj, format_currency, format_date


def test_format_currency():
    assert format_currency(Decimal("0")) == "R$ 0,00"
    assert format_currency(Decimal("1234.56")) == "R$ 1.234,56"
    assert format_currency(Decimal("1234567.8")) == "R$ 1.234.567,80"
    assert format_currency("999999999.99") == "R$ 999.999.999,99"
    assert format_currency(15) == "R$ 15,00"
    assert format_currency(None) == "R$ 0,00"
    assert format_currency(Decimal("-10")) == "-R$ 10,00"


def test_format_date():
    assert format_date(date(2026, 10, 18)) == "18/10/2026"
    assert format_date("2026-01-05") == "05/01/2026"
    assert format_date(datetime(2026, 1, 5, 10, 30)) == "05/01/2026"
    assert format_date(None) == ""
    assert format_date("invalida") == ""


def test_format_cnpj():
    assert format_cnpj("12345678000190") == "12.345.678/0001-90"
    assert format_cnpj("123") == "123"
    assert format_cnpj(None) == ""


# Feature: crm-agentes-ia, Property 10: Valor monetário com duas casas decimais
@given(valor=st.decimals(min_value="0", max_value="999999999.99", places=2))
@settings(max_examples=100)
def test_property_10_formatacao_preserva_valor(valor):
    texto = format_currency(valor)
    numero = texto.removeprefix("R$ ").replace(".", "").replace(",", ".")
    assert Decimal(numero) == valor
    assert len(numero.split(".")[1]) == 2
