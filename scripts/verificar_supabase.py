"""Verificação do projeto Supabase (integração real).

Uso:
    .venv\\Scripts\\python scripts\\verificar_supabase.py           # só checagens anônimas
    .venv\\Scripts\\python scripts\\verificar_supabase.py --login   # + checagens autenticadas

Parte 1 (sem credenciais): conexão e bloqueio do papel anon pelo RLS.
Parte 2 (--login): pede e-mail e senha no terminal (não ficam salvos),
cria dados de teste marcados como "[VERIFICACAO]", valida constraints,
triggers, RPC de inativação em cascata e imutabilidade do escopo,
e remove os dados de teste ao final.
"""

import getpass
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from postgrest.exceptions import APIError  # noqa: E402

import config  # noqa: E402
from utils.supabase_client import SupabaseConfigError, create_user_client  # noqa: E402

TABLES = ("clientes", "contratos", "escopo_agentes")
results: list[tuple[bool, str]] = []


def check(ok: bool, message: str, detail: str = "") -> bool:
    results.append((ok, message))
    print(f"  [{'OK' if ok else 'FALHOU'}] {message}" + (f" — {detail}" if detail and not ok else ""))
    return ok


def expect_api_error(fn, contains: str | None = None) -> tuple[bool, str]:
    try:
        fn()
    except APIError as exc:
        text = f"{exc.code} {exc.message}"
        if (exc.code or "").startswith("PGRST20"):
            return False, f"{text} (objeto não encontrado pela API — não é bloqueio de RLS)"
        return (contains is None or contains.lower() in text.lower()), text
    return False, "operação foi aceita"


def part_anon() -> bool:
    print("\n== Parte 1: conexão e RLS para usuário anônimo ==")
    try:
        sb = create_user_client()
    except SupabaseConfigError as exc:
        check(False, "Configuração do .env", str(exc))
        return False
    check(True, f"Configuração carregada ({config.SUPABASE_URL})")

    for table in TABLES:
        try:
            rows = sb.table(table).select("*").limit(1).execute().data
            check(rows == [], f"anon não lê '{table}'", f"retornou {len(rows)} registro(s)")
        except APIError as exc:
            # 42501 = permission denied (REVOKE) / 42P01 = tabela inexistente
            check(exc.code == "42501", f"anon não lê '{table}'", f"{exc.code} {exc.message}")

    ok, detail = expect_api_error(
        lambda: sb.table("clientes").insert(_client_payload("00000000000000")).execute()
    )
    check(ok, "anon não insere em 'clientes'", detail)

    ok, detail = expect_api_error(
        lambda: sb.rpc("inativar_cliente", {"p_cliente_id": "00000000-0000-0000-0000-000000000000"}).execute()
    )
    check(ok, "anon não executa a RPC inativar_cliente", detail)
    return True


def _client_payload(cnpj: str) -> dict:
    return {
        "razao_social": "[VERIFICACAO] Cliente de teste",
        "cnpj": cnpj,
        "contato_nome": "Teste",
        "email": "teste@exemplo.com",
    }


def _contract_payload(cliente_id: str, status: str) -> dict:
    hoje = date.today()
    return {
        "cliente_id": cliente_id,
        "titulo_projeto": f"[VERIFICACAO] {status}",
        "status": status,
        "data_inicio": hoje.isoformat(),
        "data_fim": (hoje + timedelta(days=365)).isoformat(),
        "valor_mensal": "1500.50",
        "setup_fee": "0",
    }


