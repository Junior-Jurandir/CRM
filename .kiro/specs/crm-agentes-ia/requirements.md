# Requirements Document

## Introduction

Este documento especifica os requisitos funcionais e não funcionais do **CRM para Agentes de IA**, uma aplicação web SPA/MPA construída com Streamlit (Python) e Supabase (PostgreSQL). O sistema permite que equipes internas gerenciem clientes, contratos de agentes de IA, escopos técnicos e acompanhem métricas de receita recorrente (MRR), com autenticação segura e alertas de vencimento de contratos.

## Glossary

- **CRM**: Customer Relationship Management — sistema de gestão de relacionamento com clientes.
- **Sistema**: A aplicação web CRM para Agentes de IA como um todo.
- **Auth_Service**: Módulo de autenticação e autorização delegado ao Supabase Auth.
- **Cliente_Manager**: Módulo responsável pelo CRUD de clientes e seus contatos.
- **Contrato_Manager**: Módulo responsável pelo CRUD de contratos de IA vinculados a clientes.
- **Escopo_Manager**: Módulo responsável pelo detalhamento técnico do escopo de cada agente de IA.
- **Alerta_Service**: Serviço de monitoramento e sinalização visual de contratos próximos ao vencimento.
- **Dashboard**: Tela de visão consolidada de métricas do sistema.
- **MRR**: Monthly Recurring Revenue — receita mensal recorrente.
- **RLS**: Row Level Security — política de segurança em nível de linha no banco de dados.
- **Usuário_Interno**: Membro da equipe autenticado com acesso ao sistema.
- **SLA**: Service Level Agreement — acordo de nível de serviço.
- **CNPJ**: Cadastro Nacional de Pessoa Jurídica — identificador fiscal de empresas brasileiras (14 dígitos numéricos).
- **JSONB**: Tipo de dado PostgreSQL para armazenamento de JSON binário.
- **UUID**: Universally Unique Identifier — identificador único universal utilizado como chave primária.
- **JWT**: JSON Web Token — token de autenticação utilizado pelo Supabase Auth.
- **TTL**: Time To Live — tempo máximo de validade de uma entrada em cache.
- **RPC**: Remote Procedure Call — função SQL no PostgreSQL invocada via `client.rpc()` do supabase-py, executada em uma única transação.
- **Service_Role_Key**: chave administrativa do Supabase que ignora RLS; de uso exclusivo no servidor.
- **Refresh_Token**: token emitido pelo Supabase Auth usado para obter um novo token de acesso sem nova digitação de senha.

## Requirements

### Requirement 1: Autenticação de Usuários Internos

**User Story:** Como membro da equipe, quero me autenticar no sistema com e-mail e senha, para que apenas usuários autorizados tenham acesso às informações de clientes e contratos.

#### Acceptance Criteria

1. WHEN um Usuário_Interno submete um e-mail com formato válido (contendo "@" e domínio) e uma senha com no mínimo 8 caracteres, THE Auth_Service SHALL autenticar o usuário via Supabase Auth e redirecionar para o Dashboard.
2. IF um Usuário_Interno submete credenciais inválidas, THEN THE Auth_Service SHALL exibir uma mensagem de erro indicando falha de autenticação sem especificar qual campo está incorreto.
3. WHILE uma sessão autenticada está ativa, THE Sistema SHALL manter o identificador do usuário e seu perfil de acesso disponíveis entre as telas da aplicação, pelo período de até 8 horas a partir do último login, renovando automaticamente o token de acesso do Supabase Auth (via refresh token) antes de sua expiração dentro desse período.
4. WHEN o usuário realiza logout, THE Auth_Service SHALL invalidar o token de sessão no Supabase Auth e redirecionar o usuário para a tela de Login.
5. IF a sessão do usuário expira após 8 horas sem renovação, THEN THE Auth_Service SHALL invalidar o token de sessão e redirecionar o usuário para a tela de Login.
6. IF um Usuário_Interno submete credenciais inválidas 5 vezes consecutivas, THEN THE Auth_Service SHALL bloquear novas tentativas de login para aquele e-mail por 15 minutos e exibir mensagem indicando o bloqueio temporário. O controle de tentativas SHALL ser mantido no servidor, indexado pelo e-mail normalizado (minúsculas, sem espaços), e compartilhado entre todas as sessões do navegador, de modo que recarregar a página ou abrir nova aba não reinicie a contagem.
7. IF um usuário não autenticado tenta acessar qualquer rota protegida, THEN THE Auth_Service SHALL redirecionar o acesso para a tela de Login.
8. THE Auth_Service SHALL delegar toda a lógica de autenticação, incluindo validação de credenciais e gerenciamento de tokens, ao Supabase Auth via supabase-py.
9. THE Sistema SHALL manter um cliente Supabase dedicado por sessão de usuário, de modo que o token JWT de um usuário nunca seja utilizado em requisições de outro usuário.
10. IF a renovação automática do token de acesso falhar, THEN THE Auth_Service SHALL encerrar a sessão e redirecionar o usuário para a tela de Login.

