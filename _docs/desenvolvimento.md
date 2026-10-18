# Guia de desenvolvimento

> Público: desenvolvedores. Leia antes a [arquitetura](arquitetura.md).

## Ambiente local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # preencha com um projeto Supabase de desenvolvimento
streamlit run app.py
```

As versões em `requirements.txt` foram verificadas com Python 3.14.2. O código exige Python 3.10 ou superior (usa a sintaxe `X | Y` em anotações de tipo).

> Use um projeto Supabase separado para desenvolvimento. Os scripts de verificação criam e removem dados de teste, mas o app em si nunca exclui registros.

## Convenções

| Tema | Convenção |
|---|---|
| Idioma | Código (nomes de funções, variáveis) em inglês; mensagens, docstrings e nomes de colunas do banco em português |
| Dinheiro | Sempre `Decimal`. Converta entradas com `utils.converters.to_decimal()`; nunca some `float` |
| Datas | `datetime.date`. O PostgREST devolve `DATE` como string ISO; use `utils.converters.to_date()` |
| Retorno de repositório | `(resultado, erro)`, nunca lança exceção |
| Retorno de escrita no serviço | `ServiceResult(data, error, warning)` |
| Leitura no serviço | Retorna o valor ou lança `DataLoadError` |
| Mensagens ao usuário | Em português, prontas para `st.error()`; constantes `MSG_*` no módulo de origem |
| Exclusão | Proibida. Use estados (`ativo = false`, `status = 'Cancelado'`) |

## Como adicionar uma funcionalidade

Exemplo: um novo campo `responsavel` em contratos.

1. **Banco** — crie `sql/05_contrato_responsavel.sql` com `ALTER TABLE` e `NOTIFY pgrst, 'reload schema';` ([banco-de-dados.md](banco-de-dados.md#evoluindo-o-esquema)).
2. **Validação** — adicione a regra em `utils/validators.py` (retornando `(bool, mensagem)`) e testes em `tests/test_validators.py`.
3. **Repositório** — inclua o campo em `CREATE_FIELDS`/`EDITABLE_FIELDS` de `repositories/contract_repo.py`. Campos fora dessas tuplas são descartados, o que impede gravar colunas não previstas.
4. **Serviço** — valide o campo em `services/contract_service._validate()`.
5. **Tela** — adicione o campo ao formulário em `pages/3_Contratos.py`, passando o valor ao serviço.
6. **Testes** — repositório (payload enviado), serviço (validação e cache) e, se a tela mudar, `tests/test_pages.py`.
7. **Documentação** — atualize esta pasta e o design da Spec.

### Nova página

```python
from auth.authentication import render_user_sidebar, require_auth
from utils.ui import setup_page, show_flash