def part_auth() -> None:
    print("\n== Parte 2: checagens autenticadas ==")
    email = input("  E-mail: ").strip()
    password = getpass.getpass("  Senha (não aparece ao digitar): ")

    sb = create_user_client()
    try:
        response = sb.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:  # noqa: BLE001
        check(False, "Login", str(exc))
        return
    finally:
        password = None  # noqa: F841
    check(response.session is not None, "Login com Supabase Auth")
    role = (response.user.app_metadata or {}).get("role")
    check(role == "admin", "Usuário tem perfil Admin (app_metadata.role)", f"role atual: {role!r} — rode sql/04_bootstrap_admin.sql")

    for table in TABLES:
        try:
            sb.table(table).select("id").limit(1).execute()
            check(True, f"autenticado lê '{table}'")
        except APIError as exc:
            check(False, f"autenticado lê '{table}'", f"{exc.code} {exc.message}")

    cnpj = "99" + "".join(random.choices("0123456789", k=12))
    created_ids: dict[str, list[str]] = {t: [] for t in TABLES}
    try:
        cliente = sb.table("clientes").insert(_client_payload(cnpj)).execute().data[0]
        created_ids["clientes"].append(cliente["id"])
        check(True, "Insere cliente")

        ok, detail = expect_api_error(lambda: sb.table("clientes").insert(_client_payload(cnpj)).execute(), "23505")
        check(ok, "CNPJ duplicado é rejeitado (UNIQUE)", detail)

        ok, detail = expect_api_error(lambda: sb.table("clientes").insert(_client_payload("123")).execute(), "23514")
        check(ok, "CNPJ fora do formato é rejeitado (CHECK)", detail)

        bad = _contract_payload(cliente["id"], "Ativo") | {"data_fim": date.today().isoformat()}
        ok, detail = expect_api_error(lambda: sb.table("contratos").insert(bad).execute(), "23514")
        check(ok, "data_fim <= data_inicio é rejeitada (CHECK)", detail)

        bad = _contract_payload(cliente["id"], "Ativa")
        ok, detail = expect_api_error(lambda: sb.table("contratos").insert(bad).execute(), "23514")
        check(ok, "Status inválido é rejeitado (CHECK)", detail)

        contratos = {}
        for status in ("Ativo", "Em Implantação", "Renovação Pendente"):
            row = sb.table("contratos").insert(_contract_payload(cliente["id"], status)).execute().data[0]
            created_ids["contratos"].append(row["id"])
            contratos[status] = row
        check(True, "Insere contratos (Ativo, Em Implantação, Renovação Pendente)")
        check(str(contratos["Ativo"]["valor_mensal"]) in ("1500.5", "1500.50"), "valor_mensal preservado", str(contratos["Ativo"]["valor_mensal"]))

        escopo = (
            sb.table("escopo_agentes")
            .insert(
                {
                    "contrato_id": contratos["Ativo"]["id"],
                    "tipo_arquitetura": "RAG",
                    "limite_requisicoes": 1000,
                    "horas_manutencao": 10.5,
                    "modelos_permitidos": ["claude-opus-5-5"],
                }
            )
            .execute()
            .data[0]
        )
        created_ids["escopo_agentes"].append(escopo["id"])
        check(True, "Insere escopo")

        ok, detail = expect_api_error(
            lambda: sb.table("escopo_agentes").update({"contrato_id": contratos["Em Implantação"]["id"]}).eq("id", escopo["id"]).execute(),
            "contrato_id",
        )
        check(ok, "Trigger impede troca de contrato_id do escopo", detail)

        ok, detail = expect_api_error(
            lambda: sb.table("escopo_agentes").update({"modelos_permitidos": []}).eq("id", escopo["id"]).execute(), "23514"
        )
        check(ok, "modelos_permitidos vazio é rejeitado (CHECK)", detail)

        cancelados = sb.rpc("inativar_cliente", {"p_cliente_id": cliente["id"]}).execute().data
        check(cancelados == 2, "RPC inativar_cliente cancela 2 contratos", f"retornou {cancelados!r}")

        cli = sb.table("clientes").select("ativo, inativado_em").eq("id", cliente["id"]).execute().data[0]
        check(cli["ativo"] is False and cli["inativado_em"], "Cliente inativado e registro preservado")

        status = {
            r["titulo_projeto"]: r["status"]
            for r in sb.table("contratos").select("titulo_projeto, status").eq("cliente_id", cliente["id"]).execute().data
        }
        check(
            status.get("[VERIFICACAO] Ativo") == "Cancelado"
            and status.get("[VERIFICACAO] Em Implantação") == "Cancelado"
            and status.get("[VERIFICACAO] Renovação Pendente") == "Renovação Pendente",
            "Cascata: Ativo/Em Implantação → Cancelado; Renovação Pendente mantido",
            str(status),
        )

        ok, detail = expect_api_error(lambda: sb.rpc("inativar_cliente", {"p_cliente_id": cliente["id"]}).execute(), "P0002")
        check(ok, "Inativar cliente já inativo é rejeitado", detail)

        ok, detail = expect_api_error(
            lambda: sb.table("contratos").insert(_contract_payload(cliente["id"], "Ativo")).execute(), "inativo"
        )
        check(ok, "Trigger impede contrato para cliente inativo", detail)

        try:
            refreshed = sb.auth.refresh_session()
            check(refreshed.session is not None, "Renovação do token (refresh_session)")
        except Exception as exc:  # noqa: BLE001
            check(False, "Renovação do token (refresh_session)", str(exc))
    except APIError as exc:
        check(False, "Fluxo de dados de teste interrompido", f"{exc.code} {exc.message}")
    finally:
        print("\n  Removendo dados de teste...")
        for table in ("escopo_agentes", "contratos", "clientes"):
            for row_id in created_ids[table]:
                try:
                    sb.table(table).delete().eq("id", row_id).execute()
                except APIError as exc:
                    print(f"  aviso: não removeu {table} {row_id}: {exc.message}")
        try:
            sb.auth.sign_out()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    started = time.time()
    if part_anon() and "--login" in sys.argv:
        part_auth()
    failed = [m for ok, m in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} verificações OK em {time.time() - started:.1f}s")
    for message in failed:
        print(f"  FALHOU: {message}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
