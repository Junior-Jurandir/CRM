# CRM para Agentes de IA

Aplicação interna em **Streamlit + Supabase** para gerenciar clientes, contratos de agentes de IA e seus escopos técnicos, com **MRR**, **alertas de vencimento** e **perfis Admin/Membro**.

## Funcionalidades

- **Login** com Supabase Auth, bloqueio após 5 tentativas e sessão de até 8 horas
- **Clientes**: cadastro, busca por razão social ou CNPJ, edição e inativação (com cancelamento automático dos contratos em aberto)
- **Contratos**: cadastro, filtros, edição de status, cancelamento e alertas de vencimento em 4 níveis
- **Escopo do agente**: arquitetura, limite de requisições, horas de manutenção e modelos permitidos
- **Dashboard**: MRR, contratos por status, gráfico de vencimentos e lista de alertas
- **Configurações**: edição do próprio perfil; cadastro de membros com senha temporária (somente Admin)

## Início rápido

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

1. Preencha o `.env` com `SUPABASE_URL`, `SUPABASE_ANON_KEY` e, opcionalmente, `SUPABASE_SERVICE_ROLE_KEY`.
2. No SQL Editor do Supabase, execute `sql/01` a `sql/03` e, depois de criar o primeiro usuário, `sql/04_bootstrap_admin.sql` com o e-mail dele.
3. Verifique a instalação:

   ```bash
   .venv\Scripts\python scripts\verificar_supabase.py --login
   ```

4. Execute o app:

   ```bash
   streamlit run app.py
   ```

O passo a passo completo está em [docs/operacao.md](docs/operacao.md).

## Testes

```bash
pytest
```

245 testes (unitários, de propriedade com Hypothesis, de arquitetura e de telas), sem acesso à rede.

## Documentação

| | |
|---|---|
| [Manual do usuário](docs/manual-do-usuario.md) | Como usar cada tela |
| [Operação e deploy](docs/operacao.md) | Instalação, configuração, deploy e solução de problemas |
| [Arquitetura](docs/arquitetura.md) | Camadas, decisões de design e limitações |
| [Segurança](docs/seguranca.md) | Autenticação, perfis, RLS e `service_role` |
| [Banco de dados](docs/banco-de-dados.md) | Tabelas, funções, triggers e consultas úteis |
| [Guia de desenvolvimento](docs/desenvolvimento.md) | Convenções, como estender e testes |
| [Spec](.kiro/specs/crm-agentes-ia) | Requisitos, design e plano de tarefas |

## Estrutura

```
app.py              Login
pages/              Dashboard, Clientes, Contratos, Configurações
auth/               Autenticação, sessão, perfis, bloqueio de tentativas
services/           Validação, cache e regras de negócio
repositories/       Acesso ao Supabase (sem Streamlit)
utils/              Validadores, formatadores, fábrica de clientes, helpers de UI
sql/                Scripts do banco
scripts/            Verificação de integração com o Supabase
tests/              Testes automatizados
docs/               Documentação
```
