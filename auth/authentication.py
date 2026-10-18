"""Autenticação, sessão, perfis de acesso e cadastro de membros.

Todo acesso ao Supabase Auth passa por este módulo. As páginas nunca chamam
supabase.auth diretamente (Req 9.1). É o único módulo autorizado a criar o
cliente com a chave service_role (Req 7.5).
"""

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import streamlit as st
from supabase_auth.errors import AuthApiError, AuthError

import config
from auth.login_guard import LoginGuard
from utils.supabase_client import SupabaseConfigError, create_admin_client, create_user_client
from utils.validators import validate_email, validate_password_format, validate_text_length

logger = logging.getLogger(__name__)

SESSION_CLIENT = "sb"
SESSION_USER = "user"
SESSION_LOGIN_AT = "login_at"
_SESSION_KEYS = (SESSION_CLIENT, SESSION_USER, SESSION_LOGIN_AT)

ROLE_ADMIN = "admin"
ROLE_MEMBER = "membro"
VALID_ROLES = (ROLE_MEMBER, ROLE_ADMIN)
ROLE_LABELS = {ROLE_ADMIN: "Admin", ROLE_MEMBER: "Membro"}

MSG_INVALID_CREDENTIALS = "E-mail ou senha inválidos."
MSG_AUTH_UNAVAILABLE = "Falha ao conectar ao serviço de autenticação. Tente novamente."
MSG_PERMISSION_DENIED = "Permissão negada: apenas administradores podem cadastrar membros."
MSG_ADMIN_KEY_MISSING = (
    "Cadastro de membros indisponível: chave administrativa não configurada."
)
MSG_EMAIL_CONFIRMATION = (
    "Enviamos um link de confirmação para o novo e-mail. "
    "A alteração só será aplicada após a confirmação."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@st.cache_resource
def _login_guard() -> LoginGuard:
    """Instância única por processo, compartilhada por todas as sessões."""
    return LoginGuard(
        max_attempts=config.LOGIN_MAX_ATTEMPTS,
        lockout=timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES),
    )