> **Limitação conhecida:** o estado de sessão do Streamlit não sobrevive ao recarregamento completo da página (F5). Nesse caso o usuário precisará autenticar-se novamente. Persistência de sessão via cookies está fora do escopo desta versão.

---

### Requirement 2: Gestão de Clientes (CRUD)

**User Story:** Como membro da equipe, quero cadastrar, visualizar, editar e inativar empresas clientes com seus contatos, para que o histórico de relacionamento esteja centralizado e atualizado.

#### Acceptance Criteria

1. THE Cliente_Manager SHALL armazenar para cada cliente os campos: razao_social (texto, máx. 255 caracteres), cnpj (14 dígitos numéricos), contato_nome (texto, máx. 150 caracteres), email (formato válido com "@" e domínio), telefone (texto, máx. 20 caracteres) e created_at (timestamp).
2. WHEN um Usuário_Interno cadastra um novo cliente com os campos obrigatórios razao_social, cnpj, contato_nome e email preenchidos, THE Cliente_Manager SHALL criar o registro com UUID gerado automaticamente e registrar o created_at com o timestamp atual.
3. WHEN um Usuário_Interno submete um cadastro de cliente com CNPJ já existente na base de dados, THE Cliente_Manager SHALL rejeitar o registro, exibir uma mensagem de erro indicando duplicidade e preservar os dados preenchidos no formulário.
4. WHEN um Usuário_Interno edita os dados de um cliente existente, THE Cliente_Manager SHALL permitir a alteração dos campos razao_social, contato_nome, email e telefone, e SHALL preservar os campos UUID, cnpj e created_at originais sem modificação.
5. WHEN um Usuário_Interno inativa um cliente, THE Cliente_Manager SHALL marcar o cliente como inativo, registrar o timestamp de inativação e não excluir o registro do banco de dados.
6. WHILE um cliente está inativo, THE Cliente_Manager SHALL exibir o cliente na listagem com o rótulo textual "Inativo" e SHALL rejeitar a criação de novos contratos vinculados a ele, exibindo mensagem de erro indicando que o cliente está inativo.
7. WHEN um Usuário_Interno inativa um cliente que possui contratos com status "Ativo" ou "Em Implantação", THE Cliente_Manager SHALL alterar automaticamente o status desses contratos para "Cancelado" na mesma operação de inativação, de forma atômica (em uma única transação no banco de dados): ou o cliente é inativado e os contratos cancelados, ou nenhuma alteração é persistida.
8. IF um Usuário_Interno tenta inativar um cliente inexistente ou já inativo, THEN THE Cliente_Manager SHALL rejeitar a operação e exibir mensagem de erro indicando que o cliente não foi encontrado ou já está inativo.
9. WHEN um Usuário_Interno acessa a listagem de clientes, THE Cliente_Manager SHALL exibir todos os clientes com suporte a busca por correspondência parcial em razao_social e por correspondência exata em CNPJ.

