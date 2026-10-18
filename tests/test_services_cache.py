from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from services import client_service, contract_service, scope_service
from services.cache_utils import CACHE_WARNING, safe_clear
from services.result import DataLoadError

SB = object()  # cliente da sessão (opaco para os serviços)

CLIENTE = {"razao_social": " Acme ", "cnpj": "12.345.678/0001-90", "contato_nome": "Ana", "email": "ana@acme.com", "telefone": ""}
CONTRATO = {
    "cliente_id": "c-1",
    "titulo_projeto": "Agente SAC",
    "status": "Ativo",
    "data_inicio": date(2026, 1, 1),
    "data_fim": date(2026, 12, 31),
    "valor_mensal": "1500,50",
    "setup_fee": 0,
}
ESCOPO = {
    "contrato_id": "k-1",
    "tipo_arquitetura": "RAG",
    "limite_requisicoes": 1000,
    "horas_manutencao": 10.5,
    "modelos_permitidos": [" claude-opus-5-5 "],
}


def cached_mock():
    fn = MagicMock()
    fn.clear = MagicMock()
    return fn


@pytest.fixture
def caches(monkeypatch):
    mocks = {
        "clients": cached_mock(),
        "contracts": cached_mock(),
        "scopes": cached_mock(),
    }
    monkeypatch.setattr(client_service, "list_clients", mocks["clients"])
    monkeypatch.setattr(contract_service, "list_contracts", mocks["contracts"])
    monkeypatch.setattr(scope_service, "get_scope_by_contract", mocks["scopes"])
    return mocks


# --- safe_clear -----------------------------------------------------------------

def test_safe_clear_sucesso():
    a, b = cached_mock(), cached_mock()
    assert safe_clear(a, b) is None
    a.clear.assert_called_once()
    b.clear.assert_called_once()


def test_safe_clear_falha_gera_aviso_e_continua():
    a, b = cached_mock(), cached_mock()
    a.clear.side_effect = RuntimeError("cache")
    assert safe_clear(a, b) == CACHE_WARNING
    b.clear.assert_called_once()


# --- Leituras cacheadas -------------------------------------------------------------

def test_leitura_com_erro_nao_e_cacheada(monkeypatch):
    client_service.list_clients.clear()
    sb = object()
    monkeypatch.setattr(client_service.client_repo, "list_clients", lambda _sb, search="": (None, "Falha ao carregar dados."))
    with pytest.raises(DataLoadError):
        client_service.list_clients(sb, "x")
    monkeypatch.setattr(client_service.client_repo, "list_clients", lambda _sb, search="": ([{"id": 1}], None))
    assert client_service.list_clients(sb, "x") == [{"id": 1}]
    client_service.list_clients.clear()


def test_leitura_cacheada_ate_invalidacao(monkeypatch):
    client_service.list_clients.clear()
    repo = MagicMock(return_value=([{"id": 1}], None))
    monkeypatch.setattr(client_service.client_repo, "list_clients", repo)
    client_service.list_clients(object(), "cache")
    client_service.list_clients(object(), "cache")  # outro cliente: mesma chave (_sb fora do hash)
    assert repo.call_count == 1
    client_service.list_clients.clear()
    client_service.list_clients(object(), "cache")
    assert repo.call_count == 2
    client_service.list_clients.clear()


# --- Clientes -------------------------------------------------------------------

def test_create_client_normaliza_valida_e_invalida_cache(caches, monkeypatch):
    repo = MagicMock(return_value=({"id": "c-1"}, None))
    monkeypatch.setattr(client_service.client_repo, "create_client", repo)

    result = client_service.create_client(SB, CLIENTE)

    assert result.ok and result.data == {"id": "c-1"} and result.warning is None
    sent = repo.call_args.args[1]
    assert sent["cnpj"] == "12345678000190"
    assert sent["razao_social"] == "Acme"
    assert sent["telefone"] is None
    caches["clients"].clear.assert_called_once()


def test_create_client_invalido_nao_chama_repositorio(caches, monkeypatch):
    repo = MagicMock()
    monkeypatch.setattr(client_service.client_repo, "create_client", repo)
    assert client_service.create_client(SB, {**CLIENTE, "email": "invalido"}).error
    assert client_service.create_client(SB, {**CLIENTE, "cnpj": "123"}).error
    assert client_service.create_client(SB, {**CLIENTE, "razao_social": ""}).error == "Razão social é obrigatório."
    repo.assert_not_called()
    caches["clients"].clear.assert_not_called()


