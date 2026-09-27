#!/bin/sh
# Clone the primary and stream from it.
#
# Used by docker-compose.replication.yml for the standby and read replica.
# Steps, in order:
#   1. wait for the primary to accept connections (never race an empty cluster)
#   2. release a stale replication slot left by a previous run
#   3. pg_basebackup -R  (clones the cluster, writes primary_conninfo)
#   4. ensure standby.signal so the clone starts read-only and follows
#   5. start postgres as the `postgres` user
#
# The `replicator` role and the pg_hba rule are created by bootstrap-hba.sh
# against the primary before this runs; creating them here too would race.
set -eu

: "${DATA:=/var/lib/postgresql/data}"
: "${PGDATABASE:=theteam}"
# Password for the `replicator` clone role, set by bootstrap-hba.sh. It is
# deliberately NOT the admin password the service sets in PGPASSWORD.
: "${REPLICA_PASSWORD:=replicator}"

echo "[$(date +%T)] waiting for primary at $PGHOST:$PGPORT"
i=0
while ! pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    echo "[$(date +%T)] primary never became ready" >&2
    exit 1
  fi
  sleep 1
done
echo "[$(date +%T)] primary is ready"

# A non-empty data dir means a previous run; keep it so the replica can restart
# in place rather than re-cloning a live cluster.
if [ -s "$DATA/PG_VERSION" ]; then
  echo "[$(date +%T)] data dir already initialised, starting in-place"
else
  rm -rf "${DATA:?}"/*

  # A slot left behind by a previous run makes every restart fail with
  # 'replication slot "..." already exists' - pg_basebackup -C cannot create an
  # existing slot, so release it first.
  echo "[$(date +%T)] releasing any stale slot $REPLICA_NAME"
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tAc \
    "SELECT pg_drop_replication_slot('$REPLICA_NAME') FROM pg_replication_slots
     WHERE slot_name = '$REPLICA_NAME' AND NOT active" >/dev/null

  # PGPASSWORD in the environment is the ADMIN password (theteam), but this
  # connects as `replicator`, whose password differs. Without the override the
  # clone sends the admin secret and fails with "password authentication
  # failed for user replicator".
  echo "[$(date +%T)] running pg_basebackup from $PGHOST as replicator"
  PGPASSWORD="$REPLICA_PASSWORD" pg_basebackup \
    -h "$PGHOST" -p "$PGPORT" -U replicator -D "$DATA" -R -X stream -C -S "$REPLICA_NAME"
  echo "[$(date +%T)] base backup complete"
fi

# -R writes primary_conninfo and standby.signal, but be explicit: a replica
# that is not read-only will happily corrupt the primary's WAL stream. A
# replica that accepts writes is NOT a replica.
if [ ! -f "$DATA/standby.signal" ]; then
  touch "$DATA/standby.signal"
  echo "[$(date +%T)] standby.signal created"
else
  echo "[$(date +%T)] standby.signal already present"
fi


# pg_basebackup runs as root here, so it leaves root-owned files behind and the
# server (running as `postgres`) cannot read its own config. Chown is a no-op
# on a restart where nothing changed.
echo "[$(date +%T)] fixing data dir ownership"
chown -R postgres:postgres "$DATA"
chmod 700 "$DATA"

# Run postgres DIRECTLY, as the postgres user. `docker-entrypoint.sh` decides
# whether to run initdb from the POSTGRES_* env vars, and with none set it
# treats the cloned PGDATA as uninitialised - wiping standby.signal and starting
# a WRITABLE primary that also streams. That is why an earlier run accepted a
# CREATE TABLE. The entrypoint also drops privileges via gosu; running the
# binary directly does not, and the server refuses to start as root.
echo "[$(date +%T)] starting postgres as a read-only standby"
exec su postgres -c "postgres -D '$DATA' -c hot_standby=on -c wal_level=logical"