---

### Requirement 3: Gestão de Contratos de IA (CRUD)

**User Story:** Como membro da equipe, quero registrar e gerenciar contratos de agentes de IA vinculados a clientes, para que eu possa acompanhar vigências, status e valores financeiros de cada projeto.

#### Acceptance Criteria

1. THE Contrato_Manager SHALL armazenar para cada contrato os campos: cliente_id (FK), titulo_projeto (texto, máx. 255 caracteres), status, data_inicio, data_fim, valor_mensal (decimal), setup_fee (decimal) e created_at.
2. WHEN um Usuário_Interno cria um contrato, THE Contrato_Manager SHALL exigir a vinculação a um cliente com status igual a "Ativo" no banco de dados. Essa regra SHALL ser verificada na aplicação e reforçada no banco de dados, de modo que uma inserção vinculada a cliente inativo seja rejeitada mesmo que a validação da aplicação seja contornada.
3. WHEN um Usuário_Interno cria ou edita um contrato, THE Contrato_Manager SHALL aceitar somente os seguintes valores para o campo status: "Ativo", "Em Implantação", "Renovação Pendente" ou "Cancelado".
4. IF um Usuário_Interno registra um contrato com data_fim anterior ou igual à data_inicio, THEN THE Contrato_Manager SHALL rejeitar o registro, exibir mensagem de erro descritiva e preservar os dados do formulário.
5. WHEN um Usuário_Interno edita o status de um contrato existente, THE Contrato_Manager SHALL persistir o novo status e atualizar a exibição na listagem sem exigir ação adicional do usuário.
6. THE Contrato_Manager SHALL registrar o valor_mensal (MRR) como um número decimal positivo entre 0,01 e 999.999.999,99, em reais, com até duas casas decimais.
7. IF um Usuário_Interno submete um valor_mensal fora do intervalo permitido ou em formato inválido, THEN THE Contrato_Manager SHALL rejeitar o registro e exibir mensagem de erro indicando o formato esperado.
8. THE Contrato_Manager SHALL registrar o setup_fee como um número decimal positivo entre 0,00 e 999.999.999,99, em reais, com até duas casas decimais, separado do valor_mensal.
9. IF um Usuário_Interno submete um setup_fee fora do intervalo permitido ou em formato inválido, THEN THE Contrato_Manager SHALL rejeitar o registro e exibir mensagem de erro indicando o formato esperado.
10. WHEN um Usuário_Interno cancela um contrato, THE Contrato_Manager SHALL marcar o status como "Cancelado" sem excluir o registro do banco de dados.

---

### Requirement 4: Especificação do Escopo do Agente de IA

**User Story:** Como membro da equipe, quero detalhar os parâmetros técnicos do agente de IA vinculado a um contrato, para que o escopo de entrega esteja documentado e auditável.

#### Acceptance Criteria

