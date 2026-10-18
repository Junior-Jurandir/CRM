"""Clientes: validação, cache de leitura e invalidação após escrita."""

import streamlit as st

import config
from repositories import client_repo
from services import contract_service
from services.cache_utils import safe_clear
from services.result import DataLoadError, ServiceResult
from utils.validators import normalize_cnpj, validate_cnpj, validate_email, validate_text_length

TEXT_FIELDS = ("razao_social", "contato_nome", "email", "telefone")


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def list_clients(_sb, search: str = "") -> list[dict]:
    """Leitura cacheada. `_sb` fica fora da chave do cache (Req 8.4)."""
    rows, err = client_repo.list_clients(_sb, search)
    if err:
        raise DataLoadError(err)
    return rows


def list_active_clients(sb) -> list[dict]:
    return [c for c in list_clients(sb) if c.get("ativo")]


def _clean(data: dict, creating: bool) -> dict:
    cleaned = {k: (data.get(k) or "").strip() for k in TEXT_FIELDS if k in data or creating}
    if "telefone" in cleaned and not cleaned["telefone"]:
        cleaned["telefone"] = None
    if creating:
        cleaned["cnpj"] = normalize_cnpj(data.get("cnpj"))
    return cleaned


def _validate(data: dict) -> str | None:
    checks = {
        "razao_social": lambda v: validate_text_length(v, "Razão social", 255),
        "contato_nome": lambda v: validate_text_length(v, "Nome do contato", 150),
        "email": validate_email,
        "telefone": lambda v: validate_text_length(v, "Telefone", 20, required=False),
        "cnpj": validate_cnpj,
    }
    for field, check in checks.items():
        if field in data:
            ok, err = check(data[field])
            if not ok:
                return err
    return None


def create_client(sb, data: dict) -> ServiceResult:
    cleaned = _clean(data, creating=True)
    if err := _validate(cleaned):
        return ServiceResult(error=err)
    created, err = client_repo.create_client(sb, cleaned)
    if err:
        return ServiceResult(error=err)
    return ServiceResult(data=created, warning=safe_clear(list_clients))


def update_client(sb, client_id: str, data: dict) -> ServiceResult:
    cleaned = _clean(data, creating=False)  # cnpj, id e created_at são descartados (Req 2.4)
    if err := _validate(cleaned):
        return ServiceResult(error=err)
    ok, err = client_repo.update_client(sb, client_id, cleaned)
    if err:
        return ServiceResult(error=err)
    return ServiceResult(data=ok, warning=safe_clear(list_clients))


def deactivate_client(sb, client_id: str) -> ServiceResult:
    """Inativa o cliente e cancela contratos ativos/em implantação (Req 2.5, 2.7).

    data = quantidade de contratos cancelados. Invalida clientes e contratos.
    """
    cancelled, err = client_repo.deactivate_client(sb, client_id)
    if err:
        return ServiceResult(error=err)
    return ServiceResult(data=cancelled, warning=safe_clear(list_clients, contract_service.list_contracts))
