"""Utilidades comuns dos repositórios: serialização e tradução de erros.

Sem nenhuma referência ao Streamlit (Req 9.1).
"""

import logging
from datetime import date, datetime
from decimal import Decimal

from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)

MSG_CONNECTION = "Falha ao carregar dados. Verifique a conexão."
MSG_SESSION = "Sua sessão expirou ou não tem permissão. Faça login novamente."
MSG_INVALID_ID = "Identificador inválido."
MSG_INVALID_DATA = "Dados inválidos: verifique os campos e tente novamente."


def to_json_value(value):
    """Converte valores Python para tipos aceitos pelo PostgREST (JSON)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def build_payload(data: dict, fields: tuple[str, ...]) -> dict:
    """Mantém apenas os campos permitidos presentes em data, já serializados."""
    return {field: to_json_value(data[field]) for field in fields if field in data}


def translate_error(exc: Exception, unique_violation: str | None = None) -> str:
    """Traduz exceções do supabase-py para mensagens em português para a UI."""
    if isinstance(exc, APIError):
        code = exc.code or ""
        if code == "23505" and unique_violation:
            return unique_violation
        if code in ("P0001", "P0002") and exc.message:
            return exc.message  # mensagens das funções/triggers já em português
        if code == "22P02":
            return MSG_INVALID_ID
        if code in ("23514", "23502", "22001", "22003", "22007", "22008"):
            return MSG_INVALID_DATA
        if code in ("42501", "PGRST301", "PGRST302") or "JWT" in (exc.message or ""):
            return MSG_SESSION
    logger.warning("Erro de acesso a dados: %r", exc)
    return MSG_CONNECTION
