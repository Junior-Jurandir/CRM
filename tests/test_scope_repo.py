from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from repositories import scope_repo as repo
from tests.fakes import FakeClient, api_error

ESCOPO = {
    "contrato_id": "k-1",
    "tipo_arquitetura": "RAG",
    "limite_requisicoes": 1000,
    "horas_manutencao": Decimal("10.5"),
    "modelos_permitidos": ["claude-opus-5-5"],
}


def test_get_scope_by_contract_sem_escopo():
    assert repo.get_scope_by_contract(FakeClient([]), "k-1") == (None, None)


def test_create_scope_contrato_inexistente():
    sb = FakeClient([])
    assert repo.create_scope(sb, ESCOPO) == (None, repo.MSG_CONTRACT_NOT_FOUND)
    assert len(sb.executed) == 1  # não tentou inserir


def test_create_scope_contrato_id_invalido():
    sb = FakeClient(api_error("22P02", "invalid input syntax for type uuid"))
    assert repo.create_scope(sb, {**ESCOPO, "contrato_id": "abc"}) == (None, repo.MSG_CONTRACT_NOT_FOUND)


def test_create_scope_ok():
    sb = FakeClient([{"id": "k-1"}], [{"id": "s-1"}])
    assert repo.create_scope(sb, ESCOPO) == ({"id": "s-1"}, None)
    assert sb.last.call("insert")[0][0] == {**ESCOPO, "horas_manutencao": "10.5"}


def test_create_scope_duplicado():
    sb = FakeClient([{"id": "k-1"}], api_error("23505"))
    assert repo.create_scope(sb, ESCOPO) == (None, repo.MSG_DUPLICATE)


def test_update_scope_nao_envia_contrato_id_nem_id():
    sb = FakeClient([{"id": "s-1"}])
    assert repo.update_scope(sb, "s-1", {**ESCOPO, "id": "outro", "limite_requisicoes": 5}) == (True, None)
    payload = sb.last.call("update")[0][0]
    assert "contrato_id" not in payload and "id" not in payload
    assert payload["limite_requisicoes"] == 5


def test_update_scope_inexistente():
    assert repo.update_scope(FakeClient([]), "x", {"tipo_arquitetura": "A"}) == (False, repo.MSG_NOT_FOUND)
    assert repo.get_scope_by_id(FakeClient([]), "x") == (None, repo.MSG_NOT_FOUND)


def test_update_scope_trigger_contrato_id():
    sb = FakeClient(api_error("P0001", "O campo contrato_id não pode ser alterado."))
    assert repo.update_scope(sb, "s-1", {"tipo_arquitetura": "A"})[1] == "O campo contrato_id não pode ser alterado."


# Feature: crm-agentes-ia, Property 7: Escopo preserva contrato_id na edição
@given(
    changes=st.fixed_dictionaries(
        {},
        optional={
            "contrato_id": st.uuids().map(str),
            "id": st.uuids().map(str),
            "tipo_arquitetura": st.text(min_size=1, max_size=20),
            "limite_requisicoes": st.integers(1, 10_000_000),
            "modelos_permitidos": st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=3),
        },
    )
)
@settings(max_examples=100)
def test_property_7_update_nunca_envia_contrato_id(changes):
    sb = FakeClient([{"id": "s-1"}])
    ok, err = repo.update_scope(sb, "s-1", changes)
    technical = set(changes) & set(repo.TECHNICAL_FIELDS)
    if not technical:
        assert (ok, err) == (False, repo.MSG_NOTHING_TO_UPDATE) and sb.executed == []
    else:
        assert ok is True
        assert set(sb.last.call("update")[0][0]) == technical
