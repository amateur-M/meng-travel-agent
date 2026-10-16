-- CoupleTrip local development database bootstrap (PostgreSQL 15+).
--
-- Run once as a superuser from the repository root:
--
--   "D:\Software\Postgresql18\bin\psql.exe" -U postgres -h 127.0.0.1 -f backend/scripts/init_local_db.sql
--
-- psql prompts for the postgres password interactively, so the secret never
-- has to be pasted into a shell history, a config file, or a chat.
--
-- To use your own password instead of the documented default, pass it as a
-- psql variable (it never enters this file or the shell history):
--
--   "D:\Software\Postgresql18\bin\psql.exe" -U postgres -h 127.0.0.1 -v new_password=your-password -f backend/scripts/init_local_db.sql
--
-- Safe to re-run. The database is only created when absent, so existing local
-- data is never dropped.
--
-- This file is deliberately PURE ASCII. psql reads it using the client
-- encoding, which on Windows is often a legacy code page (e.g. CP936); a
-- stray non-ASCII byte in a comment can abort the whole script.

\set ON_ERROR_STOP on

-- Store the password as a SCRAM verifier regardless of the server default.
-- If a role's verifier is MD5 while pg_hba.conf demands scram-sha-256,
-- authentication fails even with the *correct* password - which looks exactly
-- like a wrong password and is easy to misdiagnose.
SET password_encryption = 'scram-sha-256';

-- Default to the placeholder documented in backend/.env.example so a plain run
-- on a fresh checkout needs no arguments. Only the DSN in backend/.env (which
-- is gitignored) has to match whatever is set here.
--
-- An existing role's password is deliberately NOT reset unless one was passed
-- explicitly: otherwise a plain re-run would silently undo a deliberate local
-- choice and break backend/.env with no visible cause.
\if :{?new_password}
  \set reset_password yes
\else
  \set new_password coupletrip_dev
  \set reset_password no
\endif

\echo '==> Ensuring role "coupletrip" exists and can log in'

SELECT format('CREATE ROLE coupletrip WITH LOGIN PASSWORD %L', :'new_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'coupletrip')
\gexec

\echo '==> Setting its password (stored as a SCRAM verifier)'

-- format(%L) quotes and escapes the value, so the password is passed in rather
-- than written into this committed file.
SELECT format('ALTER ROLE coupletrip WITH LOGIN PASSWORD %L', :'new_password')
WHERE :'reset_password' = 'yes'
\gexec

SELECT 'existing role left untouched - pass -v new_password=... to reset it' AS note
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'coupletrip')
  AND :'reset_password' = 'no';

\echo '==> Ensuring database "coupletrip" owned by coupletrip'

-- CREATE DATABASE cannot run inside a transaction block, so it is generated
-- conditionally and executed by psql via \gexec.
SELECT 'CREATE DATABASE coupletrip OWNER coupletrip ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'coupletrip')
\gexec

\echo '==> Verification: send this output back if authentication still fails'
\echo '    verifier_prefix must read SCRAM-SHA-256 (never md5...)'

SELECT rolname,
       rolcanlogin AS can_login,
       substring(rolpassword from 1 for 13) AS verifier_prefix
FROM pg_authid
WHERE rolname = 'coupletrip';

SELECT d.datname,
       pg_get_userbyid(d.datdba) AS owner,
       pg_encoding_to_char(d.encoding) AS encoding
FROM pg_database d
WHERE d.datname = 'coupletrip';

\echo '==> Done. Make sure backend/.env PG_DSN carries the same password,'
\echo '    percent-encoding any of @ : / ? # & % that appear in it.'