def test_create_client_erro_do_repositorio_nao_invalida(caches, monkeypatch):
    monkeypatch.setattr(client_service.client_repo, "create_client", MagicMock(return_value=(None, "CNPJ já cadastrado na base de dados.")))
    result = client_service.create_client(SB, CLIENTE)
    assert result.error == "CNPJ já cadastrado na base de dados."
    caches["clients"].clear.assert_not_called()


def test_update_client_descarta_cnpj(caches, monkeypatch):
    repo = MagicMock(return_value=(True, None))
    monkeypatch.setattr(client_service.client_repo, "update_client", repo)
    assert client_service.update_client(SB, "c-1", {"razao_social": "Nova", "cnpj": "99999999999999"}).ok
    assert repo.call_args.args[2] == {"razao_social": "Nova"}


def test_deactivate_client_invalida_clientes_e_contratos(caches, monkeypatch):
    monkeypatch.setattr(client_service.client_repo, "deactivate_client", MagicMock(return_value=(2, None)))
    result = client_service.deactivate_client(SB, "c-1")
    assert result.data == 2
    caches["clients"].clear.assert_called_once()
    caches["contracts"].clear.assert_called_once()


def test_list_active_clients(monkeypatch):
    monkeypatch.setattr(client_service, "list_clients", lambda sb: [{"id": 1, "ativo": True}, {"id": 2, "ativo": False}])
    assert client_service.list_active_clients(SB) == [{"id": 1, "ativo": True}]


# --- Contratos -------------------------------------------------------------------

def test_create_contract_ok(caches, monkeypatch):
    monkeypatch.setattr(contract_service.client_repo, "get_client_by_id", MagicMock(return_value=({"ativo": True}, None)))
    repo = MagicMock(return_value=({"id": "k-1"}, None))
    monkeypatch.setattr(contract_service.contract_repo, "create_contract", repo)

    assert contract_service.create_contract(SB, CONTRATO).ok
    assert repo.call_args.args[1]["valor_mensal"] == Decimal("1500.50")
    caches["contracts"].clear.assert_called_once()


def test_create_contract_cliente_inativo(caches, monkeypatch):
    monkeypatch.setattr(contract_service.client_repo, "get_client_by_id", MagicMock(return_value=({"ativo": False}, None)))
    repo = MagicMock()
    monkeypatch.setattr(contract_service.contract_repo, "create_contract", repo)
    assert contract_service.create_contract(SB, CONTRATO).error == contract_service.MSG_CLIENT_INACTIVE
    repo.assert_not_called()


@pytest.mark.parametrize(
    "change,fragment",
    [
        ({"data_fim": date(2026, 1, 1)}, "posterior"),
        ({"valor_mensal": "0"}, "Valor mensal"),
        ({"setup_fee": "-1"}, "Setup fee"),
        ({"status": "Ativa"}, "Status"),
        ({"titulo_projeto": ""}, "Título"),
        ({"cliente_id": None}, "cliente"),
    ],
)
def test_create_contract_validacoes(caches, monkeypatch, change, fragment):
    lookup = MagicMock()
    monkeypatch.setattr(contract_service.client_repo, "get_client_by_id", lookup)
    result = contract_service.create_contract(SB, {**CONTRATO, **change})
    assert fragment.lower() in result.error.lower()
    lookup.assert_not_called()


def test_update_contract_valida_datas_com_registro_atual(caches, monkeypatch):
    current = {**CONTRATO, "data_inicio": "2026-06-01", "data_fim": "2026-12-31"}
    monkeypatch.setattr(contract_service.contract_repo, "get_contract_by_id", MagicMock(return_value=(current, None)))
    repo = MagicMock(return_value=(True, None))
    monkeypatch.setattr(contract_service.contract_repo, "update_contract", repo)

    assert "posterior" in contract_service.update_contract(SB, "k-1", {"data_fim": date(2026, 5, 1)}).error
    repo.assert_not_called()

    assert contract_service.update_contract(SB, "k-1", {"status": "Renovação Pendente", "cliente_id": "outro"}).ok
    assert repo.call_args.args[2] == {"status": "Renovação Pendente"}
    caches["contracts"].clear.assert_called_once()


def test_cancel_contract_invalida(caches, monkeypatch):
    monkeypatch.setattr(contract_service.contract_repo, "cancel_contract", MagicMock(return_value=(True, None)))
    assert contract_service.cancel_contract(SB, "k-1").ok
    caches["contracts"].clear.assert_called_once()


# --- Escopo -----------------------------------------------------------------------

def test_parse_models():
    assert scope_service.parse_models(" a \n\n b\n") == ["a", "b"]


