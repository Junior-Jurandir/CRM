-- =============================================================================
-- CRM para Agentes de IA — 04: Bootstrap do primeiro Admin (Req 11.6)
--
-- 1. Crie o usuário em Authentication → Users → Add user (Auto Confirm User).
-- 2. Substitua o e-mail abaixo e execute no SQL Editor.
-- 3. O usuário deve fazer login novamente para o perfil aparecer no token.
--
-- O perfil fica em app_metadata (raw_app_meta_data), que o próprio usuário
-- não consegue alterar. Para rebaixar um Admin, troque 'admin' por 'membro'.
-- =============================================================================

UPDATE auth.users
   SET raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role": "admin"}'::jsonb
 WHERE email = 'admin@suaempresa.com.br';   -- <<< substitua pelo e-mail do primeiro Admin

-- Conferência:
SELECT email, raw_app_meta_data ->> 'role' AS perfil
  FROM auth.users
 ORDER BY created_at;
