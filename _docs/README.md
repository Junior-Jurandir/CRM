# Documentação do CRM para Agentes de IA

| Documento | Para quem | Conteúdo |
|---|---|---|
| [Manual do usuário](manual-do-usuario.md) | Equipe que usa o CRM | Login, Dashboard, Clientes, Contratos, Escopo, Configurações, perguntas frequentes |
| [Operação e deploy](operacao.md) | Quem instala e mantém | Supabase, variáveis de ambiente, primeiro Admin, verificação, deploy, manutenção, solução de problemas |
| [Arquitetura](arquitetura.md) | Desenvolvedores | Camadas, fluxo de requisição, cache, padrão de erros, alertas, limitações |
| [Segurança](seguranca.md) | Desenvolvedores e operação | Autenticação, bloqueio, isolamento de sessões, perfis, `service_role`, RLS |
| [Banco de dados](banco-de-dados.md) | Desenvolvedores e operação | Tabelas, constraints, funções, triggers, RLS, consultas úteis |
| [Guia de desenvolvimento](desenvolvimento.md) | Desenvolvedores | Ambiente, convenções, como estender, testes, depuração |

A especificação original (requisitos, design e plano de tarefas) está em [`.kiro/specs/crm-agentes-ia/`](../.kiro/specs/crm-agentes-ia).

## Por onde começar

- **Vou usar o sistema** → [Manual do usuário](manual-do-usuario.md)
- **Vou instalar** → [Operação e deploy](operacao.md), seções 1 a 4
- **Vou mexer no código** → [Arquitetura](arquitetura.md) e depois [Guia de desenvolvimento](desenvolvimento.md)