def _lockout_message(seconds: int) -> str:
    minutes = max(1, -(-seconds // 60))
    return (
        f"Acesso bloqueado por {config.LOGIN_LOCKOUT_MINUTES} minutos após "
        f"{config.LOGIN_MAX_ATTEMPTS} tentativas inválidas. "
        f"Tente novamente em {minutes} minuto(s)."
    )


# --- Perfis -------------------------------------------------------------------

def _metadata(user, field: str) -> dict:
    value = user.get(field) if isinstance(user, dict) else getattr(user, field, None)
    return value if isinstance(value, dict) else {}


def extract_role(user) -> str:
    """Perfil a partir de app_metadata.role; qualquer valor diferente de 'admin' → 'membro'.

    Nunca lê user_metadata, que o próprio usuário pode editar (Req 11.2).
    """
    return ROLE_ADMIN if _metadata(user, "app_metadata").get("role") == ROLE_ADMIN else ROLE_MEMBER


def _build_profile(user) -> dict:
    email = getattr(user, "email", None) or ""
    nome = _metadata(user, "user_metadata").get("nome") or email.split("@")[0]
    return {"id": getattr(user, "id", None), "email": email, "nome": nome, "role": extract_role(user)}


def get_current_user() -> dict | None:
    return st.session_state.get(SESSION_USER)


def get_session_client():
    return st.session_state.get(SESSION_CLIENT)


def is_admin(user: dict | None = None) -> bool:
    """Para a UI. A autorização real de create_team_member consulta o Supabase."""
    user = user if user is not None else get_current_user()
    return bool(user) and user.get("role") == ROLE_ADMIN


# --- Login / logout / sessão ------------------------------------------------------

def login(email: str, password: str) -> tuple[dict | None, str | None]:
    """Autentica via Supabase Auth. Retorna (perfil, erro)."""
    email = (email or "").strip()
    if not validate_email(email)[0] or not validate_password_format(password)[0]:
        return None, MSG_INVALID_CREDENTIALS

    guard = _login_guard()
    locked, seconds = guard.check(email)
    if locked:
        return None, _lockout_message(seconds)

    try:
        sb = create_user_client()
    except SupabaseConfigError as exc:
        return None, str(exc)

    try:
        response = sb.auth.sign_in_with_password({"email": email, "password": password})
    except AuthApiError:
        response = None
    except Exception:
        logger.exception("Falha inesperada no login")
        return None, MSG_AUTH_UNAVAILABLE

    if response is None or response.session is None or response.user is None:
        guard.register_failure(email)
        locked, seconds = guard.check(email)
        return None, _lockout_message(seconds) if locked else MSG_INVALID_CREDENTIALS

    guard.register_success(email)
    profile = _build_profile(response.user)
    st.session_state[SESSION_CLIENT] = sb
    st.session_state[SESSION_USER] = profile
    st.session_state[SESSION_LOGIN_AT] = _utcnow()
    return profile, None


def _clear_session() -> None:
    for key in _SESSION_KEYS:
        st.session_state.pop(key, None)


def logout() -> None:
    """Invalida o token no Supabase Auth e limpa a sessão local."""
    sb = get_session_client()
    if sb is not None:
        try:
            sb.auth.sign_out()
        except Exception:
            logger.warning("Falha ao invalidar o token no logout", exc_info=True)
    _clear_session()


def is_session_valid() -> bool:
    """Sessão existe, tem menos de 8h desde o login e o token está válido/renovado."""
    sb = get_session_client()
    login_at = st.session_state.get(SESSION_LOGIN_AT)
    if sb is None or login_at is None:
        return False
    if _utcnow() - login_at >= timedelta(hours=config.SESSION_MAX_HOURS):
        return False
    try:
        session = sb.auth.get_session()
        if session is None:
            return False
        expires_at = session.expires_at or 0
        if expires_at and expires_at - time.time() <= config.TOKEN_REFRESH_MARGIN_SECONDS:
            refreshed = sb.auth.refresh_session()
            if refreshed is None or refreshed.session is None:
                return False
    except AuthError:
        return False
    except Exception:
        logger.warning("Falha ao validar/renovar a sessão", exc_info=True)
        return False
    return True


def require_auth():
    """Retorna o cliente Supabase da sessão ou redireciona para o Login."""
    if not is_session_valid():
        logout()
        st.switch_page("app.py")
        st.stop()
    return get_session_client()


def render_user_sidebar() -> None:
    """Sidebar comum às páginas autenticadas: usuário, perfil e botão Sair (Req 11.7)."""
    user = get_current_user() or {}
    with st.sidebar:
        st.markdown(f"**{user.get('nome', '')}**")
        st.caption(user.get("email", ""))
        st.caption(f"Perfil: {ROLE_LABELS.get(user.get('role'), 'Membro')}")
        if st.button("Sair", width="stretch"):
            logout()
            st.switch_page("app.py")


# --- Perfil e membros --------------------------------------------------------------

def update_profile(nome: str, email: str) -> tuple[bool, str | None, str | None]:
    """Atualiza nome (user_metadata) e e-mail do usuário logado. Retorna (ok, erro, aviso)."""
    sb = get_session_client()
    user = get_current_user()
    if sb is None or user is None:
        return False, "Sessão expirada. Faça login novamente.", None

    nome = (nome or "").strip()
    email = (email or "").strip()
    for ok, err in (validate_text_length(nome, "Nome", 150), validate_email(email)):
        if not ok:
            return False, err, None

    attributes: dict = {"data": {"nome": nome}}
    email_changed = email.lower() != (user.get("email") or "").lower()
    if email_changed:
        attributes["email"] = email

    try:
        response = sb.auth.update_user(attributes)
    except AuthApiError as exc:
        return False, f"Não foi possível atualizar o perfil: {exc.message}", None
    except Exception:
        logger.exception("Falha ao atualizar perfil")
        return False, MSG_AUTH_UNAVAILABLE, None

    updated = _build_profile(response.user) if response and response.user else {**user, "nome": nome}
    st.session_state[SESSION_USER] = {**user, "nome": updated["nome"], "email": updated["email"] or user["email"]}

    warning = None
    if email_changed and (updated["email"] or "").lower() != email.lower():
        warning = MSG_EMAIL_CONFIRMATION
    return True, None, warning


def _requester_is_admin() -> bool:
    """Revalida o perfil no Supabase Auth no momento da operação (Req 11.4)."""
    sb = get_session_client()
    if sb is None:
        return False
    try:
        response = sb.auth.get_user()
    except Exception:
        logger.warning("Falha ao verificar o perfil do solicitante", exc_info=True)
        return False
    return bool(response and response.user) and extract_role(response.user) == ROLE_ADMIN


def create_team_member(nome: str, email: str, role: str = ROLE_MEMBER) -> tuple[str | None, str | None]:
    """Cria a credencial de um novo membro. Retorna (senha_temporaria, erro).

    A senha é gerada aqui, devolvida uma única vez para exibição e não é
    persistida (Req 9.4). O cliente administrativo é descartado ao final.
    """
    if not _requester_is_admin():
        return None, MSG_PERMISSION_DENIED

    nome = (nome or "").strip()
    email = (email or "").strip()
    for ok, err in (validate_text_length(nome, "Nome", 150), validate_email(email)):
        if not ok:
            return None, err
    if role not in VALID_ROLES:
        return None, "Perfil inválido. Escolha entre Membro e Admin."

    try:
        admin = create_admin_client()
    except SupabaseConfigError:
        return None, MSG_ADMIN_KEY_MISSING

    password = secrets.token_urlsafe(12)
    try:
        admin.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"nome": nome},
                "app_metadata": {"role": role},
            }
        )
    except AuthApiError as exc:
        if exc.code == "email_exists" or "already" in (exc.message or "").lower():
            return None, "Já existe um usuário cadastrado com este e-mail."
        return None, f"Não foi possível cadastrar o membro: {exc.message}"
    except Exception:
        logger.exception("Falha ao cadastrar membro")
        return None, MSG_AUTH_UNAVAILABLE

    return password, None