1. THE Escopo_Manager SHALL armazenar para cada escopo os campos: contrato_id (FK), tipo_arquitetura (texto), limite_requisicoes (inteiro), horas_manutencao (numérico) e modelos_permitidos (JSONB — array de strings).
2. WHEN um Usuário_Interno cadastra o escopo de um agente, THE Escopo_Manager SHALL exigir a vinculação a um contrato existente identificado por um contrato_id válido no banco de dados.
3. IF um Usuário_Interno informa um contrato_id que não existe no banco de dados, THEN THE Escopo_Manager SHALL rejeitar o registro e exibir mensagem de erro indicando que o contrato não foi encontrado.
4. WHEN um Usuário_Interno informa limite_requisicoes, THE Escopo_Manager SHALL aceitar somente valores inteiros positivos entre 1 e 10.000.000.
5. IF um Usuário_Interno informa limite_requisicoes fora do intervalo permitido ou em formato não inteiro, THEN THE Escopo_Manager SHALL rejeitar o registro e exibir mensagem de erro indicando o intervalo aceito.
6. WHEN um Usuário_Interno informa horas_manutencao, THE Escopo_Manager SHALL aceitar somente valores numéricos positivos entre 0,5 e 8.760.
7. IF um Usuário_Interno informa horas_manutencao fora do intervalo permitido, THEN THE Escopo_Manager SHALL rejeitar o registro e exibir mensagem de erro indicando o intervalo aceito.
8. THE Escopo_Manager SHALL armazenar o campo modelos_permitidos como um array JSON contendo entre 1 e 50 strings, cada uma com no máximo 100 caracteres.
9. IF um Usuário_Interno submete modelos_permitidos como array vazio ou com itens inválidos, THEN THE Escopo_Manager SHALL rejeitar o registro e exibir mensagem de erro indicando que ao menos um modelo deve ser especificado.
10. WHEN um Usuário_Interno edita os parâmetros técnicos de um escopo existente sem informar um contrato_id diferente do original, THE Escopo_Manager SHALL atualizar o registro preservando o contrato_id e o UUID originais.
11. IF um Usuário_Interno informa um contrato_id diferente do original em uma operação de edição de escopo, THEN THE Escopo_Manager SHALL rejeitar a edição e exibir mensagem de erro indicando que o campo contrato_id não pode ser alterado.
12. IF um Usuário_Interno tenta editar um escopo com UUID inexistente, THEN THE Escopo_Manager SHALL retornar mensagem de erro indicando que o escopo não foi encontrado.

---

### Requirement 5: Alertas de Vencimento de Contratos

**User Story:** Como membro da equipe, quero ser alertado visualmente sobre contratos próximos ao vencimento, para que eu possa iniciar o processo de renovação com antecedência e evitar cancelamentos indesejados.

#### Acceptance Criteria

1. WHEN a data_fim de um contrato com status "Ativo" ou "Renovação Pendente" está entre 16 e 30 dias a partir da data atual, THE Alerta_Service SHALL exibir um indicador visual de nível 1 (atenção) junto ao contrato na listagem e no Dashboard, informando o número de dias restantes.
2. WHEN a data_fim de um contrato com status "Ativo" ou "Renovação Pendente" está entre 8 e 15 dias a partir da data atual, THE Alerta_Service SHALL exibir um indicador visual de nível 2 (urgente), distinto do nível 1, junto ao contrato na listagem e no Dashboard, informando o número de dias restantes.
3. WHEN a data_fim de um contrato com status "Ativo" ou "Renovação Pendente" está a 7 dias ou menos a partir da data atual, THE Alerta_Service SHALL exibir um indicador visual de nível 3 (crítico), distinto dos níveis anteriores, junto ao contrato na listagem e no Dashboard, informando o número de dias restantes.
4. THE Alerta_Service SHALL calcular os dias restantes com base na data atual do servidor no momento do carregamento da tela.
5. WHILE um contrato está com status "Cancelado", THE Alerta_Service SHALL não emitir alertas de vencimento para esse contrato.
6. IF a data_fim de um contrato com status "Ativo" ou "Renovação Pendente" é anterior ou igual à data atual, THEN THE Alerta_Service SHALL exibir um indicador visual de nível 4 (vencido), distinto dos demais, informando que o contrato está vencido.

---

### Requirement 6: Dashboard de Métricas

**User Story:** Como membro da equipe, quero visualizar métricas consolidadas de MRR, contratos ativos e status no Dashboard, para que eu tenha uma visão executiva do portfólio de agentes de IA gerenciados.

#### Acceptance Criteria

