# Manual do usuário

> Público: equipe que usa o CRM no dia a dia.

O CRM para Agentes de IA reúne os **clientes**, os **contratos** de agentes de IA e o **escopo técnico** de cada agente, e mostra a **receita mensal recorrente (MRR)** e os **contratos perto do vencimento**.

## Entrar e sair

1. Abra o endereço do CRM informado pela equipe.
2. Informe **E-mail** e **Senha** e clique em **Entrar**.
3. Para sair, clique em **Sair** na barra lateral.

Bom saber:

- Se o e-mail ou a senha estiverem errados, aparece "E-mail ou senha inválidos.". Por segurança, o sistema não diz qual dos dois está errado.
- Depois de **5 tentativas erradas seguidas**, o acesso daquele e-mail fica **bloqueado por 15 minutos**.
- A sessão dura até **8 horas**. Depois disso, ou se você **recarregar a página (F5)**, será preciso entrar de novo.
- Recebeu uma senha temporária de um administrador? Use-a no primeiro acesso e peça orientação para trocá-la.

A barra lateral mostra seu nome, e-mail e perfil (**Admin** ou **Membro**) e dá acesso às telas: **Dashboard**, **Clientes**, **Contratos** e **Configuracoes**.

## Dashboard

Visão geral do portfólio.

| Bloco | O que mostra |
|---|---|
| **MRR total** | Soma do valor mensal de todos os contratos com status **Ativo** |
| **Contratos ativos** / **Total de contratos** | Quantidades atuais |
| **Contratos por status** | Quantos contratos há em cada status: Ativo, Em Implantação, Renovação Pendente e Cancelado |
| **Vencimentos** | Gráfico com quantos contratos vencem em cada faixa: vencidos, 1-7, 8-15, 16-30 e mais de 30 dias (contratos cancelados não entram) |
| **Alertas de vencimento** | Lista dos contratos Ativos ou em Renovação Pendente que vencem em até 30 dias ou já venceram |

O botão **Atualizar dados** busca as informações mais recentes no banco. Use-o quando um colega acabou de fazer uma alteração: o sistema guarda os dados por até 5 minutos para ficar mais rápido.

### Indicadores de alerta

| Indicador | Significado |
|---|---|
| 🟡 Atenção · N dias | Vence em 16 a 30 dias |
| 🟠 Urgente · N dias | Vence em 8 a 15 dias |
| 🔴 Crítico · N dias | Vence em até 7 dias |
| ⛔ Vencido | A data de término já chegou ou passou |

Só contratos **Ativos** ou em **Renovação Pendente** recebem alertas. Contratos **Em Implantação** e **Cancelados** não recebem.

## Clientes

### Cadastrar um cliente

1. Abra **➕ Novo cliente**.
2. Preencha **Razão social**, **CNPJ**, **Nome do contato** e **E-mail** (obrigatórios) e, se quiser, **Telefone**.
3. Clique em **Cadastrar**.

- O CNPJ pode ser digitado com ou sem pontuação (`12.345.678/0001-90` ou `12345678000190`).
- Cada CNPJ só pode ser cadastrado uma vez. Se ele já existir, aparece "CNPJ já cadastrado na base de dados." e o que você digitou continua no formulário.

### Buscar

Use o campo de busca acima da tabela:

- digite **parte da razão social** (ex.: `acme`) para ver todos que contêm o termo;
- digite o **CNPJ completo** (com ou sem pontuação) para encontrar exatamente aquele cliente.

### Editar

1. Clique na linha do cliente na tabela.
2. Altere **Razão social**, **Nome do contato**, **E-mail** ou **Telefone**.
3. Clique em **Salvar alterações**.

O **CNPJ não pode ser alterado**. Se ele foi cadastrado errado, fale com um administrador.

### Inativar

1. Selecione o cliente e clique em **Inativar cliente**.
2. Leia o aviso e clique em **Inativar** para confirmar (ou **Voltar** para desistir).

O que acontece:

