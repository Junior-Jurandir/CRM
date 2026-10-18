-- =============================================================================
-- CRM para Agentes de IA — 02: Funções e triggers de integridade
-- Executar após 01_schema.sql. Script idempotente.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Inativação atômica de cliente com cancelamento em cascata (Req 2.5, 2.7, 2.8)
-- Retorna a quantidade de contratos cancelados.
-- SECURITY INVOKER: respeita o RLS do usuário que chama.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.inativar_cliente(p_cliente_id uuid)
RETURNS integer
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cancelados integer;
BEGIN
    UPDATE clientes
       SET ativo = false,
           inativado_em = now()
     WHERE id = p_cliente_id
       AND ativo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cliente não encontrado ou já inativo.' USING ERRCODE = 'P0002';
    END IF;

    UPDATE contratos
       SET status = 'Cancelado'
     WHERE cliente_id = p_cliente_id
       AND status IN ('Ativo', 'Em Implantação');

    GET DIAGNOSTICS v_cancelados = ROW_COUNT;
    RETURN v_cancelados;
END
$$;

REVOKE ALL ON FUNCTION public.inativar_cliente(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.inativar_cliente(uuid) FROM anon;
GRANT EXECUTE ON FUNCTION public.inativar_cliente(uuid) TO authenticated;

-- -----------------------------------------------------------------------------
-- Contrato só pode ser criado para cliente ativo (Req 2.6, 3.2)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.verificar_cliente_ativo()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM clientes WHERE id = NEW.cliente_id AND ativo) THEN
        RAISE EXCEPTION 'O cliente selecionado está inativo.' USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_contratos_cliente_ativo ON public.contratos;
CREATE TRIGGER trg_contratos_cliente_ativo
    BEFORE INSERT ON public.contratos
    FOR EACH ROW EXECUTE FUNCTION public.verificar_cliente_ativo();

-- -----------------------------------------------------------------------------
-- contrato_id do escopo é imutável (Req 4.11)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.impedir_troca_contrato_escopo()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    IF NEW.contrato_id IS DISTINCT FROM OLD.contrato_id THEN
        RAISE EXCEPTION 'O campo contrato_id não pode ser alterado.' USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_escopo_contrato_imutavel ON public.escopo_agentes;
CREATE TRIGGER trg_escopo_contrato_imutavel
    BEFORE UPDATE ON public.escopo_agentes
    FOR EACH ROW EXECUTE FUNCTION public.impedir_troca_contrato_escopo();
