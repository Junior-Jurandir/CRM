from datetime import date
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from repositories import contract_repo as repo
from tests.fakes import FakeClient, api_error

CONTRATO = {
    "cliente_id": "c-1",
    "titulo_projeto": "Agente SAC",
    "status": "Ativo",
    "data_inicio": date(2026, 1, 1),
    "data_fim": date(2026, 12, 31),
    "valor_mensal": Decimal("1500.50"),
    "setup_fee": Decimal("0"),
}


def test_list_contracts_inclui_razao_social_e_filtra_por_cliente():
    sb = FakeClient([])
    repo.list_contracts(sb, "c-1")
    assert sb.last.call("select")[0] == ("*, clientes(razao_social)",)
    assert sb.last.call("eq")[0] == ("cliente_id", "c-1")


def test_list_contracts_sem_filtro():
    sb = FakeClient([])
    repo.list_contracts(sb)
    assert "eq" not in sb.last.names()


def test_create_contract_serializa_datas_e_decimais():
    sb = FakeClient([{"id": "k-1"}])
    assert repo.create_contract(sb, {**CONTRATO, "id": "forjado"}) == ({"id": "k-1"}, None)
    assert sb.last.call("insert")[0][0] == {
        "cliente_id": "c-1",
        "titulo_projeto": "Agente SAC",
        "status": "Ativo",
        "data_inicio": "2026-01-01",
        "data_fim": "2026-12-31",
        "valor_mensal": "1500.50",
        "setup_fee": "0",
    }


def test_create_contract_cliente_inativo_traduzido_do_trigger():
    sb = FakeClient(api_error("P0001", "O cliente selecionado está inativo."))
    assert repo.create_contract(sb, CONTRATO) == (None, "O cliente selecionado está inativo.")


def test_create_contract_violacao_de_check():
    sb = FakeClient(api_error("23514", 'violates check constraint "contratos_datas_validas"'))
    assert repo.create_contract(sb, CONTRATO)[1].startswith("Dados inválidos")


def test_update_contract_nao_envia_cliente_id():
    sb = FakeClient([{"id": "k-1"}])
    assert repo.update_contract(sb, "k-1", {"status": "Renovação Pendente", "cliente_id": "outro"}) == (True, None)
    assert sb.last.call("update")[0][0] == {"status": "Renovação Pendente"}


def test_contrato_inexistente():
    assert repo.get_contract_by_id(FakeClient([]), "x") == (None, repo.MSG_NOT_FOUND)
    assert repo.update_contract(FakeClient([]), "x", {"status": "Ativo"}) == (False, repo.MSG_NOT_FOUND)
    assert repo.cancel_contract(FakeClient([]), "x") == (False, repo.MSG_NOT_FOUND)


def test_cancel_contract_usa_update_e_nunca_delete():
    sb = FakeClient([{"id": "k-1", "status": "Cancelado"}])
    assert repo.cancel_contract(sb, "k-1") == (True, None)
    assert sb.last.call("update")[0][0] == {"status": "Cancelado"}
    assert "delete" not in sb.all_method_names()


# Feature: crm-agentes-ia, Property 9: Cancelamento de contrato não exclui registro
@given(contract_id=st.uuids().map(str))
@settings(max_examples=100)
def test_property_9_cancelamento_preserva_registro(contract_id):
    sb = FakeClient([{"id": contract_id, "status": "Cancelado"}])
    assert repo.cancel_contract(sb, contract_id) == (True, None)
    assert sb.all_method_names() == {"update", "eq"}
    assert sb.last.call("update")[0][0] == {"status": "Cancelado"}
