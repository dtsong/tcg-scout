-- Enable Row Level Security on all labs tables.
--
-- No policies are attached: this locks the tables to the service role only
-- (which bypasses RLS), blocking the anon/authenticated roles used by the
-- Supabase client libraries. Scout reads data at build time via the service
-- role / direct connection, so the ingestion pipeline is unaffected.
--
-- Note: the public.rls_auto_enable() event trigger only auto-enables RLS for
-- tables in the `public` schema, so labs tables must be enabled explicitly.

ALTER TABLE labs.tournaments       ENABLE ROW LEVEL SECURITY;
ALTER TABLE labs.players           ENABLE ROW LEVEL SECURITY;
ALTER TABLE labs.placements        ENABLE ROW LEVEL SECURITY;
ALTER TABLE labs.decklists         ENABLE ROW LEVEL SECURITY;
ALTER TABLE labs.decklist_cards    ENABLE ROW LEVEL SECURITY;
ALTER TABLE labs.matches           ENABLE ROW LEVEL SECURITY;
ALTER TABLE labs.archetype_mapping ENABLE ROW LEVEL SECURITY;