setup_page("Relatórios", "📈")   # precisa ser a primeira chamada ao Streamlit
sb = require_auth()               # redireciona para o Login se a sessão for inválida
render_user_sidebar()
show_flash()
```

Regras verificadas automaticamente para arquivos em `pages/`: não importar `supabase`, `postgrest`, `supabase_auth`, `repositories` ou `utils.supabase_client`, e não chamar `.table(`, `.rpc(` ou `.auth.`.

### Nova leitura cacheada

```python
@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def list_algo(_sb, filtro: str = "") -> list[dict]:
    rows, err = algo_repo.list_algo(_sb, filtro)
    if err:
        raise DataLoadError(err)   # não cacheia a falha
    return rows
```

Depois de cada escrita bem-sucedida: `ServiceResult(data=..., warning=safe_clear(list_algo, ...))`. Adicione a função a `cache_utils.clear_all_caches()`.

### Ler dados na página

```python
dados = load_or_stop(algo_service.list_algo, sb, filtro)  # erro + botão Recarregar se falhar
```

### Gravar dados na página

```python
result = algo_service.create_algo(sb, payload)
if handle_result(result, "Registro salvo."):   # mostra o erro ou agenda sucesso/aviso
    st.rerun()
```

Use `st.form(..., clear_on_submit=False)` para preservar o que o usuário digitou quando a validação falha.

## Testes

```bash
pytest                                  # tudo (cerca de 7 s)
pytest tests/test_validators.py -v      # um arquivo
pytest -k cnpj                          # por nome
```

Os testes não acessam a rede. São 245 testes em quatro tipos:

| Tipo | Arquivos | O que cobre |
|---|---|---|
| Unitários | `test_validators`, `test_formatters`, `test_login_guard`, `test_authentication`, `test_*_repo`, `test_alert_service`, `test_dashboard_service`, `test_services_cache` | Regras, bordas, erros, payloads enviados ao Supabase |
| Propriedades (Hypothesis) | marcados com `# Feature: crm-agentes-ia, Property N` | As 13 propriedades de corretude do design, com 100 exemplos gerados cada |
| Arquitetura | `test_architecture` | Separação de camadas e confinamento da `service_role` |
| Telas | `test_pages` | Renderização das 5 telas com `streamlit.testing.v1.AppTest` |

### Ferramentas de teste

- **`tests/fakes.py`** — `FakeClient` substitui o cliente Supabase nos testes de repositório. Cada `.execute()` consome a próxima resposta da fila (lista de linhas ou exceção). Use `sb.last.call("insert")` para inspecionar o que foi enviado e `api_error("23505")` para simular erros do PostgREST.
- **`st.session_state`** — nos testes de autenticação é substituído por um `dict` com `monkeypatch`.
- **Telas** — `test_pages.py` roda a partir de `app.py` (como o app real) e usa `at.switch_page(...)`. Os repositórios são substituídos por dados fixos.

### Propriedades de corretude

| # | Propriedade | Teste |
|---|---|---|
| 1 | `data_fim ≤ data_inicio` é rejeitada; `data_fim > data_inicio` é aceita | `test_validators` |
| 2 | Nível de alerta determinístico e correto por faixa | `test_alert_service` |
| 3 | Cancelado / Em Implantação nunca alertam | `test_alert_service` |
| 4 | MRR = soma dos Ativos | `test_dashboard_service` |
| 5 | Inativação usa RPC, nunca DELETE | `test_client_repo` |
| 6 | CNPJ duplicado sempre rejeitado | `test_client_repo` |
| 7 | Edição de escopo nunca envia `contrato_id` | `test_scope_repo` |
| 8 | Limites de requisições e horas | `test_validators` |
| 9 | Cancelamento usa UPDATE, nunca DELETE | `test_contract_repo` |
| 10 | Valores monetários com 2 casas sem perda | `test_validators`, `test_formatters` |
| 11 | Bloqueio exatamente após 5 falhas consecutivas | `test_login_guard` |
| 12 | Cache invalidado só após escrita bem-sucedida | `test_services_cache` |
| 13 | Só `app_metadata.role == "admin"` cadastra membros | `test_authentication` |

### Testes de arquitetura

`tests/test_architecture.py` falha se:

- um arquivo de `repositories/` importar `streamlit` ou usar `st.`;
- `app.py` ou `pages/*.py` importarem o Supabase ou repositórios, ou chamarem `.table(`, `.rpc(` ou `.auth.`;
- `create_admin_client` for usado fora de `utils/supabase_client.py` e `auth/authentication.py`;
- `SUPABASE_SERVICE_ROLE_KEY` aparecer fora de `config.py` e `utils/supabase_client.py`;
- algum repositório chamar `.delete(`.

### Teste de integração com o Supabase real

```bash
.venv\Scripts\python scripts\verificar_supabase.py           # parte anônima
.venv\Scripts\python scripts\verificar_supabase.py --login   # parte autenticada (pede e-mail/senha)
```

Verifica RLS, constraints, triggers, a cascata de inativação e a renovação de token: 27 checagens. Os dados criados são marcados `[VERIFICACAO]` e removidos ao final.

### Roteiro de teste manual

Antes de uma entrega, percorra no app:

1. Login com credenciais inválidas → mensagem genérica; 5 erros seguidos → bloqueio de 15 minutos (use um e-mail que não existe).
2. Abrir `/Dashboard` sem login → redireciona para o Login.
3. Clientes: cadastrar; repetir o mesmo CNPJ (erro, dados preservados no formulário); buscar por parte da razão social e pelo CNPJ formatado; editar.
4. Contratos: criar para um cliente ativo; `data_fim` ≤ `data_inicio` e valor 0 são rejeitados; cadastrar e editar o escopo do agente.
5. Um contrato com término em até 30 dias aparece com alerta na listagem e no Dashboard.
6. Inativar um cliente com contratos Ativo/Em Implantação → eles passam a Cancelado; "Renovação Pendente" é mantido; novo contrato para ele é rejeitado.
7. Configurações (Admin): cadastrar um Membro → senha temporária exibida uma vez; entrar como esse membro → a seção de cadastro não aparece.
8. Duas janelas anônimas com usuários diferentes: cada uma mantém a própria identidade.

## Depuração

| Sintoma | Onde olhar |
|---|---|
| Mensagem "Falha ao carregar dados" | Log do servidor: `repositories.base` registra o erro original com `logger.warning` |
| Dados desatualizados na tela | Cache de 300 s; use **Atualizar dados** no Dashboard ou `clear_all_caches()` |
| Redirecionado para o Login sem motivo | Sessão > 8 h, F5 na página ou falha na renovação do token |
| Teste de tela falha com `FileNotFoundError` | `AppTest.from_file` resolve caminhos relativos ao arquivo de teste; use caminho absoluto |

## Spec

Requisitos, design e plano de tarefas ficam em [`.kiro/specs/crm-agentes-ia/`](../.kiro/specs/crm-agentes-ia). Mudanças de comportamento devem atualizar primeiro a Spec e depois o código.
