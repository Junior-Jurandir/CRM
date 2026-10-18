# Operação e deploy

> Público: quem instala, configura e mantém o sistema.

## Pré-requisitos

- Python 3.10 ou superior (versões das dependências verificadas com 3.14.2)
- Um projeto no [Supabase](https://supabase.com)
- Acesso de saída HTTPS do servidor para `*.supabase.co`

## 1. Criar e preparar o projeto Supabase

1. Crie o projeto no painel do Supabase.
2. Abra **SQL Editor** e execute, nesta ordem:
   1. [`sql/01_schema.sql`](../sql/01_schema.sql)
   2. [`sql/02_functions_triggers.sql`](../sql/02_functions_triggers.sql)
   3. [`sql/03_rls.sql`](../sql/03_rls.sql)
3. Em **Authentication → Providers → Email**, decida sobre **Secure email change**:
   - ligado (padrão): quando um usuário troca o e-mail em Configurações, a troca só vale depois de ele confirmar pelo link enviado ao novo endereço;
   - desligado: a troca vale na hora.

### Primeiro Admin

1. Em **Authentication → Users → Add user → Create new user**, informe e-mail e senha e marque **Auto Confirm User**.
2. Abra [`sql/04_bootstrap_admin.sql`](../sql/04_bootstrap_admin.sql), **troque o e-mail de exemplo** (`admin@suaempresa.com.br`) pelo e-mail criado e execute.
3. Confira o resultado da consulta no final do script: a coluna `perfil` deve mostrar `admin`.

> Se a coluna mostrar vazio, o `UPDATE` não encontrou o e-mail. O caso mais comum é ter executado o script sem trocar o e-mail de exemplo.

Os demais membros são cadastrados pelo próprio Admin na tela **Configurações**.

## 2. Configurar a aplicação

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Linux/macOS: cp .env.example .env
```

Preencha o `.env` com os dados de **Project Settings → API**:

| Variável | Obrigatória | Uso |
|---|---|---|
| `SUPABASE_URL` | Sim | URL do projeto (`https://<ref>.supabase.co`) |
| `SUPABASE_ANON_KEY` | Sim | Chave pública (anon). Usada nas sessões dos usuários |
| `SUPABASE_SERVICE_ROLE_KEY` | Não | Chave administrativa. Só para o Admin cadastrar membros. **Nunca versione nem compartilhe** |

As variáveis também podem vir do ambiente do sistema operacional, que têm prioridade sobre o `.env`.

Constantes de comportamento ficam em [`config.py`](../config.py):

| Constante | Padrão | Significado |
|---|---|---|
| `CACHE_TTL` | 300 | Segundos que as leituras ficam em cache |
| `SESSION_MAX_HOURS` | 8 | Duração máxima da sessão após o login |
| `TOKEN_REFRESH_MARGIN_SECONDS` | 60 | Antecedência para renovar o token |
| `LOGIN_MAX_ATTEMPTS` | 5 | Falhas seguidas até bloquear |
| `LOGIN_LOCKOUT_MINUTES` | 15 | Duração do bloqueio |

## 3. Verificar a instalação

```bash
.venv\Scripts\python scripts\verificar_supabase.py --login
```

Resultado esperado: **27/27 verificações OK**. O script pede e-mail e senha de um Admin no terminal (a senha não aparece nem é salva), cria dados marcados `[VERIFICACAO]` e os remove ao final.

Sem `--login`, roda só as 6 checagens anônimas (conexão e bloqueio pelo RLS).

## 4. Executar

```bash
streamlit run app.py
```

Abre em `http://localhost:8501`. O tema escuro vem de [`.streamlit/config.toml`](../.streamlit/config.toml).

## Deploy em produção

### Requisito importante: uma única instância

O bloqueio de tentativas de login fica na memória do processo. Rode **uma instância** do app. Com várias réplicas atrás de um balanceador, cada uma teria o próprio contador e o bloqueio deixaria de valer de forma confiável.

### Servidor próprio (Linux)

1. Copie o projeto, crie o `.venv` e o `.env` como acima.
2. Rode como serviço (exemplo `systemd`):

   ```ini
   [Unit]
   Description=CRM Agentes de IA
   After=network-online.target

   [Service]
   WorkingDirectory=/opt/crm
   ExecStart=/opt/crm/.venv/bin/streamlit run app.py --server.headless true --server.port 8501 --server.address 127.0.0.1
   Restart=on-failure
   User=crm

   [Install]
   WantedBy=multi-user.target
   ```

3. Publique por um proxy reverso com HTTPS (Nginx, Caddy). O Streamlit usa WebSocket em `/_stcore/stream`, então o proxy precisa repassar `Upgrade` e `Connection`.
4. Restrinja permissões do `.env` (`chmod 600`).

### Streamlit Community Cloud

1. Publique o repositório (sem o `.env`, que está no `.gitignore`).
2. Em **Settings → Secrets**, informe as variáveis como chaves de primeiro nível:

   ```toml
   SUPABASE_URL = "https://<ref>.supabase.co"
   SUPABASE_ANON_KEY = "..."
   SUPABASE_SERVICE_ROLE_KEY = "..."
   ```

   O Streamlit Cloud expõe chaves de primeiro nível dos Secrets também como variáveis de ambiente, que é de onde `config.py` lê. Confira na primeira publicação: se o Login mostrar "Configuração ausente: defina SUPABASE_URL", as variáveis não chegaram ao processo.

## Rotina de manutenção

| Tarefa | Como |
|---|---|
| Cadastrar membro | Admin → Configurações → Novo membro da equipe |
| Promover/rebaixar Admin | SQL em [banco-de-dados.md](banco-de-dados.md#perfis-de-usuário-auth) |
| Desativar o acesso de alguém | Painel do Supabase → Authentication → Users → Ban user ou Delete user |
| Redefinir senha de um membro | Painel do Supabase → Authentication → Users → Send password recovery (exige SMTP configurado) ou definir nova senha |
| Liberar um e-mail bloqueado antes de 15 min | Reiniciar o serviço do app (zera todos os bloqueios) |
| Trocar a `service_role` (vazamento) | Supabase → Project Settings → API → gerar nova chave; atualizar o `.env`; reiniciar o app |
| Backup | Backups automáticos do Supabase (conforme o plano) ou `pg_dump` com a connection string do projeto |
| Atualizar dependências | Atualize `requirements.txt`, rode `pytest` e `scripts/verificar_supabase.py --login` antes de publicar |

## Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| Login mostra "Configuração ausente: defina SUPABASE_URL…" | `.env` ausente ou variável vazia | Criar/preencher o `.env` e reiniciar o app |
| `PGRST205 Could not find the table 'public.clientes' in the schema cache` | Scripts SQL não executados neste projeto, ou cache da API desatualizado | Executar `01` a `03`; se já executou, rodar `NOTIFY pgrst, 'reload schema';` |
| `PGRST202 Could not find the function public.inativar_cliente` | `02_functions_triggers.sql` não executado | Executar o script `02` e depois o `03` |
| "E-mail ou senha inválidos." com a senha certa | Usuário não confirmado ou e-mail/senha diferentes do cadastrado | No painel, confirmar o usuário (ou recriá-lo com *Auto Confirm User*) |
| "Acesso bloqueado por 15 minutos…" | 5 falhas seguidas para o e-mail | Esperar 15 min ou reiniciar o app |
| Admin não vê "Novo membro da equipe" | `app_metadata.role` não é `admin`, ou o login foi feito antes da promoção | Rodar o bootstrap com o e-mail correto e fazer login de novo |
| "Cadastro de membros indisponível: chave administrativa não configurada." | `SUPABASE_SERVICE_ROLE_KEY` vazia | Preencher no `.env` e reiniciar |
| "Sua sessão expirou ou não tem permissão…" | Token expirado ou RLS sem `GRANT` | Fazer login de novo; se persistir, executar o `03_rls.sql` |
| Volta para o Login ao apertar F5 | Comportamento esperado: a sessão vive na memória da aba | Fazer login de novo |
| Troca de e-mail não aparece | "Secure email change" ligado: aguardando confirmação no novo e-mail | Confirmar pelo link ou desligar a opção no Supabase |
| `ConnectionResetError [WinError 10054]` no log | Navegador fechou a conexão WebSocket (troca de página) no Windows | Inofensivo; pode ser ignorado |
| Dados de outro usuário demoram a aparecer | Cache de 300 s | Dashboard → **Atualizar dados** |
