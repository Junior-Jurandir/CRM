import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from supabase_auth.errors import AuthApiError

from auth import authentication as auth
from auth.login_guard import LoginGuard
from utils.supabase_client import SupabaseConfigError

EMAIL = "ana@empresa.com"
PASSWORD = "senha-segura"


def make_user(role=None, nome="Ana", email=EMAIL, user_metadata=None):
    app_metadata = {} if role is None else {"role": role}
    return SimpleNamespace(
        id="u-1",
        email=email,
        user_metadata=user_metadata if user_metadata is not None else {"nome": nome},
        app_metadata=app_metadata,
    )


def make_session(expires_in=3600):
    return SimpleNamespace(access_token="jwt", refresh_token="rt", expires_at=int(time.time()) + expires_in)


def make_client(user=None, session=None):
    sb = MagicMock()
    user = user or make_user()
    session = session or make_session()
    sb.auth.sign_in_with_password.return_value = SimpleNamespace(session=session, user=user)
    sb.auth.get_session.return_value = session
    sb.auth.get_user.return_value = SimpleNamespace(user=user)
    sb.auth.refresh_session.return_value = SimpleNamespace(session=make_session())
    return sb


@pytest.fixture
def state(monkeypatch):
    session_state: dict = {}
    monkeypatch.setattr(auth.st, "session_state", session_state)
    return session_state


@pytest.fixture
def guard(monkeypatch):
    g = LoginGuard()
    monkeypatch.setattr(auth, "_login_guard", lambda: g)
    return g


def invalid_credentials():
    return AuthApiError("Invalid login credentials", 400, "invalid_credentials")


# --- Perfis -------------------------------------------------------------------

@pytest.mark.parametrize(
    "app_metadata,esperado",
    [({"role": "admin"}, "admin"), ({"role": "membro"}, "membro"), ({}, "membro"), ({"role": "Admin"}, "membro"), (None, "membro")],
)
def test_extract_role(app_metadata, esperado):
    user = SimpleNamespace(app_metadata=app_metadata, user_metadata={})
    assert auth.extract_role(user) == esperado


def test_extract_role_ignora_user_metadata():
    user = make_user(role=None, user_metadata={"role": "admin"})
    assert auth.extract_role(user) == "membro"


def test_extract_role_aceita_dict():
    assert auth.extract_role({"app_metadata": {"role": "admin"}}) == "admin"


def test_is_admin(state):
    assert auth.is_admin() is False
    state["user"] = {"role": "admin"}
    assert auth.is_admin() is True
    assert auth.is_admin({"role": "membro"}) is False


# --- Login --------------------------------------------------------------------

def test_login_valido_grava_sessao(state, guard, monkeypatch):
    sb = make_client(user=make_user(role="admin"))
    monkeypatch.setattr(auth, "create_user_client", lambda: sb)

    profile, err = auth.login(f"  {EMAIL} ", PASSWORD)

    assert err is None
    assert profile == {"id": "u-1", "email": EMAIL, "nome": "Ana", "role": "admin"}
    assert state["sb"] is sb
    assert state["user"] == profile
    assert isinstance(state["login_at"], datetime)
    sb.auth.sign_in_with_password.assert_called_once_with({"email": EMAIL, "password": PASSWORD})


def test_login_cada_sessao_recebe_cliente_proprio(guard, monkeypatch):
    clients = [make_client(), make_client()]
    monkeypatch.setattr(auth, "create_user_client", lambda: clients.pop(0))
    states = [{}, {}]
    for s in states:
        monkeypatch.setattr(auth.st, "session_state", s)
        auth.login(EMAIL, PASSWORD)
    assert states[0]["sb"] is not states[1]["sb"]


def test_login_invalido_mensagem_generica(state, guard, monkeypatch):
    sb = make_client()
    sb.auth.sign_in_with_password.side_effect = invalid_credentials()
    monkeypatch.setattr(auth, "create_user_client", lambda: sb)

    profile, err = auth.login(EMAIL, PASSWORD)

    assert profile is None
    assert err == auth.MSG_INVALID_CREDENTIALS
    assert "sb" not in state