- o cliente continua na lista com o status **Inativo** (nada é apagado);
- os contratos dele que estavam **Ativo** ou **Em Implantação** passam automaticamente para **Cancelado**;
- contratos em **Renovação Pendente** não mudam;
- não é possível criar novos contratos para esse cliente.

## Contratos

### Cadastrar um contrato

1. Abra **➕ Novo contrato**.
2. Escolha o **Cliente** (só aparecem clientes ativos).
3. Preencha **Título do projeto**, **Status**, **Início**, **Término**, **Valor mensal (MRR)** e, se houver, **Setup fee**.
4. Clique em **Cadastrar contrato**.

Regras:

- O **Término** precisa ser depois do **Início**.
- O **Valor mensal** deve estar entre R$ 0,01 e R$ 999.999.999,99.
- O **Setup fee** é a taxa de implantação, cobrada à parte; pode ser zero.
- Status possíveis: **Ativo**, **Em Implantação**, **Renovação Pendente** e **Cancelado**.

Se algo estiver errado, a mensagem explica o motivo e os dados digitados continuam no formulário.

### Filtrar e acompanhar

Use os filtros **Cliente** e **Status** acima da tabela. A coluna **Alerta** mostra o indicador de vencimento de cada contrato (veja [Indicadores de alerta](#indicadores-de-alerta)).

### Editar ou mudar o status

1. Clique na linha do contrato.
2. Na aba **Detalhes do contrato**, altere o que precisar, inclusive o **Status**.
3. Clique em **Salvar alterações**. A tabela é atualizada na hora.

O cliente de um contrato não pode ser trocado.

### Cancelar

1. Selecione o contrato e clique em **Cancelar contrato**.
2. Confirme no aviso.

O contrato passa para **Cancelado** e continua no histórico.

### Escopo do agente

Cada contrato pode ter um escopo técnico do agente de IA. Selecione o contrato e abra a aba **Escopo do agente**.

| Campo | Regra |
|---|---|
| **Tipo de arquitetura** | Texto livre, obrigatório (ex.: "RAG com agente orquestrador") |
| **Limite de requisições** | Número inteiro de 1 a 10.000.000 |
| **Horas de manutenção** | De 0,5 a 8.760, com no máximo uma casa decimal |
| **Modelos permitidos** | Um modelo por linha; de 1 a 50 modelos, cada um com até 100 caracteres |

Clique em **Cadastrar escopo** (primeira vez) ou **Salvar escopo** (alterações). O escopo fica sempre ligado ao mesmo contrato.

## Configurações

### Meu perfil

Altere seu **Nome** e **E-mail** e clique em **Salvar perfil**.

Ao trocar o e-mail, pode aparecer o aviso de que um link de confirmação foi enviado ao novo endereço. Nesse caso, a troca só vale depois que você clicar no link.

### Novo membro da equipe (somente Admin)

1. Preencha **Nome**, **E-mail** e escolha o **Perfil** (**Membro** ou **Admin**).
2. Clique em **Cadastrar membro**.
3. **Copie a senha temporária exibida** e repasse ao novo membro por um canal seguro.

A senha temporária aparece **uma única vez**. Se você sair da página sem copiá-la, peça a um administrador para redefinir a senha pelo painel do Supabase.

Nenhum e-mail de convite é enviado. Membros que não são Admin veem apenas o aviso de que o cadastro é restrito a administradores.

## Perguntas frequentes

**Apaguei um cliente sem querer?**
Não é possível apagar. O máximo é inativar, e o registro continua no histórico.

**Por que um contrato não aparece nos alertas?**
Alertas só valem para contratos **Ativos** ou em **Renovação Pendente** que vencem em até 30 dias ou já venceram.

**O MRR não inclui contratos em implantação?**
Não. O MRR soma apenas contratos com status **Ativo**.

**Um colega alterou um dado e eu não vejo.**
Clique em **Atualizar dados** no Dashboard ou aguarde até 5 minutos.

**Fui desconectado.**
A sessão termina após 8 horas, ao recarregar a página ou ao clicar em **Sair**. Basta entrar de novo.
