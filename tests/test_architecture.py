"""Verificação estática da separação de camadas (Req 7.5, 9.1)."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPOSITORIES = sorted((ROOT / "repositories").glob("*.py"))
UI_FILES = sorted([*(ROOT / "pages").glob("*.py"), *([ROOT / "app.py"] if (ROOT / "app.py").exists() else [])])
APP_DIRS = ("app.py", "config.py", "pages", "repositories", "services", "auth", "utils")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def app_python_files() -> list[Path]:
    files = []
    for entry in APP_DIRS:
        path = ROOT / entry
        files.extend([path] if path.is_file() else sorted(path.glob("*.py")) if path.is_dir() else [])
    return files


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_existem_repositorios_para_verificar():
    assert {p.name for p in REPOSITORIES} >= {"client_repo.py", "contract_repo.py", "scope_repo.py"}


@pytest.mark.parametrize("path", REPOSITORIES, ids=rel)
def test_repositorios_nao_importam_streamlit(path):
    offending = {m for m in imported_modules(path) if m == "streamlit" or m.startswith("streamlit.")}
    assert not offending, f"{rel(path)} importa {offending}"
    assert not re.search(r"\bst\.", path.read_text(encoding="utf-8")), f"{rel(path)} referencia st.*"


FORBIDDEN_IN_UI = ("supabase", "postgrest", "supabase_auth", "repositories", "utils.supabase_client")


@pytest.mark.parametrize("path", UI_FILES, ids=rel)
def test_interface_nao_acessa_supabase_nem_repositorios(path):
    offending = {
        m for m in imported_modules(path) if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_IN_UI)
    }
    assert not offending, f"{rel(path)} importa {offending}"
    source = path.read_text(encoding="utf-8")
    for pattern in (r"\.auth\.", r"\.table\(", r"\.rpc\("):
        assert not re.search(pattern, source), f"{rel(path)} chama o cliente Supabase diretamente ({pattern})"


def test_service_role_confinada_ao_modulo_de_autenticacao():
    allowed = {"utils/supabase_client.py", "auth/authentication.py"}
    users = {rel(p) for p in app_python_files() if "create_admin_client" in p.read_text(encoding="utf-8")}
    assert users <= allowed, f"create_admin_client usado fora do permitido: {users - allowed}"
    key_users = {rel(p) for p in app_python_files() if "SUPABASE_SERVICE_ROLE_KEY" in p.read_text(encoding="utf-8")}
    assert key_users <= {"config.py", "utils/supabase_client.py"}, key_users


def test_service_role_nunca_vai_para_session_state():
    source = (ROOT / "auth" / "authentication.py").read_text(encoding="utf-8")
    assert not re.search(r"session_state\[[^\]]*\]\s*=\s*admin", source)
    assert "SERVICE_ROLE" not in source


def test_nenhum_delete_nos_repositorios():
    """Auditabilidade: registros nunca são excluídos pela aplicação."""
    for path in REPOSITORIES:
        assert ".delete(" not in path.read_text(encoding="utf-8"), rel(path)