def test_login_formato_invalido_nao_chama_supabase(state, guard, monkeypatch):
    factory = MagicMock()
    monkeypatch.setattr(auth, "create_user_client", factory)
    assert auth.login("sem-arroba", PASSWORD) == (None, auth.MSG_INVALID_CREDENTIALS)
    assert auth.login(EMAIL, "curta") == (None, auth.MSG_INVALID_CREDENTIALS)
    factory.assert_not_called()


def test_login_bloqueia_apos_5_falhas(state, guard, monkeypatch):
    sb = make_client()
    sb.auth.sign_in_with_password.side_effect = invalid_credentials()
    monkeypatch.setattr(auth, "create_user_client", lambda: sb)

    for _ in range(4):
        assert auth.login(EMAIL, PASSWORD)[1] == auth.MSG_INVALID_CREDENTIALS
    _, err = auth.login(EMAIL, PASSWORD)
    assert "bloqueado por 15 minutos" in err

    sb.auth.sign_in_with_password.reset_mock()
    _, err = auth.login(EMAIL.upper(), PASSWORD)
    assert "bloqueado" in err
    sb.auth.sign_in_with_password.assert_not_called()


def test_login_sucesso_zera_tentativas(state, guard, monkeypatch):
    sb = make_client()
    monkeypatch.setattr(auth, "create_user_client", lambda: sb)
    sb.auth.sign_in_with_password.side_effect = invalid_credentials()
    for _ in range(4):
        auth.login(EMAIL, PASSWORD)
    sb.auth.sign_in_with_password.side_effect = None
    assert auth.login(EMAIL, PASSWORD)[1] is None
    sb.auth.sign_in_with_password.side_effect = invalid_credentials()
    assert auth.login(EMAIL, PASSWORD)[1] == auth.MSG_INVALID_CREDENTIALS


def test_login_falha_de_rede_nao_conta_tentativa(state, guard, monkeypatch):
    sb = make_client()
    sb.auth.sign_in_with_password.side_effect = ConnectionError("offline")
    monkeypatch.setattr(auth, "create_user_client", lambda: sb)
    for _ in range(6):
        assert auth.login(EMAIL, PASSWORD)[1] == auth.MSG_AUTH_UNAVAILABLE
    assert guard.check(EMAIL)[0] is False


def test_login_sem_configuracao(state, guard, monkeypatch):
    def fail():
        raise SupabaseConfigError("Configuração ausente: defina SUPABASE_URL")

    monkeypatch.setattr(auth, "create_user_client", fail)
    assert "SUPABASE_URL" in auth.login(EMAIL, PASSWORD)[1]


# --- Sessão -------------------------------------------------------------------

def logged_state(state, sb, hours_ago=0.0):
    state["sb"] = sb
    state["user"] = {"id": "u-1", "email": EMAIL, "nome": "Ana", "role": "membro"}
    state["login_at"] = datetime.now(timezone.utc) - timedelta(hours=hours_ago)


def test_sessao_sem_login_invalida(state):
    assert auth.is_session_valid() is False


def test_sessao_dentro_de_8h_valida(state):
    sb = make_client()
    logged_state(state, sb, hours_ago=7.9)
    assert auth.is_session_valid() is True
    sb.auth.refresh_session.assert_not_called()


def test_sessao_apos_8h_invalida(state):
    logged_state(state, make_client(), hours_ago=8)
    assert auth.is_session_valid() is False


def test_token_perto_de_expirar_e_renovado(state):
    sb = make_client(session=make_session(expires_in=30))
    logged_state(state, sb, hours_ago=1)
    assert auth.is_session_valid() is True
    sb.auth.refresh_session.assert_called_once()


def test_falha_na_renovacao_invalida_sessao(state):
    sb = make_client(session=make_session(expires_in=30))
    sb.auth.refresh_session.side_effect = AuthApiError("Invalid Refresh Token", 400, "refresh_token_not_found")
    logged_state(state, sb, hours_ago=1)
    assert auth.is_session_valid() is False


