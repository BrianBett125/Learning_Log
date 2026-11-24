-- Runs once, when the pgvector/pgvector data volume is first created.
--
-- The pgvector image already ships the `vector` extension; enabling it here means
-- later phases can add vector columns without a superuser step at migration time.
-- Plan Phase 1 asks for pgvector "where available": on a PostgreSQL server that
-- does not have the extension, this file is simply never run.
CREATE EXTENSION IF NOT EXISTS vector;
