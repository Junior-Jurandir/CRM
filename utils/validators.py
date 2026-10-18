"""Validações de domínio. Todas retornam (válido, mensagem_de_erro)."""

import re
from decimal import Decimal

from utils.converters import to_date, to_decimal

ValidationResult = tuple[bool, str | None]

OK: ValidationResult = (True, None)

CONTRACT_STATUSES = ("Ativo", "Em Implantação", "Renovação Pendente", "Cancelado")

_CNPJ_RE = re.compile(r"\d{14}")
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

_CENT = Decimal("0.01")
_TENTH = Decimal("0.1")
_MAX_MONEY = Decimal("999999999.99")

MSG_CNPJ = "CNPJ inválido. Informe 14 dígitos numéricos."
MSG_EMAIL = "E-mail inválido. Informe um endereço no formato nome@dominio.com."
MSG_PASSWORD = "A senha deve ter no mínimo 8 caracteres."
MSG_DATES = "A data de término deve ser posterior à data de início."
MSG_DATES_MISSING = "Informe as datas de início e de término do contrato."
MSG_VALOR_MENSAL = "Valor mensal inválido. Informe um valor entre R$ 0,01 e R$ 999.999.999,99."
MSG_SETUP_FEE = "Setup fee inválido. Informe um valor entre R$ 0,00 e R$ 999.999.999,99."
MSG_STATUS = "Status inválido. Valores aceitos: " + ", ".join(CONTRACT_STATUSES) + "."
MSG_LIMITE = "Limite de requisições inválido. Informe um número inteiro entre 1 e 10.000.000."
MSG_HORAS = (
    "Horas de manutenção inválidas. Informe um valor entre 0,5 e 8.760, "
    "com no máximo uma casa decimal."
)
MSG_MODELOS = (
    "Informe ao menos um modelo permitido "
    "(máximo de 50 modelos, cada um com até 100 caracteres)."
)


def normalize_cnpj(cnpj: str | None) -> str:
    """Remove pontuação: '12.345.678/0001-90' → '12345678000190'."""
    return re.sub(r"\D", "", cnpj or "")


def validate_cnpj(cnpj) -> ValidationResult:
    if isinstance(cnpj, str) and _CNPJ_RE.fullmatch(cnpj):
        return OK
    return False, MSG_CNPJ


def validate_email(email) -> ValidationResult:
    if isinstance(email, str) and len(email) <= 255 and _EMAIL_RE.fullmatch(email.strip()):
        return OK
    return False, MSG_EMAIL


def validate_password_format(password) -> ValidationResult:
    if isinstance(password, str) and len(password) >= 8:
        return OK
    return False, MSG_PASSWORD


def validate_text_length(value, label: str, max_len: int, required: bool = True) -> ValidationResult:
    text = value.strip() if isinstance(value, str) else ""
    if value is not None and not isinstance(value, str):
        return False, f"{label} inválido."
    if required and not text:
        return False, f"{label} é obrigatório."
    if len(text) > max_len:
        return False, f"{label} deve ter no máximo {max_len} caracteres."
    return OK


def validate_contract_dates(data_inicio, data_fim) -> ValidationResult:
    inicio, fim = to_date(data_inicio), to_date(data_fim)
    if inicio is None or fim is None:
        return False, MSG_DATES_MISSING
    if fim <= inicio:
        return False, MSG_DATES
    return OK


def _has_at_most(value: Decimal, quantum: Decimal) -> bool:
    return value == value.quantize(quantum)


def _validate_money(valor, minimum: Decimal, message: str) -> ValidationResult:
    amount = to_decimal(valor)
    if amount is None or not _has_at_most(amount, _CENT):
        return False, message
    if not (minimum <= amount <= _MAX_MONEY):
        return False, message
    return OK


def validate_valor_mensal(valor) -> ValidationResult:
    return _validate_money(valor, _CENT, MSG_VALOR_MENSAL)


def validate_setup_fee(valor) -> ValidationResult:
    return _validate_money(valor, Decimal("0"), MSG_SETUP_FEE)


def validate_status(status) -> ValidationResult:
    if status in CONTRACT_STATUSES:
        return OK
    return False, MSG_STATUS


def validate_limite_requisicoes(limite) -> ValidationResult:
    if isinstance(limite, bool) or not isinstance(limite, int):
        return False, MSG_LIMITE
    if not (1 <= limite <= 10_000_000):
        return False, MSG_LIMITE
    return OK


def validate_horas_manutencao(horas) -> ValidationResult:
    value = to_decimal(horas)
    if value is None or not _has_at_most(value, _TENTH):
        return False, MSG_HORAS
    if not (Decimal("0.5") <= value <= Decimal("8760")):
        return False, MSG_HORAS
    return OK


def validate_modelos_permitidos(modelos) -> ValidationResult:
    if not isinstance(modelos, list) or not (1 <= len(modelos) <= 50):
        return False, MSG_MODELOS
    for item in modelos:
        if not isinstance(item, str) or not item.strip() or len(item) > 100:
            return False, MSG_MODELOS
    return OK