def test_sessao_ausente_no_cliente_invalida(state):
    sb = make_client()
    sb.auth.get_session.return_value = None
    logged_state(state, sb)
    assert auth.is_session_valid() is False


def test_logout_limpa_sessao_mesmo_com_erro(state):
    sb = make_client()
    sb.auth.sign_out.side_effect = RuntimeError("rede")
    logged_state(state, sb)
    auth.logout()
    assert state == {}
    sb.auth.sign_out.assert_called_once()


def test_require_auth_redireciona_para_login(state, monkeypatch):
    class Redirect(Exception):
        pass

    def switch_page(page):
        raise Redirect(page)

    monkeypatch.setattr(auth.st, "switch_page", switch_page)
    with pytest.raises(Redirect, match="app.py"):
        auth.require_auth()


def test_require_auth_retorna_cliente_da_sessao(state):
    sb = make_client()
    logged_state(state, sb)
    assert auth.require_auth() is sb


# --- Perfil -------------------------------------------------------------------

def test_update_profile_somente_nome(state):
    sb = make_client()
    sb.auth.update_user.return_value = SimpleNamespace(user=make_user(nome="Ana Maria"))
    logged_state(state, sb)

    assert auth.update_profile("Ana Maria", EMAIL) == (True, None, None)
    sb.auth.update_user.assert_called_once_with({"data": {"nome": "Ana Maria"}})
    assert state["user"]["nome"] == "Ana Maria"


def test_update_profile_email_pendente_de_confirmacao(state):
    sb = make_client()
    sb.auth.update_user.return_value = SimpleNamespace(user=make_user())  # e-mail antigo mantido
    logged_state(state, sb)

    ok, err, warning = auth.update_profile("Ana", "nova@empresa.com")

    assert ok and err is None and warning == auth.MSG_EMAIL_CONFIRMATION
    assert sb.auth.update_user.call_args.args[0]["email"] == "nova@empresa.com"
    assert state["user"]["email"] == EMAIL


def test_update_profile_email_aplicado_imediatamente(state):
    sb = make_client()
    sb.auth.update_user.return_value = SimpleNamespace(user=make_user(email="nova@empresa.com"))
    logged_state(state, sb)
    assert auth.update_profile("Ana", "nova@empresa.com") == (True, None, None)
    assert state["user"]["email"] == "nova@empresa.com"


def test_update_profile_email_invalido(state):
    sb = make_client()
    logged_state(state, sb)
    ok, err, _ = auth.update_profile("Ana", "invalido")
    assert ok is False and err
    sb.auth.update_user.assert_not_called()


# --- Cadastro de membros -------------------------------------------------------------

def admin_state(state, role="admin", user_metadata=None):
    sb = make_client(user=make_user(role=role, user_metadata=user_metadata))
    logged_state(state, sb)
    return sb


def test_membro_nao_pode_cadastrar(state, monkeypatch):
    admin_state(state, role="membro")
    factory = MagicMock()
    monkeypatch.setattr(auth, "create_admin_client", factory)

    assert auth.create_team_member("Bia", "bia@empresa.com") == (None, auth.MSG_PERMISSION_DENIED)
    factory.assert_not_called()


def test_user_metadata_admin_nao_concede_permissao(state, monkeypatch):
    admin_state(state, role=None, user_metadata={"nome": "Ana", "role": "admin"})
    factory = MagicMock()
    monkeypatch.setattr(auth, "create_admin_client", factory)
    assert auth.create_team_member("Bia", "bia@empresa.com")[1] == auth.MSG_PERMISSION_DENIED
    factory.assert_not_called()


def test_perfil_da_sessao_nao_e_suficiente(state, monkeypatch):
    """Sessão diz admin, mas o Supabase (fonte da verdade) diz membro."""
    admin_state(state, role="membro")
    state["user"]["role"] = "admin"
    factory = MagicMock()
    monkeypatch.setattr(auth, "create_admin_client", factory)
    assert auth.create_team_member("Bia", "bia@empresa.com")[1] == auth.MSG_PERMISSION_DENIED
    factory.assert_not_called()


