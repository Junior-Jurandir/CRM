"""Acesso à tabela clientes e à RPC inativar_cliente.

Todas as funções recebem o cliente Supabase da sessão e retornam
(resultado, mensagem_de_erro), sem lançar exceções.
"""

import re

from repositories.base import build_payload, translate_error
from utils.validators import normalize_cnpj

TABLE = "clientes"
CREATE_FIELDS = ("razao_social", "cnpj", "contato_nome", "email", "telefone")
EDITABLE_FIELDS = ("razao_social", "contato_nome", "email", "telefone")

MSG_DUPLICATE_CNPJ = "CNPJ já cadastrado na base de dados."
MSG_NOT_FOUND = "Cliente não encontrado."
MSG_NOTHING_TO_UPDATE = "Nenhum campo para atualizar."

_CNPJ_SEARCH_RE = re.compile(r"[\d.\-/\s]+")


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_clients(client, search: str = "") -> tuple[list[dict] | None, str | None]:
    """Sem busca → todos. Termo com 14 dígitos (com ou sem pontuação) → CNPJ exato.
    Caso contrário → correspondência parcial em razao_social (Req 2.9)."""
    term = (search or "").strip()
    try:
        query = client.table(TABLE).select("*")
        digits = normalize_cnpj(term)
        if term and len(digits) == 14 and _CNPJ_SEARCH_RE.fullmatch(term):
            query = query.eq("cnpj", digits)
        elif term:
            query = query.ilike("razao_social", f"%{_escape_like(term)}%")
        return query.order("razao_social").execute().data, None
    except Exception as exc:
        return None, translate_error(exc)


def get_client_by_id(client, client_id: str) -> tuple[dict | None, str | None]:
    try:
        rows = client.table(TABLE).select("*").eq("id", client_id).limit(1).execute().data
    except Exception as exc:
        return None, translate_error(exc)
    return (rows[0], None) if rows else (None, MSG_NOT_FOUND)


def cnpj_exists(client, cnpj: str) -> tuple[bool | None, str | None]:
    try:
        rows = client.table(TABLE).select("id").eq("cnpj", cnpj).limit(1).execute().data
    except Exception as exc:
        return None, translate_error(exc)
    return bool(rows), None


def create_client(client, data: dict) -> tuple[dict | None, str | None]:
    """Insere um cliente. UUID e created_at são gerados pelo banco (Req 2.2)."""
    payload = build_payload(data, CREATE_FIELDS)
    exists, err = cnpj_exists(client, payload.get("cnpj", ""))
    if err:
        return None, err
    if exists:
        return None, MSG_DUPLICATE_CNPJ
    try:
        rows = client.table(TABLE).insert(payload).execute().data
    except Exception as exc:
        # 23505: outro usuário cadastrou o mesmo CNPJ entre a verificação e o insert.
        return None, translate_error(exc, unique_violation=MSG_DUPLICATE_CNPJ)
    return (rows[0], None) if rows else (None, MSG_NOT_FOUND)


def update_client(client, client_id: str, data: dict) -> tuple[bool, str | None]:
    """Atualiza somente os campos editáveis; id, cnpj e created_at nunca são enviados (Req 2.4)."""
    payload = build_payload(data, EDITABLE_FIELDS)
    if not payload:
        return False, MSG_NOTHING_TO_UPDATE
    try:
        rows = client.table(TABLE).update(payload).eq("id", client_id).execute().data
    except Exception as exc:
        return False, translate_error(exc)
    return (True, None) if rows else (False, MSG_NOT_FOUND)


def deactivate_client(client, client_id: str) -> tuple[int | None, str | None]:
    """Inativa o cliente e cancela seus contratos ativos/em implantação de forma atômica
    (RPC inativar_cliente). Retorna a quantidade de contratos cancelados."""
    try:
        cancelled = client.rpc("inativar_cliente", {"p_cliente_id": client_id}).execute().data
    except Exception as exc:
        return None, translate_error(exc)
    return int(cancelled or 0), None