1. THE Dashboard SHALL exibir o MRR total calculado como a soma dos valores_mensais de todos os contratos com status "Ativo", formatado como valor monetário com duas casas decimais.
2. THE Dashboard SHALL exibir a contagem total de contratos agrupados por status: "Ativo", "Em Implantação", "Renovação Pendente" e "Cancelado".
3. THE Dashboard SHALL exibir um gráfico de vencimentos mostrando a distribuição de contratos por faixa de dias restantes até a data de término: vencidos (0 dias ou menos), 1 a 7 dias, 8 a 15 dias, 16 a 30 dias e acima de 30 dias, considerando todos os contratos com status diferente de "Cancelado".
4. WHEN um Usuário_Interno acessa o Dashboard, THE Dashboard SHALL carregar e exibir todas as métricas em no máximo 5 segundos, com dados refletindo o estado atual do banco de dados no momento do acesso.
5. IF uma consulta ao banco de dados falha durante o carregamento do Dashboard, THEN THE Dashboard SHALL exibir uma mensagem de erro indicando falha no carregamento dos dados e apresentar um botão que permite ao usuário retentar o carregamento.

---

### Requirement 7: Segurança e Controle de Acesso por Linha

**User Story:** Como administrador do sistema, quero que o banco de dados aplique políticas de segurança em nível de linha, para que cada usuário acesse apenas os dados autorizados para o seu perfil.

#### Acceptance Criteria

1. THE Sistema SHALL habilitar Row Level Security (RLS) nas tabelas clientes, contratos e escopo_agentes no Supabase, cobrindo todas as operações DML (SELECT, INSERT, UPDATE, DELETE).
2. IF uma requisição ao Supabase é realizada sem token de autenticação válido, THEN THE Sistema SHALL retornar zero registros ou rejeitar a operação nas tabelas protegidas por RLS.
3. THE Auth_Service SHALL transmitir o token JWT do usuário autenticado no cabeçalho de autorização de todas as requisições ao Supabase.
4. IF o token JWT transmitido está expirado ou é inválido, THEN THE Sistema SHALL rejeitar a requisição e sinalizar ao Auth_Service que o usuário deve ser reautenticado.
5. THE Sistema SHALL utilizar a chave `service_role` do Supabase exclusivamente no servidor, apenas dentro do Auth_Service e apenas para a criação de credenciais de novos membros da equipe. A chave SHALL NOT ser armazenada em `st.session_state`, exibida na interface, registrada em logs ou referenciada por módulos de interface.
6. THE Sistema SHALL definir as políticas de RLS com a cláusula `TO authenticated`, concedendo acesso completo (SELECT, INSERT, UPDATE, DELETE) apenas a usuários autenticados e nenhum acesso ao papel `anon`.

---

### Requirement 8: Cache de Consultas

**User Story:** Como membro da equipe, quero que as consultas ao banco de dados sejam cacheadas, para que a navegação entre telas seja mais rápida e o número de requisições ao Supabase seja reduzido.

#### Acceptance Criteria

1. THE Sistema SHALL aplicar o decorator @st.cache_data com TTL de 300 segundos às leituras de clientes, contratos e escopos na camada de serviços de dados (`services/`), que encapsula as funções dos repositórios. Os repositórios SHALL permanecer livres de cache e de qualquer referência a `st.*` (ver Requisito 9.1).
2. WHEN os dados de clientes, contratos ou escopos são alterados por uma operação de escrita bem-sucedida, THE Sistema SHALL invocar `.clear()` na função de leitura cacheada de cada entidade afetada (incluindo entidades alteradas em cascata, como contratos cancelados na inativação de um cliente), garantindo que a próxima leitura reflita os dados atualizados.
3. IF a invalidação do cache falha após uma operação de escrita já persistida no banco de dados, THEN THE Sistema SHALL manter a escrita (que já foi confirmada pelo banco) e exibir um aviso ao usuário indicando que os dados exibidos podem estar desatualizados e que a página deve ser recarregada.
4. WHILE as políticas de RLS concederem o mesmo conjunto de dados a todos os usuários autenticados, THE Sistema MAY compartilhar o cache de leitura entre sessões. IF as políticas de RLS passarem a restringir dados por usuário, THEN THE Sistema SHALL incluir o identificador do usuário na chave do cache.

---

### Requirement 9: Estrutura de Código e Separação de Responsabilidades

**User Story:** Como desenvolvedor, quero que o código siga um padrão de repositório separando as chamadas ao Supabase da lógica de interface, para que o sistema seja manutenível e testável ao longo do tempo.

