"""Escopo do agente: validação, cache de leitura e invalidação após escrita."""

import streamlit as st

import config
from repositories import scope_repo
from services.cache_utils import safe_clear
from services.result import DataLoadError, ServiceResult
from utils.converters import to_decimal
from utils.validators import (
    validate_horas_manutencao,
    validate_limite_requisicoes,
    validate_modelos_permitidos,
    validate_text_length,
)

MSG_CONTRACT_ID_IMMUTABLE = "O campo contrato_id não pode ser alterado."
MSG_SELECT_CONTRACT = "Selecione o contrato do escopo."

_CHECKS = {
    "tipo_arquitetura": lambda v: validate_text_length(v, "Tipo de arquitetura", 5000),
    "limite_requisicoes": validate_limite_requisicoes,
    "horas_manutencao": validate_horas_manutencao,
    "modelos_permitidos": validate_modelos_permitidos,
}


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def get_scope_by_contract(_sb, contract_id: str) -> dict | None:
    scope, err = scope_repo.get_scope_by_contract(_sb, contract_id)
    if err:
        raise DataLoadError(err)
    return scope


def parse_models(text: str) -> list[str]:
    """Converte o texto do formulário (um modelo por linha) em lista, ignorando linhas vazias."""
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _clean(data: dict) -> dict:
    cleaned = dict(data)
    if "tipo_arquitetura" in cleaned:
        cleaned["tipo_arquitetura"] = (cleaned["tipo_arquitetura"] or "").strip()
    if isinstance(cleaned.get("modelos_permitidos"), list):
        cleaned["modelos_permitidos"] = [m.strip() if isinstance(m, str) else m for m in cleaned["modelos_permitidos"]]
    if "horas_manutencao" in cleaned:
        hours = to_decimal(cleaned["horas_manutencao"])
        cleaned["horas_manutencao"] = hours if hours is not None else cleaned["horas_manutencao"]
    return cleaned


def _validate(data: dict, fields) -> str | None:
    for field in fields:
        ok, err = _CHECKS[field](data.get(field))
        if not ok:
            return err
    return None


def create_scope(sb, data: dict) -> ServiceResult:
    cleaned = _clean(data)
    if not cleaned.get("contrato_id"):
        return ServiceResult(error=MSG_SELECT_CONTRACT)
    if err := _validate(cleaned, _CHECKS):
        return ServiceResult(error=err)
    created, err = scope_repo.create_scope(sb, cleaned)
    if err:
        return ServiceResult(error=err)
    return ServiceResult(data=created, warning=safe_clear(get_scope_by_contract))


def update_scope(sb, scope_id: str, data: dict) -> ServiceResult:
    current, err = scope_repo.get_scope_by_id(sb, scope_id)
    if err:
        return ServiceResult(error=err)  # Req 4.12
    if "contrato_id" in data and data["contrato_id"] != current["contrato_id"]:
        return ServiceResult(error=MSG_CONTRACT_ID_IMMUTABLE)  # Req 4.11
    cleaned = _clean(data)
    if err := _validate(cleaned, [f for f in _CHECKS if f in cleaned]):
        return ServiceResult(error=err)
    ok, err = scope_repo.update_scope(sb, scope_id, cleaned)
    if err:
        return ServiceResult(error=err)
    return ServiceResult(data=ok, warning=safe_clear(get_scope_by_contract))
