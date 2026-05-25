-- Revoke public EXECUTE on the rls_auto_enable() event-trigger function.
--
-- rls_auto_enable() is a SECURITY DEFINER function backing the `ensure_rls`
-- event trigger. Because it is SECURITY DEFINER and not revoked, Supabase
-- exposes it at /rest/v1/rpc/rls_auto_enable to the anon/authenticated roles.
-- Direct RPC calls are effectively a no-op (pg_event_trigger_ddl_commands()
-- returns nothing outside a DDL event), but there is no reason to expose it
-- on the public API. Revoking clears the database-linter warning.

REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM anon, authenticated, public;