def test_cadastro_sem_service_role(state, monkeypatch):
    admin_state(state)

    def fail():
        raise SupabaseConfigError("sem chave")

    monkeypatch.setattr(auth, "create_admin_client", fail)
    assert auth.create_team_member("Bia", "bia@empresa.com") == (None, auth.MSG_ADMIN_KEY_MISSING)


def test_cadastro_perfil_invalido(state, monkeypatch):
    admin_state(state)
    factory = MagicMock()
    monkeypatch.setattr(auth, "create_admin_client", factory)
    assert "Perfil inválido" in auth.create_team_member("Bia", "bia@empresa.com", role="root")[1]
    factory.assert_not_called()


def test_cadastro_dados_invalidos(state, monkeypatch):
    admin_state(state)
    monkeypatch.setattr(auth, "create_admin_client", MagicMock())
    assert auth.create_team_member("", "bia@empresa.com")[1] == "Nome é obrigatório."
    assert auth.create_team_member("Bia", "bia")[0] is None


@pytest.mark.parametrize("role", ["membro", "admin"])
def test_cadastro_bem_sucedido(state, monkeypatch, role):
    admin_state(state)
    admin = MagicMock()
    monkeypatch.setattr(auth, "create_admin_client", lambda: admin)

    password, err = auth.create_team_member(" Bia ", "bia@empresa.com", role=role)

    assert err is None
    assert isinstance(password, str) and len(password) >= 12
    attrs = admin.auth.admin.create_user.call_args.args[0]
    assert attrs == {
        "email": "bia@empresa.com",
        "password": password,
        "email_confirm": True,
        "user_metadata": {"nome": "Bia"},
        "app_metadata": {"role": role},
    }
    assert password not in repr(state)


def test_cadastro_email_existente(state, monkeypatch):
    admin_state(state)
    admin = MagicMock()
    admin.auth.admin.create_user.side_effect = AuthApiError(
        "A user with this email address has already been registered", 422, "email_exists"
    )
    monkeypatch.setattr(auth, "create_admin_client", lambda: admin)
    assert auth.create_team_member("Bia", "bia@empresa.com")[1] == "Já existe um usuário cadastrado com este e-mail."


def test_senhas_temporarias_sao_unicas(state, monkeypatch):
    admin_state(state)
    monkeypatch.setattr(auth, "create_admin_client", MagicMock)
    senhas = {auth.create_team_member("Bia", "bia@empresa.com")[0] for _ in range(20)}
    assert len(senhas) == 20


# Feature: crm-agentes-ia, Property 13: Apenas Admin cadastra membros
@given(
    role=st.one_of(
        st.none(),
        st.text(max_size=10),
        st.sampled_from(["admin", "Admin", "ADMIN", " admin", "admin ", "membro", "root"]),
        st.integers(),
    ),
    user_metadata_role=st.sampled_from([None, "admin"]),
)
@settings(max_examples=100)
def test_property_13_apenas_admin_cadastra(role, user_metadata_role):
    user_metadata = {"nome": "Ana"} if user_metadata_role is None else {"nome": "Ana", "role": user_metadata_role}
    sb = make_client(user=make_user(role=role, user_metadata=user_metadata))
    session_state = {
        "sb": sb,
        "user": {"id": "u-1", "email": EMAIL, "nome": "Ana", "role": "admin"},
        "login_at": datetime.now(timezone.utc),
    }
    admin = MagicMock()
    factory = MagicMock(return_value=admin)
    with patch.object(auth.st, "session_state", session_state), patch.object(auth, "create_admin_client", factory):
        password, err = auth.create_team_member("Bia", "bia@empresa.com")

    assert auth.extract_role(sb.auth.get_user.return_value.user) == ("admin" if role == "admin" else "membro")
    if role == "admin":
        assert err is None and password
        factory.assert_called_once()
    else:
        assert password is None and err == auth.MSG_PERMISSION_DENIED
        factory.assert_not_called()
