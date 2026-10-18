"""Acesso à tabela escopo_agentes (1:1 com contratos)."""

from repositories.base import MSG_INVALID_ID, build_payload, translate_error

TABLE = "escopo_agentes"
TECHNICAL_FIELDS = ("tipo_arquitetura", "limite_requisicoes", "horas_manutencao", "modelos_permitidos")
CREATE_FIELDS = ("contrato_id",) + TECHNICAL_FIELDS

MSG_NOT_FOUND = "Escopo não encontrado."
MSG_CONTRACT_NOT_FOUND = "Contrato não encontrado."
MSG_DUPLICATE = "Este contrato já possui um escopo cadastrado."
MSG_NOTHING_TO_UPDATE = "Nenhum campo para atualizar."


def get_scope_by_contract(client, contract_id: str) -> tuple[dict | None, str | None]:
    """(None, None) quando o contrato ainda não tem escopo."""
    try:
        rows = client.table(TABLE).select("*").eq("contrato_id", contract_id).limit(1).execute().data
    except Exception as exc:
        return None, translate_error(exc)
    return (rows[0] if rows else None), None


def get_scope_by_id(client, scope_id: str) -> tuple[dict | None, str | None]:
    try:
        rows = client.table(TABLE).select("*").eq("id", scope_id).limit(1).execute().data
    except Exception as exc:
        return None, translate_error(exc)
    return (rows[0], None) if rows else (None, MSG_NOT_FOUND)


def _contract_exists(client, contract_id: str) -> tuple[bool | None, str | None]:
    try:
        rows = client.table("contratos").select("id").eq("id", contract_id).limit(1).execute().data
    except Exception as exc:
        message = translate_error(exc)
        return None, MSG_CONTRACT_NOT_FOUND if message == MSG_INVALID_ID else message
    return bool(rows), None


def create_scope(client, data: dict) -> tuple[dict | None, str | None]:
    """Exige contrato_id existente (Req 4.2, 4.3)."""
    exists, err = _contract_exists(client, data.get("contrato_id") or "")
    if err:
        return None, err
    if not exists:
        return None, MSG_CONTRACT_NOT_FOUND
    try:
        rows = client.table(TABLE).insert(build_payload(data, CREATE_FIELDS)).execute().data
    except Exception as exc:
        if getattr(exc, "code", None) == "23503":
            return None, MSG_CONTRACT_NOT_FOUND
        return None, translate_error(exc, unique_violation=MSG_DUPLICATE)
    return (rows[0], None) if rows else (None, MSG_NOT_FOUND)


def update_scope(client, scope_id: str, data: dict) -> tuple[bool, str | None]:
    """Envia apenas campos técnicos: id e contrato_id são preservados (Req 4.10)."""
    payload = build_payload(data, TECHNICAL_FIELDS)
    if not payload:
        return False, MSG_NOTHING_TO_UPDATE
    try:
        rows = client.table(TABLE).update(payload).eq("id", scope_id).execute().data
    except Exception as exc:
        return False, translate_error(exc)
    return (True, None) if rows else (False, MSG_NOT_FOUND)
