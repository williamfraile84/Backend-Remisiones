-- ==============================================================================
-- REGLAS DE ENDURECIMIENTO Y REMEDIACIÓN DE SEGURIDAD (SUPABASE SECURITY ADVISOR)
-- ==============================================================================
-- 1. Resolver aviso: "View public.v_pedidos_resumen is defined with the SECURITY DEFINER property"
-- En PostgreSQL 15+, las vistas sin `security_invoker = true` se ejecutan con los permisos del
-- propietario (SECURITY DEFINER), lo que puede eludir las políticas de Row Level Security (RLS)
-- de los usuarios autenticados. Al activar security_invoker = true, la vista respeta el contexto
-- y los permisos del usuario que realiza la consulta.
ALTER VIEW IF EXISTS public.v_pedidos_resumen SET (security_invoker = true);

-- 2. Resolver avisos: "Function public.rls_auto_enable() can be executed by anon / authenticated role"
-- Por defecto en PostgreSQL, las funciones en el esquema public otorgan EXECUTE a PUBLIC.
-- Dado que rls_auto_enable() es una función de disparador de eventos (event trigger) con SECURITY DEFINER,
-- Supabase PostgREST la exponía como RPC pública en /rest/v1/rpc/rls_auto_enable.
-- Revocamos el permiso a PUBLIC, anon y authenticated, dejando únicamente a postgres y service_role.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'rls_auto_enable') THEN
        REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC;
        REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM anon;
        REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM authenticated;
        GRANT EXECUTE ON FUNCTION public.rls_auto_enable() TO postgres;
        GRANT EXECUTE ON FUNCTION public.rls_auto_enable() TO service_role;
    END IF;
END $$;
