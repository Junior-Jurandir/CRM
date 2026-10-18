"""Acesso à tabela contratos. Registros nunca são excluídos (Req 3.10)."""

from repositories.base import build_payload, translate_error

TABLE = "contratos"
SELECT = "*, clientes(razao_social)"
CREATE_FIELDS = (
    "cliente_id",
    "titulo_projeto",
    "status",
    "data_inicio",
    "data_fim",
    "valor_mensal",
    "setup_fee",
)
EDITABLE_FIELDS = tuple(f for f in CREATE_FIELDS if f != "cliente_id")

STATUS_CANCELLED = "Cancelado"
MSG_NOT_FOUND = "Contrato não encontrado."
MSG_NOTHING_TO_UPDATE = "Nenhum campo para atualizar."


def list_contracts(client, client_id: str | None = None) -> tuple[list[dict] | None, str | None]:
    try:
        query = client.table(TABLE).select(SELECT)
        if client_id:
            query = query.eq("cliente_id", client_id)
        return query.order("data_fim").execute().data, None
    except Exception as exc:
        return None, translate_error(exc)


def get_contract_by_id(client, contract_id: str) -> tuple[dict | None, str | None]:
    try:
        rows = client.table(TABLE).select(SELECT).eq("id", contract_id).limit(1).execute().data
    except Exception as exc:
        return None, translate_error(exc)
    return (rows[0], None) if rows else (None, MSG_NOT_FOUND)


def create_contract(client, data: dict) -> tuple[dict | None, str | None]:
    """O trigger trg_contratos_cliente_ativo rejeita cliente inativo (P0001)."""
    try:
        rows = client.table(TABLE).insert(build_payload(data, CREATE_FIELDS)).execute().data
    except Exception as exc:
        return None, translate_error(exc)
    return (rows[0], None) if rows else (None, MSG_NOT_FOUND)


def update_contract(client, contract_id: str, data: dict) -> tuple[bool, str | None]:
    """cliente_id não é editável e nunca é enviado."""
    payload = build_payload(data, EDITABLE_FIELDS)
    if not payload:
        return False, MSG_NOTHING_TO_UPDATE
    try:
        rows = client.table(TABLE).update(payload).eq("id", contract_id).execute().data
    except Exception as exc:
        return False, translate_error(exc)
    return (True, None) if rows else (False, MSG_NOT_FOUND)


def cancel_contract(client, contract_id: str) -> tuple[bool, str | None]:
    """Marca como Cancelado via UPDATE; o registro é preservado."""
    return update_contract(client, contract_id, {"status": STATUS_CANCELLED})
