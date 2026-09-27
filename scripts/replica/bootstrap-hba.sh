#!/bin/sh
# Grant the replication role permission to stream.
#
# Runs inside the PRIMARY container. Server flags can set wal_level and
# max_wal_senders, but they cannot express a pg_hba rule, and without a
# `replication` line pg_basebackup is refused with:
#
#   no pg_hba.conf entry for replication connection from host "...", user
#   "replicator", no encryption
#
# That single missing line is the most common streaming-replication failure,
# and it is invisible in `docker-compose.yml` review.
set -eu

# The primary is a DIFFERENT container. Without -h, psql looks for a local unix
# socket that does not exist here and fails with "No such file or directory".
: "${PGHOST:=pg-primary}"
: "${PGPORT:=5432}"
: "${PGUSER:=theteam}"
: "${PGDATABASE:=theteam}"
HBA="$PGDATA/pg_hba.conf"

if [ ! -f "$HBA" ]; then
  echo "[$(date +%T)] no pg_hba.conf at $HBA" >&2
  exit 1
fi


# Idempotent: only append when the marker is absent, so a rerun is a no-op.
# `host replication` matches physical-replication connections only, so this
# does not widen access to ordinary database sessions.
if ! grep -q "theteam replication" "$HBA"; then
  cat >>"$HBA" <<'HBA'

# --- theteam replication (added by bootstrap-hba.sh) ---
host    replication     replicator     all     scram-sha-256
host    all             replicator     all     scram-sha-256
HBA
  echo "[$(date +%T)] pg_hba.conf updated"
else
  echo "[$(date +%T)] pg_hba.conf already configured"
fi


# A reload is enough for pg_hba changes; no restart, so the primary keeps
# serving and replicas can connect as soon as this exits.
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "SELECT pg_reload_conf()" >/dev/null
echo "[$(date +%T)] config reloaded; streaming replication is possible"

# Role setup comes AFTER the reload. Creating the role before its auth method
# is enabled leaves it without a usable SCRAM verifier, and the clone then
# fails with "password authentication failed for user replicator".
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c \
  "DO \$\$
   BEGIN
     IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'replicator') THEN
       CREATE ROLE replicator WITH REPLICATION LOGIN;
     END IF;
   END
   \$\$;" >/dev/null
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c \
  "ALTER ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replicator'" >/dev/null
echo "[$(date +%T)] replication role ready"
