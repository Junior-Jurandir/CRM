-- =============================================================================
-- CRM para Agentes de IA — 03: Row Level Security (Req 7.1, 7.2, 7.6)
-- Executar após 02_functions_triggers.sql. Script idempotente.
--
-- Política: qualquer usuário autenticado tem acesso completo; o papel anon
-- não possui política alguma (zero registros / operação rejeitada).
-- =============================================================================

ALTER TABLE public.clientes       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contratos      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.escopo_agentes ENABLE ROW LEVEL SECURITY;

-- Privilégios explícitos: projetos Supabase recentes podem não conceder
-- privilégios automaticamente a tabelas criadas via SQL.
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.clientes, public.contratos, public.escopo_agentes
    TO authenticated, service_role;

-- Defesa adicional: remove privilégios de tabela do papel anon.
REVOKE ALL ON public.clientes       FROM anon;
REVOKE ALL ON public.contratos      FROM anon;
REVOKE ALL ON public.escopo_agentes FROM anon;

DROP POLICY IF EXISTS "authenticated_all" ON public.clientes;
CREATE POLICY "authenticated_all" ON public.clientes
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "authenticated_all" ON public.contratos;
CREATE POLICY "authenticated_all" ON public.contratos
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "authenticated_all" ON public.escopo_agentes;
CREATE POLICY "authenticated_all" ON public.escopo_agentes
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- Recarrega o cache de esquema da API (PostgREST) para expor as tabelas e a RPC.
NOTIFY pgrst, 'reload schema';
