"""Smoke tests das telas com streamlit.testing (sem rede).

O cliente Supabase da sessão é um MagicMock; os serviços de dados são
substituídos por dados fixos para exercitar a renderização das páginas.
"""

import time
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from streamlit.testing.v1 import AppTest

HOJE = date.today()
CLIENTES = [
    {"id": "c-1", "razao_social": "Acme IA", "cnpj": "12345678000190", "contato_nome": "Ana", "email": "ana@acme.com",
     "telefone": None, "ativo": True, "inativado_em": None, "created_at": "2026-01-01T10:00:00+00:00"},
    {"id": "c-2", "razao_social": "Beta Bots", "cnpj": "98765432000110", "contato_nome": "Bia", "email": "bia@beta.com",
     "telefone": "11", "ativo": False, "inativado_em": "2026-05-01T10:00:00+00:00", "created_at": "2026-01-02T10:00:00+00:00"},
]
CONTRATOS = [
    {"id": "k-1", "cliente_id": "c-1", "titulo_projeto": "Agente SAC", "status": "Ativo",
     "data_inicio": "2026-01-01", "data_fim": (HOJE + timedelta(days=5)).isoformat(), "valor_mensal": 1500.5,
     "setup_fee": 0, "clientes": {"razao_social": "Acme IA"}},
    {"id": "k-2", "cliente_id": "c-1", "titulo_projeto": "Agente Vendas", "status": "Em Implantação",
     "data_inicio": "2026-01-01", "data_fim": (HOJE + timedelta(days=200)).isoformat(), "valor_mensal": "800.00",
     "setup_fee": "5000.00", "clientes": {"razao_social": "Acme IA"}},
]


def logged_session(at: AppTest, role: str = "admin") -> MagicMock:
    sb = MagicMock()
    sb.auth.get_session.return_value = SimpleNamespace(expires_at=int(time.time()) + 3600)
    at.session_state["sb"] = sb
    at.session_state["user"] = {"id": "u-1", "email": "ana@empresa.com", "nome": "Ana", "role": role}
    at.session_state["login_at"] = datetime.now(timezone.utc)
    return sb


@pytest.fixture
def fake_data():
    with patch("services.client_service.client_repo.list_clients", return_value=(CLIENTES, None)), \
         patch("services.contract_service.contract_repo.list_contracts", return_value=(CONTRATOS, None)), \
         patch("services.scope_service.scope_repo.get_scope_by_contract", return_value=(None, None)):
        from services.cache_utils import clear_all_caches
        clear_all_caches()
        yield
        clear_all_caches()


ROOT = Path(__file__).resolve().parent.parent


def run(page: str, role: str | None = "admin") -> AppTest:
    """Executa a partir do entrypoint (app.py), como no app real, e troca para a página."""
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    if role:
        logged_session(at, role)
    if page == "app.py":
        return at.run()
    return at.switch_page(page).run()


def test_login_renderiza():
    at = run("app.py", role=None)
    assert not at.exception
    assert [t.label for t in at.text_input] == ["E-mail", "Senha"]
    assert at.button[0].label == "Entrar"


def test_login_invalido_mostra_erro_generico():
    at = run("app.py", role=None)
    at.text_input[0].input("sem-arroba")
    at.text_input[1].input("12345678")
    at.button[0].click().run()
    assert not at.exception
    assert at.error[0].value == "E-mail ou senha inválidos."


@pytest.mark.parametrize("page", ["pages/1_Dashboard.py", "pages/2_Clientes.py", "pages/3_Contratos.py", "pages/4_Configuracoes.py"])
def test_paginas_protegidas_sem_login_redirecionam_para_login(page):
    at = run(page, role=None)
    assert not at.exception
    assert [t.label for t in at.text_input] == ["E-mail", "Senha"]


def test_dashboard(fake_data):
    at = run("pages/1_Dashboard.py")
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["MRR total"] == "R$ 1.500,50"
    assert metrics["Contratos ativos"] == "1"
    assert metrics["Em Implantação"] == "1"
    assert at.dataframe  # alertas de vencimento (contrato a 5 dias)


def test_dashboard_falha_de_leitura_mostra_recarregar():
    with patch("services.contract_service.contract_repo.list_contracts", return_value=(None, "Falha ao carregar dados. Verifique a conexão.")):
        from services.contract_service import list_contracts
        list_contracts.clear()
        at = run("pages/1_Dashboard.py")
    assert not at.exception
    assert "Falha no carregamento" in at.error[0].value
    assert any(b.label == "Recarregar" for b in at.button)


def test_clientes(fake_data):
    at = run("pages/2_Clientes.py")
    assert not at.exception
    df = at.dataframe[0].value
    assert list(df["Status"]) == ["Ativo", "Inativo"]
    assert df["CNPJ"][0] == "12.345.678/0001-90"


def test_contratos(fake_data):
    at = run("pages/3_Contratos.py")
    assert not at.exception
    df = at.dataframe[0].value
    assert df["Alerta"][0] == "🔴 Crítico · 5 dias"
    assert df["Valor mensal"][1] == "R$ 800,00"


def test_configuracoes_admin_ve_cadastro():
    at = run("pages/4_Configuracoes.py", role="admin")
    assert not at.exception
    assert any(b.label == "Cadastrar membro" for b in at.button)


def test_configuracoes_membro_nao_ve_cadastro():
    at = run("pages/4_Configuracoes.py", role="membro")
    assert not at.exception
    assert not any(b.label == "Cadastrar membro" for b in at.button)
    assert "restrito a administradores" in at.info[0].value