def test_create_scope_ok(caches, monkeypatch):
    repo = MagicMock(return_value=({"id": "s-1"}, None))
    monkeypatch.setattr(scope_service.scope_repo, "create_scope", repo)
    assert scope_service.create_scope(SB, ESCOPO).ok
    assert repo.call_args.args[1]["modelos_permitidos"] == ["claude-opus-5-5"]
    caches["scopes"].clear.assert_called_once()


@pytest.mark.parametrize(
    "change",
    [{"limite_requisicoes": 0}, {"horas_manutencao": 0.4}, {"modelos_permitidos": []}, {"tipo_arquitetura": " "}, {"contrato_id": ""}],
)
def test_create_scope_invalido(caches, monkeypatch, change):
    repo = MagicMock()
    monkeypatch.setattr(scope_service.scope_repo, "create_scope", repo)
    assert scope_service.create_scope(SB, {**ESCOPO, **change}).error
    repo.assert_not_called()


def test_update_scope_rejeita_troca_de_contrato(caches, monkeypatch):
    monkeypatch.setattr(scope_service.scope_repo, "get_scope_by_id", MagicMock(return_value=({"id": "s-1", "contrato_id": "k-1"}, None)))
    repo = MagicMock()
    monkeypatch.setattr(scope_service.scope_repo, "update_scope", repo)
    assert scope_service.update_scope(SB, "s-1", {"contrato_id": "k-2"}).error == scope_service.MSG_CONTRACT_ID_IMMUTABLE
    repo.assert_not_called()


def test_update_scope_mesmo_contrato_e_aceito(caches, monkeypatch):
    monkeypatch.setattr(scope_service.scope_repo, "get_scope_by_id", MagicMock(return_value=({"id": "s-1", "contrato_id": "k-1"}, None)))
    monkeypatch.setattr(scope_service.scope_repo, "update_scope", MagicMock(return_value=(True, None)))
    assert scope_service.update_scope(SB, "s-1", {"contrato_id": "k-1", "limite_requisicoes": 5}).ok


def test_update_scope_inexistente(caches, monkeypatch):
    monkeypatch.setattr(scope_service.scope_repo, "get_scope_by_id", MagicMock(return_value=(None, "Escopo não encontrado.")))
    assert scope_service.update_scope(SB, "x", {"limite_requisicoes": 5}).error == "Escopo não encontrado."


# --- Property 12 ---------------------------------------------------------------------

OPERATIONS = {
    "create_client": (client_service, "client_repo", "create_client", ({"id": 1}, None), (CLIENTE,), ["clients"]),
    "update_client": (client_service, "client_repo", "update_client", (True, None), ("c-1", {"razao_social": "X"}), ["clients"]),
    "deactivate_client": (client_service, "client_repo", "deactivate_client", (1, None), ("c-1",), ["clients", "contracts"]),
    "cancel_contract": (contract_service, "contract_repo", "cancel_contract", (True, None), ("k-1",), ["contracts"]),
    "create_scope": (scope_service, "scope_repo", "create_scope", ({"id": 1}, None), (ESCOPO,), ["scopes"]),
}


# Feature: crm-agentes-ia, Property 12: Invalidação de cache após escrita bem-sucedida
@given(op=st.sampled_from(sorted(OPERATIONS)), repo_fails=st.booleans(), clear_fails=st.booleans())
@settings(max_examples=100)
def test_property_12_invalidacao_de_cache(op, repo_fails, clear_fails):
    module, repo_name, fn_name, success, args, affected = OPERATIONS[op]
    caches = {"clients": cached_mock(), "contracts": cached_mock(), "scopes": cached_mock()}
    for mock in caches.values():
        if clear_fails:
            mock.clear.side_effect = RuntimeError("cache")
    repo = getattr(module, repo_name)
    response = ((None if fn_name.startswith("create") else False), "erro do banco") if repo_fails else success

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client_service, "list_clients", caches["clients"])
        mp.setattr(contract_service, "list_contracts", caches["contracts"])
        mp.setattr(scope_service, "get_scope_by_contract", caches["scopes"])
        mp.setattr(repo, fn_name, MagicMock(return_value=response))
        result = getattr(module, fn_name)(SB, *args)

    if repo_fails:
        assert result.error == "erro do banco"
        assert all(not m.clear.called for m in caches.values())
    else:
        assert result.error is None and result.data == success[0]
        assert result.warning == (CACHE_WARNING if clear_fails else None)
        for name, mock in caches.items():
            assert mock.clear.called == (name in affected)