#### Acceptance Criteria

1. THE Sistema SHALL organizar o código em camadas de forma verificável:
   - módulos de repositório (`repositories/`) SHALL NOT conter referências a `st.*` e SHALL receber o cliente Supabase da sessão como parâmetro, sem depender de estado global;
   - módulos de interface (`app.py`, `pages/`) SHALL NOT conter chamadas diretas ao cliente Supabase (incluindo `supabase.auth.*`) nem importar repositórios, acessando dados apenas via `services/` e autenticação apenas via `auth/`.
2. THE Sistema SHALL estruturar as telas da aplicação nos seguintes arquivos, na raiz do projeto: app.py (Login), pages/1_Dashboard.py (Dashboard), pages/2_Clientes.py (Clientes), pages/3_Contratos.py (Contratos) e pages/4_Configuracoes.py (Configurações).
3. THE Sistema SHALL expor na tela de Configurações a edição dos campos nome e e-mail do perfil do usuário autenticado, e, apenas para usuários com perfil "admin" (ver Requisito 11), o cadastro de novos membros da equipe mediante informação de nome e e-mail válido, onde THE Auth_Service SHALL criar a credencial de acesso com uma senha temporária gerada automaticamente sem enviar e-mail de convite.
4. WHEN o Auth_Service cria um novo membro da equipe, THE Sistema SHALL exibir a senha temporária gerada uma única vez na tela, para que o usuário que realizou o cadastro a repasse ao novo membro, e SHALL NOT persistir a senha em `st.session_state`, logs ou banco de dados da aplicação.
5. WHEN o usuário altera o próprio e-mail na tela de Configurações, THE Sistema SHALL informar que a alteração pode depender de confirmação pelo link enviado pelo Supabase Auth ao novo endereço, conforme a configuração "Secure email change" do projeto Supabase.

---

### Requirement 11: Perfil de Acesso Admin

**User Story:** Como administrador, quero que apenas usuários com perfil Admin possam cadastrar novos membros da equipe, para controlar quem recebe acesso ao sistema.

#### Acceptance Criteria

1. THE Sistema SHALL suportar dois perfis de acesso: "admin" e "membro". Usuários sem perfil definido SHALL ser tratados como "membro".
2. THE Sistema SHALL armazenar o perfil de acesso no campo `app_metadata.role` do usuário no Supabase Auth, que só pode ser alterado com a chave `service_role`, de modo que um usuário não consiga elevar o próprio perfil. O campo `user_metadata` SHALL NOT ser usado para determinar permissões.
3. WHILE o usuário autenticado não tiver perfil "admin", THE Sistema SHALL ocultar a seção "Novo Membro da Equipe" na tela de Configurações.
4. WHEN o Auth_Service recebe uma solicitação de criação de membro, THE Auth_Service SHALL verificar no servidor, consultando o Supabase Auth no momento da operação, se o usuário solicitante tem perfil "admin", e SHALL rejeitar a operação com mensagem de permissão negada caso contrário, mesmo que a interface tenha sido contornada.
5. WHEN um Admin cadastra um novo membro, THE Sistema SHALL permitir escolher o perfil do novo usuário entre "membro" (padrão) e "admin".
6. THE Sistema SHALL fornecer um script SQL para definir o primeiro Admin do projeto (bootstrap), a ser executado manualmente no SQL Editor do Supabase.
7. THE Sistema SHALL exibir o perfil do usuário autenticado na barra lateral da aplicação.

---

### Requirement 10: Aparência

**User Story:** Como membro da equipe, quero uma interface com tema escuro corporativo, para uso prolongado com conforto visual.

#### Acceptance Criteria

1. THE Sistema SHALL aplicar um tema escuro (dark mode) corporativo definido em `.streamlit/config.toml`.
2. THE Alerta_Service SHALL apresentar os quatro níveis de alerta (atenção, urgente, crítico, vencido) com ícone e cor distintos, sem depender exclusivamente da cor para diferenciá-los.

