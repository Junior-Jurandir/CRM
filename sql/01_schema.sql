-- =============================================================================
-- CRM para Agentes de IA — 01: Esquema (tabelas, constraints e índices)
-- Executar no SQL Editor do Supabase. Script idempotente.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- busca parcial (ILIKE) indexada

-- -----------------------------------------------------------------------------
-- clientes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clientes (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    razao_social  VARCHAR(255) NOT NULL,
    cnpj          CHAR(14)     NOT NULL,
    contato_nome  VARCHAR(150) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    telefone      VARCHAR(20),
    ativo         BOOLEAN      NOT NULL DEFAULT true,
    inativado_em  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT clientes_cnpj_key        UNIQUE (cnpj),
    CONSTRAINT clientes_cnpj_formato    CHECK (cnpj ~ '^[0-9]{14}$'),
    CONSTRAINT clientes_email_formato   CHECK (email LIKE '%_@_%._%'),
    CONSTRAINT clientes_inativacao      CHECK (ativo OR inativado_em IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_clientes_razao_social
    ON public.clientes USING gin (razao_social gin_trgm_ops);

-- -----------------------------------------------------------------------------
-- contratos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.contratos (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id      UUID          NOT NULL REFERENCES public.clientes (id),
    titulo_projeto  VARCHAR(255)  NOT NULL,
    status          VARCHAR(30)   NOT NULL,
    data_inicio     DATE          NOT NULL,
    data_fim        DATE          NOT NULL,
    valor_mensal    NUMERIC(15,2) NOT NULL,
    setup_fee       NUMERIC(15,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT contratos_status_valido CHECK (
        status IN ('Ativo', 'Em Implantação', 'Renovação Pendente', 'Cancelado')
    ),
    CONSTRAINT contratos_datas_validas CHECK (data_fim > data_inicio),
    CONSTRAINT contratos_valor_mensal  CHECK (valor_mensal BETWEEN 0.01 AND 999999999.99),
    CONSTRAINT contratos_setup_fee     CHECK (setup_fee BETWEEN 0 AND 999999999.99)
);

CREATE INDEX IF NOT EXISTS idx_contratos_cliente_id ON public.contratos (cliente_id);
CREATE INDEX IF NOT EXISTS idx_contratos_status     ON public.contratos (status);
CREATE INDEX IF NOT EXISTS idx_contratos_data_fim   ON public.contratos (data_fim);

-- -----------------------------------------------------------------------------
-- escopo_agentes (1:1 com contratos)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.escopo_agentes (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    contrato_id         UUID         NOT NULL REFERENCES public.contratos (id),
    tipo_arquitetura    TEXT         NOT NULL,
    limite_requisicoes  INTEGER      NOT NULL,
    horas_manutencao    NUMERIC(7,1) NOT NULL,
    modelos_permitidos  JSONB        NOT NULL,

    CONSTRAINT escopo_agentes_contrato_id_key UNIQUE (contrato_id),
    CONSTRAINT escopo_limite_requisicoes CHECK (limite_requisicoes BETWEEN 1 AND 10000000),
    CONSTRAINT escopo_horas_manutencao   CHECK (horas_manutencao BETWEEN 0.5 AND 8760),
    CONSTRAINT escopo_modelos_permitidos CHECK (
        jsonb_typeof(modelos_permitidos) = 'array'
        AND jsonb_array_length(modelos_permitidos) BETWEEN 1 AND 50
    )
);
