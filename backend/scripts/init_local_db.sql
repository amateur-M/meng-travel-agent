-- CoupleTrip — local development database bootstrap (PostgreSQL 15+).
--
-- Run once as a superuser from the repository root:
--
--   "D:\Software\Postgresql18\bin\psql.exe" -U postgres -h 127.0.0.1 -f backend/scripts/init_local_db.sql
--
-- psql will prompt for the postgres password interactively, so the secret
-- never has to be pasted into a shell history, a config file, or a chat.
--
-- Safe to re-run: the role is created if missing and its password reset to the
-- value expected by backend/.env (PG_DSN). The database is only created when
-- absent, so existing local data is never dropped.
--
-- This matches docker-compose.yml, which passes the same credentials to the
-- postgres:16-alpine service via POSTGRES_USER/POSTGRES_PASSWORD.

\set ON_ERROR_STOP on

\echo '==> Ensuring role "coupletrip" exists with the .env password'

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'coupletrip') THEN
        ALTER ROLE coupletrip WITH LOGIN PASSWORD 'coupletrip_dev';
        RAISE NOTICE 'role coupletrip already existed - password reset';
    ELSE
        CREATE ROLE coupletrip WITH LOGIN PASSWORD 'coupletrip_dev';
        RAISE NOTICE 'role coupletrip created';
    END IF;
END
$$;

\echo '==> Ensuring database "coupletrip" exists (owned by coupletrip)'

-- CREATE DATABASE cannot run inside a transaction block, so it is generated
-- conditionally and executed by psql via \gexec.
SELECT 'CREATE DATABASE coupletrip OWNER coupletrip ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'coupletrip')
\gexec

\echo '==> Verifying the application can connect and create tables'

-- Connect as the application role and confirm it owns a writable schema.
\connect coupletrip coupletrip

SELECT current_user AS connected_as,
       current_database() AS database,
       has_schema_privilege(current_user, 'public', 'CREATE') AS can_create_in_public;

CREATE TABLE IF NOT EXISTS _bootstrap_check (id INT PRIMARY KEY);
DROP TABLE _bootstrap_check;

\echo '==> Done. backend/.env PG_DSN should now connect successfully.'
