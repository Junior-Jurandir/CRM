# Segurança

> Público: desenvolvedores e operação.

A segurança é feita em camadas: **Supabase Auth** autentica, cada sessão usa **o próprio JWT**, o **RLS** do PostgreSQL bloqueia acesso anônimo e as **constraints/triggers** garantem a integridade mesmo se a aplicação for contornada.

## Autenticação

| Item | Comportamento | Onde |
|---|---|---|
| Credenciais | E-mail + senha (mínimo 8 caracteres) via `sign_in_with_password` | `auth/authentication.py` → `login()` |
| Mensagem de erro | Sempre genérica: "E-mail ou senha inválidos." — nunca diz qual campo errou | `MSG_INVALID_CREDENTIALS` |
| Bloqueio | 5 falhas consecutivas para o mesmo e-mail → 15 minutos bloqueado | `auth/login_guard.py` |
| Duração da sessão | Até 8 horas a partir do login | `SESSION_MAX_HOURS` em `config.py` |
| Renovação do token | Quando faltam 60 s ou menos para expirar, `refresh_session()`; se falhar, logout | `is_session_valid()` |
| Logout | `sign_out()` no Supabase e limpeza do `session_state` (mesmo se o `sign_out` falhar) | `logout()` |
| Rotas protegidas | Toda página chama `require_auth()` antes de renderizar | `pages/*.py` |

### Bloqueio de tentativas (`LoginGuard`)

- A chave é o e-mail normalizado (`strip().lower()`), então `Ana@X.com` e ` ana@x.com` contam juntos.
- Uma instância por processo (`@st.cache_resource`), compartilhada por todas as sessões: recarregar a página ou abrir outra aba **não** zera a contagem.
- Login bem-sucedido zera a contagem. Falhas durante o bloqueio não o estendem.
- E-mail ou senha em formato inválido não consultam o Supabase e não contam como tentativa.
- Falhas de rede também não contam como tentativa.

> **Limitação:** o contador vive na memória. Reiniciar o servidor zera todos os bloqueios, e várias réplicas do app não compartilham o contador.

## Isolamento entre sessões

O Streamlit atende todos os usuários no mesmo processo Python. Por isso:

- **Cada login cria um cliente Supabase novo** (`create_user_client()`), guardado em `st.session_state["sb"]`.
- Nunca existe um cliente global com sessão de usuário.
- Repositórios recebem o cliente como parâmetro e não guardam estado.

## Perfis de acesso

| Perfil | Valor em `app_metadata.role` | Pode |
|---|---|---|
| Membro | `"membro"` ou ausente | Tudo em clientes, contratos, escopos e dashboard |
| Admin | `"admin"` | Tudo o que o Membro faz **e** cadastrar novos membros |

Regras:

- O perfil fica em **`app_metadata`**, que só pode ser alterado com a chave `service_role`. O usuário não consegue se promover.
- **`user_metadata` nunca é usado para permissões**, porque o próprio usuário pode alterá-lo via `update_user`. Um `user_metadata.role = "admin"` é ignorado.
- Qualquer valor diferente de exatamente `"admin"` (inclusive `"Admin"`, `" admin"` ou ausente) é tratado como Membro.
- A tela de Configurações esconde o cadastro para Membros, mas a **autorização real** está em `create_team_member()`: ela consulta `sb.auth.get_user()` no Supabase no momento da operação e não confia no perfil guardado na sessão.

O primeiro Admin é definido manualmente com `sql/04_bootstrap_admin.sql` (veja [operacao.md](operacao.md#primeiro-admin)).

## Chave `service_role`

A `SUPABASE_SERVICE_ROLE_KEY` ignora o RLS. Por isso:

- É opcional: sem ela o app funciona, só o cadastro de membros fica indisponível.
- É lida apenas em `config.py` e usada apenas em `utils/supabase_client.create_admin_client()`.
- `create_admin_client()` só é chamada em `auth/authentication.create_team_member()`. O cliente é criado na hora e descartado; nunca vai para o `session_state`.
- Essas três restrições são verificadas em `tests/test_architecture.py`.
- Nunca deve ser versionada (o `.env` está no `.gitignore`) nem exposta no navegador.

## Cadastro de membros

1. O Admin informa nome, e-mail e perfil.
2. O servidor revalida que o solicitante é Admin.
3. É gerada uma senha temporária com `secrets.token_urlsafe(12)` (16 caracteres aleatórios).
4. O usuário é criado com `email_confirm: true` (sem e-mail de convite), `user_metadata.nome` e `app_metadata.role`.
5. A senha é exibida **uma única vez** na tela. Ela não é gravada no `session_state`, em logs nem no banco da aplicação.

> Recomende ao novo membro trocar a senha. Hoje isso é feito pelo painel do Supabase ou pelo fluxo de recuperação de senha; o app não tem tela de troca de senha.

## Banco de dados

| Proteção | Detalhe |
|---|---|
| RLS | Habilitado em `clientes`, `contratos` e `escopo_agentes` |
| Políticas | `FOR ALL TO authenticated USING (true) WITH CHECK (true)` — acesso completo só para autenticados |
| Papel `anon` | Sem política e com privilégios revogados (`REVOKE ALL`): leitura retorna `42501 permission denied` |
| RPC `inativar_cliente` | `SECURITY INVOKER` (respeita o RLS de quem chama); `EXECUTE` apenas para `authenticated` |
| Integridade | CHECKs, UNIQUE e triggers rejeitam dados inválidos mesmo vindos fora da aplicação |

Detalhes em [banco-de-dados.md](banco-de-dados.md).

## Dados pessoais e segredos

- Senhas digitadas não são guardadas pela aplicação; o Supabase Auth cuida do armazenamento.
- O `.env` contém chaves e não deve ser versionado.
- Os logs registram falhas técnicas (`logger.warning`/`logger.exception`) sem incluir senhas ou tokens.

## Checklist de revisão de segurança

Antes de cada entrega:

- [ ] `pytest` passa, incluindo `tests/test_architecture.py`
- [ ] `scripts/verificar_supabase.py` passa na Parte 1 (anon bloqueado)
- [ ] Nenhuma página nova chama o Supabase diretamente
- [ ] Nenhum uso novo de `create_admin_client` fora de `auth/authentication.py`
- [ ] Toda página nova chama `require_auth()` no topo
- [ ] `.env` fora do controle de versão
