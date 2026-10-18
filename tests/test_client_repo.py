import httpx
from hypothesis import given, settings
from hypothesis import strategies as st

from repositories import client_repo as repo
from repositories.base import MSG_CONNECTION
from tests.fakes import FakeClient, api_error

CLIENTE = {
    "razao_social": "Acme IA Ltda",
    "cnpj": "12345678000190",
    "contato_nome": "Ana",
    "email": "ana@acme.com",
    "telefone": "11999990000",
}


def test_list_clients_sem_busca():
    sb = FakeClient([CLIENTE])
    assert repo.list_clients(sb) == ([CLIENTE], None)
    assert sb.last.target == "clientes"
    assert "eq" not in sb.last.names() and "ilike" not in sb.last.names()
    assert sb.last.call("order")[0] == ("razao_social",)


def test_list_clients_busca_parcial_em_razao_social():
    sb = FakeClient([])
    repo.list_clients(sb, "  acme ")
    assert sb.last.call("ilike")[0] == ("razao_social", "%acme%")


def test_list_clients_escapa_curingas():
    sb = FakeClient([])
    repo.list_clients(sb, "100%_ia")
    assert sb.last.call("ilike")[0] == ("razao_social", "%100\\%\\_ia%")


def test_list_clients_busca_exata_por_cnpj_formatado():
    sb = FakeClient([])
    repo.list_clients(sb, "12.345.678/0001-90")
    assert sb.last.call("eq")[0] == ("cnpj", "12345678000190")
    assert "ilike" not in sb.last.names()


def test_list_clients_falha_de_conexao():
    sb = FakeClient(httpx.ConnectError("offline"))
    assert repo.list_clients(sb) == (None, MSG_CONNECTION)


def test_get_client_inexistente():
    assert repo.get_client_by_id(FakeClient([]), "x") == (None, repo.MSG_NOT_FOUND)


def test_create_client_com_cnpj_duplicado_pre_verificacao():
    sb = FakeClient([{"id": "c-1"}])
    assert repo.create_client(sb, CLIENTE) == (None, repo.MSG_DUPLICATE_CNPJ)
    assert len(sb.executed) == 1  # não tentou inserir


def test_create_client_com_cnpj_duplicado_condicao_de_corrida():
    sb = FakeClient([], api_error("23505", "duplicate key value violates unique constraint"))
    assert repo.create_client(sb, CLIENTE) == (None, repo.MSG_DUPLICATE_CNPJ)


def test_create_client_envia_apenas_campos_permitidos():
    created = {**CLIENTE, "id": "c-1", "ativo": True}
    sb = FakeClient([], [created])
    payload = {**CLIENTE, "id": "forjado", "ativo": False, "created_at": "2000-01-01"}

    assert repo.create_client(sb, payload) == (created, None)
    inserted = sb.last.call("insert")[0][0]
    assert inserted == CLIENTE


def test_update_client_preserva_id_cnpj_created_at():
    sb = FakeClient([{"id": "c-1"}])
    ok, err = repo.update_client(
        sb, "c-1", {"razao_social": "Nova", "cnpj": "99999999999999", "id": "outro", "created_at": "x", "email": "n@x.com"}
    )
    assert (ok, err) == (True, None)
    assert sb.last.call("update")[0][0] == {"razao_social": "Nova", "email": "n@x.com"}
    assert sb.last.call("eq")[0] == ("id", "c-1")


def test_update_client_inexistente():
    assert repo.update_client(FakeClient([]), "x", {"razao_social": "A"}) == (False, repo.MSG_NOT_FOUND)


def test_update_client_sem_campos_editaveis():
    sb = FakeClient()
    assert repo.update_client(sb, "c-1", {"cnpj": "1"}) == (False, repo.MSG_NOTHING_TO_UPDATE)
    assert sb.executed == []


def test_deactivate_client_usa_rpc_e_nunca_delete():
    sb = FakeClient(2)
    assert repo.deactivate_client(sb, "c-1") == (2, None)
    assert sb.last.target == "rpc:inativar_cliente"
    assert sb.last.call("rpc")[0] == ("inativar_cliente", {"p_cliente_id": "c-1"})
    assert "delete" not in sb.all_method_names()


def test_deactivate_client_ja_inativo():
    sb = FakeClient(api_error("P0002", "Cliente não encontrado ou já inativo."))
    assert repo.deactivate_client(sb, "c-1") == (None, "Cliente não encontrado ou já inativo.")


def test_sessao_expirada_traduzida():
    sb = FakeClient(api_error("PGRST301", "JWT expired"))
    assert "login" in repo.list_clients(sb)[1].lower()


# Feature: crm-agentes-ia, Property 5: Inativação preserva registro
@given(client_id=st.uuids().map(str), cancelled=st.integers(min_value=0, max_value=100))
@settings(max_examples=100)
def test_property_5_inativacao_preserva_registro(client_id, cancelled):
    sb = FakeClient(cancelled)
    assert repo.deactivate_client(sb, client_id) == (cancelled, None)
    assert sb.all_method_names() == {"rpc"}  # nenhuma operação de DELETE/UPDATE direta


# Feature: crm-agentes-ia, Property 6: CNPJ único por cliente
@given(cnpj=st.text(alphabet="0123456789", min_size=14, max_size=14), race=st.booleans())
@settings(max_examples=100)
def test_property_6_cnpj_unico(cnpj, race):
    data = {**CLIENTE, "cnpj": cnpj}
    sb = FakeClient([], api_error("23505")) if race else FakeClient([{"id": "existente"}])
    created, err = repo.create_client(sb, data)
    assert created is None and err == repo.MSG_DUPLICATE_CNPJ
