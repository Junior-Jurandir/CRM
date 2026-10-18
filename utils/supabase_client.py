"""Fábrica de clientes Supabase.

Não é um singleton: cada sessão de usuário recebe um cliente próprio, para que
o JWT de um usuário nunca seja usado em requisições de outro (Req 1.9).
"""

from supabase import Client, ClientOptions, create_client

import config


class SupabaseConfigError(RuntimeError):
    """Variáveis de conexão com o Supabase ausentes."""


def _require(value: str, name: str) -> str:
    if not value:
        raise SupabaseConfigError(
            f"Configuração ausente: defina {name} no arquivo .env (veja .env.example)."
        )
    return value


def create_user_client() -> Client:
    """Cria um cliente novo com a chave anon, dedicado a uma sessão de usuário.

    auto_refresh_token=False: a renovação é feita explicitamente em
    auth.authentication.is_session_valid(), sem threads de timer por sessão.
    persist_session=False: a sessão fica apenas na memória deste cliente.
    """
    return create_client(
        _require(config.SUPABASE_URL, "SUPABASE_URL"),
        _require(config.SUPABASE_ANON_KEY, "SUPABASE_ANON_KEY"),
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def create_admin_client() -> Client:
    """Cria um cliente com a chave service_role (ignora RLS).

    USO EXCLUSIVO de auth/authentication.py, para criação de membros da equipe
    (Req 7.5). Verificado por tests/test_architecture.py.
    """
    return create_client(
        _require(config.SUPABASE_URL, "SUPABASE_URL"),
        _require(config.SUPABASE_SERVICE_ROLE_KEY, "SUPABASE_SERVICE_ROLE_KEY"),
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )
