# Implementation Plan: CRM para Agentes de IA

## Overview

Implementação incremental do CRM para Agentes de IA em Python + Streamlit com backend Supabase (PostgreSQL), na raiz do projeto (`C:\Dev\CRM`). A construção segue a arquitetura em camadas do design: configuração → utilitários → autenticação → repositórios → serviços → páginas UI. Cada etapa produz código integrado e testável antes de avançar.

O projeto Supabase ainda não existe: os scripts SQL são gerados no repositório e executados pelo usuário no SQL Editor quando o projeto for criado. Até lá, toda a verificação é feita com testes automatizados usando mocks do cliente Supabase.

## Tasks

- [x] 1. Configurar estrutura do projeto e dependências
  - Criar na raiz as pastas `pages/`, `repositories/`, `services/`, `auth/`, `utils/`, `sql/`, `tests/`, `.streamlit/`
  - Criar `__init__.py` em `repositories/`, `services/`, `auth/`, `utils/`
  - Verificar compatibilidade das dependências com o Python disponível; se necessário, documentar o uso de ambiente virtual com Python 3.12
  - Criar `requirements.txt` com versões exatas fixadas de `streamlit`, `supabase`, `python-dotenv`, `pytest`, `hypothesis`, `pytest-mock`
  - Criar `.env.example` com `SUPABASE_URL`, `SUPABASE_ANON_KEY` e `SUPABASE_SERVICE_ROLE_KEY` (com aviso de uso exclusivo no servidor)
  - Criar `.gitignore` incluindo `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.hypothesis/`
  - Criar `.streamlit/config.toml` com tema dark corporativo
  - Criar `README.md` com instruções de ambiente, criação do projeto Supabase, execução dos scripts SQL, execução do app e dos testes
  - Criar `pytest.ini` / `conftest.py` configurando o path do projeto
  - _Requisitos: 9.1, 9.2, 10.1_

- [x] 2. Criar scripts SQL do banco de dados
  - [x] 2.1 Criar `sql/01_schema.sql` com as tabelas `clientes`, `contratos` e `escopo_agentes`
    - Todas as colunas, tipos, constraints (UNIQUE de CNPJ, CHECK de formato do CNPJ, e-mail, status, datas, valores, limites e `modelos_permitidos`) conforme o design
    - Extensão `pg_trgm` e índice trigram `idx_clientes_razao_social`; índices `idx_contratos_cliente_id`, `idx_contratos_status`, `idx_contratos_data_fim`
    - Script idempotente (`IF NOT EXISTS` onde aplicável)
    - _Requisitos: 2.1, 3.1, 3.3, 3.4, 3.6, 3.8, 4.1, 4.4, 4.6, 4.8_

  - [x] 2.2 Criar `sql/02_functions_triggers.sql`
    - Função RPC `inativar_cliente(p_cliente_id uuid)` — `SECURITY INVOKER`, atômica, retorna a quantidade de contratos cancelados, erro `P0002` se o cliente for inexistente ou já inativo; `GRANT EXECUTE` apenas para `authenticated`
    - Trigger `trg_contratos_cliente_ativo` (BEFORE INSERT em `contratos`) rejeitando cliente inativo
    - Trigger `trg_escopo_contrato_imutavel` (BEFORE UPDATE em `escopo_agentes`) rejeitando troca de `contrato_id`
    - _Requisitos: 2.5, 2.6, 2.7, 2.8, 3.2, 4.11_

  - [x] 2.3 Criar `sql/03_rls.sql`
    - `ENABLE ROW LEVEL SECURITY` nas três tabelas
    - Políticas `FOR ALL TO authenticated USING (true) WITH CHECK (true)`; nenhuma política para `anon`
    - _Requisitos: 7.1, 7.2, 7.6_

  - [x] 2.4 Criar `sql/04_bootstrap_admin.sql`
    - `UPDATE auth.users` definindo `raw_app_meta_data.role = 'admin'` para o e-mail do primeiro Admin (placeholder a substituir)
    - _Requisitos: 11.6_

- [x] 3. Implementar configuração e utilitários base
  - [x] 3.1 Implementar `config.py`
    - Ler `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (opcional) via `python-dotenv`, sem `st.*`
    - Constantes `CACHE_TTL = 300`, `SESSION_MAX_HOURS = 8`, `TOKEN_REFRESH_MARGIN_SECONDS = 60`, `LOGIN_MAX_ATTEMPTS = 5`, `LOGIN_LOCKOUT_MINUTES = 15`
    - _Requisitos: 1.3, 1.6, 8.1_

  - [x] 3.2 Implementar `utils/supabase_client.py` — fábrica de clientes (não singleton)
    - `create_user_client()` — novo cliente com chave anon, `auto_refresh_token=False`, `persist_session=False`
    - `create_admin_client()` — cliente com `service_role`; erro claro se a chave não estiver configurada
    - _Requisitos: 1.8, 1.9, 7.3, 7.5_

  - [x] 3.3 Implementar `utils/validators.py`
    - `validate_cnpj`, `normalize_cnpj` (remove pontuação), `validate_email`, `validate_password_format` (≥ 8)
    - `validate_contract_dates`, `validate_valor_mensal`, `validate_setup_fee` (com `Decimal`, máx. 2 casas)
    - `validate_status`, `validate_text_length`
    - `validate_limite_requisicoes`, `validate_horas_manutencao`, `validate_modelos_permitidos`
    - Todas retornam `tuple[bool, str | None]` com mensagens do design
    - _Requisitos: 1.1, 2.1, 2.3, 3.3, 3.4, 3.6, 3.7, 3.8, 3.9, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

  - [x] 3.4 Escrever testes unitários para `validators.py`
    - Bordas de CNPJ, e-mail, senha, datas, valores monetários (incluindo 3 casas decimais), status, limites do escopo e `modelos_permitidos` (vazio, 51 itens, item de 101 chars, item não-string)
    - _Requisitos: 2.3, 3.3, 3.4, 3.6, 3.8, 4.4, 4.6, 4.8, 4.9_

  - [x] 3.5 Escrever property tests para `validators.py` (Hypothesis)
    - **Property 1: Validação de datas de contrato** — **Valida: Requisito 3.4**
    - **Property 8: Validação de limites numéricos do escopo** (`limite_requisicoes` e `horas_manutencao`) — **Valida: Requisitos 4.4, 4.5, 4.6, 4.7**
    - **Property 10: Valor monetário com duas casas decimais** — **Valida: Requisitos 3.6, 3.8**

  - [x] 3.6 Implementar `utils/formatters.py`
    - `format_currency(value) -> str` ("R$ 1.234,56"), `format_date(d) -> str` ("DD/MM/AAAA"), `format_cnpj(cnpj) -> str` ("XX.XXX.XXX/XXXX-XX")
    - Aceitar `Decimal`, `str`, `int`, `float` e datas em string ISO
    - _Requisitos: 6.1_

  - [x] 3.7 Escrever testes unitários para `formatters.py`
    - Zero, milhares, milhões, valor em string, data ISO, CNPJ
    - _Requisitos: 6.1_

- [x] 4. Implementar módulo de autenticação
  - [x] 4.1 Implementar `auth/login_guard.py` (puro, sem `st.*`)
    - Classe `LoginGuard` com relógio injetável, `threading.Lock`, normalização de e-mail, `check`, `register_failure`, `register_success`
    - _Requisitos: 1.6_

  - [x] 4.2 Escrever testes para `login_guard.py` (unitários + Hypothesis)
    - 4 falhas não bloqueiam; 5ª bloqueia; expira após 15 min; sucesso zera; normalização; isolamento entre e-mails
    - **Property 11: Bloqueio de login após 5 falhas consecutivas** — **Valida: Requisito 1.6**

  - [x] 4.3 Implementar `auth/authentication.py`
    - `LoginGuard` compartilhado por processo via `@st.cache_resource`
    - `login()` — valida formato, verifica bloqueio, cria cliente da sessão, autentica e grava `sb`, `user` e `login_at` em `st.session_state`; mensagem de erro genérica
    - `logout()`, `get_current_user()`, `get_session_client()`
    - `is_session_valid()` — limite de 8h desde o login + renovação do token quando faltar ≤ 60 s; falha no refresh invalida
    - `require_auth()` — retorna o cliente da sessão ou faz logout + `st.switch_page("app.py")`
    - `update_profile(nome, email)` — `auth.update_user`, aviso de confirmação quando o e-mail muda
    - Perfis: `ROLE_ADMIN`, `ROLE_MEMBER`, `extract_role(user)` (somente `app_metadata.role`), `is_admin()`; `role` gravado em `st.session_state["user"]`
    - `render_user_sidebar()` — nome, e-mail, perfil e botão "Sair"
    - `create_team_member(nome, email, role="membro")` — revalida no servidor que o solicitante é Admin via `sb.auth.get_user()`; valida `role`; cliente admin sob demanda; senha `secrets.token_urlsafe(12)`, `email_confirm=True`, `app_metadata.role`; retorna a senha temporária sem persisti-la
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 7.3, 7.4, 7.5, 9.3, 9.4, 9.5, 11.1, 11.2, 11.4, 11.5, 11.7_

  - [x] 4.4 Escrever testes unitários para `auth/authentication.py`
    - Login válido grava sessão; inválido retorna erro genérico e registra falha; bloqueio retorna mensagem
    - Sessão > 8h inválida; dentro de 8h válida; refresh chamado perto da expiração; falha no refresh invalida
    - Logout limpa a sessão mesmo se `sign_out` falhar
    - `create_team_member` sem `service_role` → erro; com sucesso → senha gerada e não gravada no `session_state`
    - `create_team_member` por Membro → permissão negada, sem criar cliente admin; `user_metadata.role="admin"` não concede permissão; role inválido rejeitado
    - **Property 13: Apenas Admin cadastra membros** (Hypothesis sobre valores de `app_metadata.role`) — **Valida: Requisitos 11.1, 11.2, 11.4**
    - _Requisitos: 1.1, 1.2, 1.3, 1.5, 1.6, 1.10, 9.4, 11.4_

- [x] 5. Checkpoint — Verificar módulos base e autenticação
  - Garantir que todos os testes de validators, formatters, login_guard e authentication passam; perguntar ao usuário se há dúvidas antes de prosseguir.

- [x] 6. Implementar repositórios de acesso a dados (sem `st.*`, cliente injetado)
  - [x] 6.1 Implementar `repositories/client_repo.py`
    - `list_clients(client, search)` — exata por CNPJ (14 dígitos após normalização) ou ILIKE em `razao_social`
    - `get_client_by_id`, `cnpj_exists`, `create_client` (pré-verificação + tratamento de `23505`)
    - `update_client` — envia só `razao_social`, `contato_nome`, `email`, `telefone`
    - `deactivate_client` — via RPC `inativar_cliente`; traduz `P0002`
    - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 2.8, 2.9_

  - [x] 6.2 Escrever testes unitários para `client_repo.py` (mock do Supabase)
    - CNPJ duplicado (pré-verificação e `23505`); `update_client` descarta `id`/`cnpj`/`created_at`; `deactivate_client` chama a RPC e nunca DELETE; busca por CNPJ vs. ILIKE; falha de conexão → mensagem
    - **Property 5** e **Property 6** — **Valida: Requisitos 2.3, 2.5**

  - [x] 6.3 Implementar `repositories/contract_repo.py`
    - `list_contracts(client, client_id)` com `clientes(razao_social)`; `get_contract_by_id`; `create_contract` (traduz erro do trigger de cliente inativo); `update_contract` (sem `cliente_id`); `cancel_contract` (UPDATE)
    - _Requisitos: 3.1, 3.2, 3.5, 3.10_

  - [x] 6.4 Escrever testes unitários para `contract_repo.py` (mock do Supabase)
    - Cliente inativo → erro traduzido; `cancel_contract` usa UPDATE e nunca DELETE; contrato inexistente → "Contrato não encontrado."
    - **Property 9** — **Valida: Requisito 3.10**

  - [x] 6.5 Implementar `repositories/scope_repo.py`
    - `get_scope_by_contract`, `get_scope_by_id`, `create_scope` (verifica contrato existente), `update_scope` (envia apenas campos técnicos)
    - _Requisitos: 4.1, 4.2, 4.3, 4.10, 4.12_

  - [x] 6.6 Escrever testes unitários para `scope_repo.py` (mock do Supabase)
    - `create_scope` com contrato inexistente → erro; `update_scope` não envia `contrato_id`/`id`; scope inexistente → "Escopo não encontrado."
    - **Property 7** — **Valida: Requisitos 4.10, 4.11**

- [x] 7. Implementar serviços
  - [x] 7.1 Implementar `services/alert_service.py`
    - `AlertLevel`, `ALERT_ELIGIBLE_STATUSES`, `days_remaining`, `get_alert_level`, `get_expiring_contracts`, `alert_badge` (ícone e texto distintos por nível)
    - _Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.2_

  - [x] 7.2 Escrever testes unitários para `alert_service.py`
    - hoje → EXPIRED; +1/+7 → CRITICAL; +8/+15 → URGENT; +16/+30 → ATTENTION; +31 → NONE; "Cancelado" e "Em Implantação" → NONE; data em string ISO
    - _Requisitos: 5.1, 5.2, 5.3, 5.5, 5.6_

  - [x] 7.3 Escrever property tests para `alert_service.py` (Hypothesis)
    - **Property 2** — **Valida: Requisitos 5.1, 5.2, 5.3, 5.4, 5.6**
    - **Property 3** — **Valida: Requisito 5.5**

  - [x] 7.4 Implementar `services/dashboard_service.py`
    - `calculate_mrr` (Decimal), `count_by_status` (sempre 4 chaves), `expiration_distribution` (5 faixas, exclui "Cancelado")
    - _Requisitos: 6.1, 6.2, 6.3_

  - [x] 7.5 Escrever testes unitários para `dashboard_service.py`
    - Lista vazia; só cancelados; mix; valores em string; contagens; bordas das faixas
    - _Requisitos: 6.1, 6.2, 6.3_

  - [x] 7.6 Escrever property tests para `dashboard_service.py` (Hypothesis)
    - **Property 4** — **Valida: Requisito 6.1**

  - [x] 7.7 Implementar `services/result.py`, `services/cache_utils.py` e os serviços de dados `client_service.py`, `contract_service.py`, `scope_service.py`
    - Leituras com `@st.cache_data(ttl=CACHE_TTL)` e parâmetro `_sb`; lançam exceção em falha (não cacheiam erro)
    - Escritas: validação → repositório → `safe_clear` das entidades afetadas → `ServiceResult`
    - `deactivate_client` invalida clientes **e** contratos
    - `update_scope` rejeita `contrato_id` diferente do original e `scope_id` inexistente
    - `create_contract` verifica cliente ativo antes de chamar o repositório
    - _Requisitos: 2.3, 2.6, 3.2, 3.4, 3.7, 3.9, 4.3, 4.5, 4.7, 4.9, 4.11, 4.12, 8.1, 8.2, 8.3, 8.4_

  - [x] 7.8 Escrever testes para os serviços de dados
    - Escrita bem-sucedida chama `.clear()`; escrita com erro não chama; exceção no `.clear()` gera `warning` e mantém o resultado; inativação limpa clientes e contratos; validação falha não chama o repositório
    - **Property 12** — **Valida: Requisitos 8.2, 8.3**

- [x] 8. Implementar testes de arquitetura (`tests/test_architecture.py`)
  - Nenhum arquivo em `repositories/` importa `streamlit`
  - `app.py` e `pages/*.py` não importam `supabase`, `repositories` nem `utils.supabase_client`
  - `create_admin_client` só é referenciado em `auth/authentication.py` (e em sua definição)
  - _Requisitos: 7.5, 9.1_

- [x] 9. Checkpoint — Verificar serviços e repositórios
  - Garantir que todos os testes de repositórios, serviços e arquitetura passam; perguntar ao usuário se há dúvidas antes de prosseguir.

- [x] 10. Implementar página de Login (`app.py`)
  - Formulário centralizado (`st.form`) com E-mail e Senha; chama `authentication.login()`
  - Erro genérico; mensagem de bloqueio com tempo restante
  - Redireciona para o Dashboard se já houver sessão válida ou após login
  - _Requisitos: 1.1, 1.2, 1.6, 1.7_

- [x] 11. Implementar página Dashboard (`pages/1_Dashboard.py`)
  - `sb = require_auth()`; métricas de MRR e contratos ativos; contagens por status em 4 colunas; `st.bar_chart` de vencimentos; lista de alertas com `alert_badge`
  - Falha de leitura → `st.error` + botão "Recarregar"
  - Todas as páginas autenticadas chamam `render_user_sidebar()` (nome, e-mail, perfil, "Sair")
  - _Requisitos: 11.7, 1.4, 5.1, 5.2, 5.3, 5.4, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 12. Implementar página de Clientes (`pages/2_Clientes.py`)
  - `sb = require_auth()`; busca; `st.dataframe` com status "Ativo"/"Inativo" e CNPJ formatado
  - "Novo Cliente" com `clear_on_submit=False`; "Editar Cliente" com CNPJ somente leitura
  - "Inativar" com `st.dialog` informando que contratos ativos/em implantação serão cancelados
  - Exibe `error` e `warning` dos serviços
  - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 8.3_

- [x] 13. Implementar página de Contratos (`pages/3_Contratos.py`)
  - `sb = require_auth()`; filtros por cliente e status; `st.dataframe` com coluna de alerta
  - "Novo Contrato" apenas com clientes ativos, `clear_on_submit=False`
  - Edição de status; "Cancelar Contrato" com `st.dialog`
  - Seção "Escopo do Agente": criação/edição, `modelos_permitidos` um por linha
  - _Requisitos: 3.1–3.10, 4.1–4.12, 5.1, 5.2, 5.3, 5.6, 8.3, 10.2_

- [x] 14. Implementar página de Configurações (`pages/4_Configuracoes.py`)
  - `sb = require_auth()`; perfil via `authentication.update_profile()` com aviso de confirmação de e-mail
  - "Novo Membro da Equipe" visível apenas para Admin (`is_admin()`), com seleção de perfil (Membro/Admin); senha temporária exibida uma vez com `st.code()`
  - Para Membros, informar que o cadastro é restrito a administradores
  - Nenhuma chamada direta a `supabase.auth.*`
  - _Requisitos: 9.3, 9.4, 9.5, 11.3, 11.5_

- [x] 15. Checkpoint final — Garantir integração completa
  - Todos os testes passam (unitários, property-based e arquitetura)
  - App inicia com `streamlit run app.py` sem erros de import (mesmo sem `.env`, exibindo erro de configuração amigável)
  - Atualizar README com o roteiro de testes de integração manuais para quando o projeto Supabase existir
  - Perguntar ao usuário se há dúvidas antes de encerrar.

## Notes

- Todas as tarefas de teste são obrigatórias nesta implementação (decisão do usuário).
- Repositórios recebem o cliente Supabase como parâmetro e nunca referenciam `st.*`; páginas nunca chamam o Supabase nem importam repositórios.
- O cliente Supabase é criado por sessão; um cliente compartilhado entre usuários é proibido.
- A chave `service_role` só é usada em `auth/authentication.py`, para criação de membros.
- Cache fica nos serviços de dados; invalidação após escrita bem-sucedida; falha na invalidação gera `st.warning()` e mantém a escrita.
- Property tests usam `@settings(max_examples=100)` e são anotados com `# Feature: crm-agentes-ia, Property N: <texto>`.
- Testes de integração contra o Supabase real ficam para depois da criação do projeto (roteiro no README).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "2.4", "3.1", "3.3", "3.6"] },
    { "id": 2, "tasks": ["3.2", "3.4", "3.5", "3.7", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3"] },
    { "id": 4, "tasks": ["4.4", "6.1", "6.3", "6.5", "7.1", "7.4"] },
    { "id": 5, "tasks": ["6.2", "6.4", "6.6", "7.2", "7.3", "7.5", "7.6", "7.7"] },
    { "id": 6, "tasks": ["7.8", "8", "10"] },
    { "id": 7, "tasks": ["11", "12"] },
    { "id": 8, "tasks": ["13"] },
    { "id": 9, "tasks": ["14"] }
  ]
}
```
