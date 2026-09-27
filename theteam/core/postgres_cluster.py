#!/usr/bin/env python3
"""
PostgreSQL cluster support: connection pooling, read replicas, and failover.

Phase 4 deliverable. `psycopg2` is imported lazily so this module imports
cleanly without it installed, and no method requires a live server except the
ones that explicitly connect.

Topology:
    primary  (reads + writes)
      |
      +-- replica[0]  (reads only)
      +-- replica[1]  (reads only)
    standby            (promoted to primary if the primary is unreachable)

Reads go to a replica when one is healthy and fall back to the primary.
Reads must never go to the standby - it is not serving until promoted.
"""

import logging
import os
import socket
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote, urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FailoverError(RuntimeError):
    """Raised when no writable primary can be established."""


class PostgresClusterConfig:
    """
    Connection settings for the cluster, sourced from the environment.

    `DATABASE_URL` takes precedence when set, because that is what the
    container images provide.
    """

    def __init__(
        self,
        primary_host: str = "localhost",
        standby_host: Optional[str] = None,
        replica_hosts: Optional[List[str]] = None,
        port: int = 5432,
        database: str = "theteam",
        user: str = "postgres",
        password: str = "",
        pool_min: int = 1,
        pool_max: int = 10,
        connect_timeout: int = 2,
    ) -> None:
        self.primary_host = primary_host
        self.standby_host = standby_host
        self.replica_hosts = list(replica_hosts or [])
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool_min = pool_min
        self.pool_max = pool_max
        # Failover must not hang: a dead primary should be detected fast.
        self.connect_timeout = connect_timeout

    @classmethod
    def from_env(cls, environ: Optional[Dict[str, str]] = None) -> "PostgresClusterConfig":
        """Build a config from environment variables, with sane defaults."""
        env = os.environ if environ is None else environ

        replicas_raw = env.get("PG_REPLICA_HOSTS", "")
        replicas = [h.strip() for h in replicas_raw.split(",") if h.strip()]

        config = cls(
            primary_host=env.get("PG_PRIMARY_HOST") or env.get("PG_HOST", "localhost"),
            standby_host=env.get("PG_STANDBY_HOST") or None,
            replica_hosts=replicas,
            port=_int(env.get("PG_PORT"), 5432),
            database=env.get("PG_DATABASE", "theteam"),
            user=env.get("PG_USER", "postgres"),
            password=env.get("PG_PASSWORD", ""),
            pool_min=_int(env.get("PG_POOL_MIN"), 1),
            pool_max=_int(env.get("PG_POOL_MAX"), 10),
            connect_timeout=_int(env.get("PG_CONNECT_TIMEOUT"), 2),
        )
        # DATABASE_URL is authoritative when set: the container images provide
        # it, and it already carries credentials and database name. Without
        # this it was assigned and never read, so production would connect as
        # the default user with an empty password.
        config.database_url = env.get("DATABASE_URL") or None
        if config.database_url:
            config._apply_database_url(config.database_url)
        return config

    def _apply_database_url(self, url: str) -> None:
        """
        Overlay connection settings parsed from a DATABASE_URL.

        Every field access is guarded, not just urlparse itself: `.port`
        raises ValueError for a non-numeric port, and `.hostname`/`.port` are
        properties evaluated lazily. A malformed URL must degrade to the
        PG_* settings rather than crash startup.
        """
        # Read every field that can raise BEFORE mutating self. `.port` raises
        # ValueError on a non-numeric port, and assigning hostname first would
        # leave a split-half config: host from the rejected URL, credentials
        # from PG_*. Either the whole URL applies or none of it does.
        try:
            parsed = urlparse(url)
            host, port = parsed.hostname, parsed.port
        except ValueError as e:
            logger.warning(f"Ignoring malformed DATABASE_URL host/port: {e}")
            return

        if host:
            self.primary_host = host
        if port:
            self.port = port

        # urlparse does NOT percent-decode userinfo, so a password containing
        # @ : / would be sent literally and authentication would fail.
        if parsed.username:
            self.user = unquote(parsed.username)
        # `parsed.password` is None when absent but '' when written as ':'
        # with an empty secret; either way an explicit value should win.
        if parsed.password is not None:
            self.password = unquote(parsed.password)
        database = unquote((parsed.path or "").lstrip("/"))
        if database:
            self.database = database

    def dsn(self, host: Optional[str] = None, database: Optional[str] = None) -> Dict[str, Any]:
        """Build psycopg2 connect kwargs for a host."""
        return {
            "host": host or self.primary_host,
            "port": self.port,
            "dbname": database or self.database,
            "user": self.user,
            "password": self.password,
            "connect_timeout": self.connect_timeout,
        }

    def primary_dsn(self) -> Dict[str, Any]:
        """Connect kwargs for the writable primary."""
        return self.dsn(self.primary_host)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config for status endpoints (password redacted)."""
        return {
            "primary_host": self.primary_host,
            "standby_host": self.standby_host,
            "replica_hosts": list(self.replica_hosts),
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "pool_min": self.pool_min,
            "pool_max": self.pool_max,
            "connect_timeout": self.connect_timeout,
        }


def _int(value: Optional[str], default: int) -> int:
    """Parse an int env var, falling back to the default when unusable."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class FailoverManager:
    """
    Tracks which host is writable and promotes the standby on primary loss.

    Liveness is a short TCP connect: no authentication or query is needed to
    decide whether a node is reachable, which keeps the check fast enough to
    sit in a health loop.
    """

    def __init__(self, config: PostgresClusterConfig,
                 promote: Optional[Callable[[str], None]] = None) -> None:
        self.config = config
        self._primary = config.primary_host
        self._failover_count = 0
        self._last_error: Optional[str] = None
        # Promotion is not a TCP-level concern. A standby is a read-only
        # replica until something runs `pg_ctl promote`; simply repointing
        # `self._primary` at it yields a "primary" that rejects every write.
        # The caller supplies the real promotion (psql/pg_ctl); tests inject
        # a recorder. When absent, failover stays advisory and says so.
        self._promote = promote

    # -- liveness ----------------------------------------------------------

    def is_host_alive(self, host: Optional[str]) -> bool:
        """Return True if a TCP connection to `host:port` succeeds."""
        if not host:
            return False
        try:
            with socket.create_connection(
                (host, self.config.port), timeout=self.config.connect_timeout
            ):
                return True
        except OSError:
            return False

    # -- state -------------------------------------------------------------

    def current_primary(self) -> str:
        """The host currently accepting writes."""
        return self._primary

    def failover(self) -> str:
        """
        Promote the standby when the primary is unreachable.

        Returns the host now serving writes. Raises `FailoverError` if the
        primary is still healthy (nothing to do) or no candidate is available.
        """
        if self.is_host_alive(self._primary):
            raise FailoverError(f"Primary {self._primary} is still alive; refusing to fail over")

        standby = self.config.standby_host
        if not self.is_host_alive(standby):
            raise FailoverError(
                f"Primary {self._primary} is down and standby {standby!r} is unreachable"
            )

        logger.error(f"Primary {self._primary} unreachable; promoting standby {standby}")
        if self._promote is not None:
            # A standby that is not promoted stays read-only, so promotion must
            # happen BEFORE the host is recorded as the new primary.
            self._promote(standby)
        else:
            logger.warning(
                "No promotion callback configured; the new primary is recorded "
                "but a real cluster would still reject writes until promoted"
            )

        self._last_error = f"promoted {standby} after {self._primary} failed"
        self._primary = standby
        self._failover_count += 1
        return standby

    def status(self) -> Dict[str, Any]:
        """Report cluster topology and liveness. Never raises."""
        return {
            "primary": self._primary,
            "standby": self.config.standby_host,
            "replicas": list(self.config.replica_hosts),
            "failovers": self._failover_count,
            "primary_alive": self.is_host_alive(self._primary),
            "standby_alive": self.is_host_alive(self.config.standby_host),
            "replica_alive": {r: self.is_host_alive(r) for r in self.config.replica_hosts},
            "last_error": self._last_error,
        }


class ReadReplicaRouter:
    """
    Routes reads to a healthy replica, falling back to the primary.

    Round-robin across healthy replicas. The standby is never a read target:
    it is either down or a demoted node, and reading from it risks staleness
    or split-brain once promoted.
    """

    def __init__(self, config: PostgresClusterConfig, failover: Optional[FailoverManager] = None) -> None:
        self.config = config
        self.failover = failover or FailoverManager(config)
        self.unhealthy_replicas: set = set()
        # Round-robin start offset. A bare `itertools.cycle` cannot be used:
        # it advances on every __next__, including ones skipped by a failed
        # liveness check, which permanently rotates out healthy replicas.
        self._offset = 0

    def healthy_replicas(self) -> List[str]:
        """Replicas that answered the last liveness check."""
        return [r for r in self.config.replica_hosts if r not in self.unhealthy_replicas]

    def read_conn(self) -> Dict[str, Any]:
        """
        Return connect kwargs for a read query.

        Round-robins across healthy replicas. A replica that fails the TCP
        check is marked unhealthy and skipped; when none is healthy the read
        falls back to the primary so reads still succeed during an outage.
        """
        candidates = self.healthy_replicas()
        for step in range(len(candidates)):
            host = candidates[(self._offset + step) % len(candidates)]
            if self.failover.is_host_alive(host):
                # Advance only on a served read, so an outage cannot skip
                # past a replica that has since recovered.
                self._offset = (self._offset + step + 1) % len(candidates)
                return self.config.dsn(host)
            self.unhealthy_replicas.add(host)
            logger.warning(f"Replica {host} unreachable; excluding from reads")

        # Nothing healthy on the replica side: serve from the primary.
        return self.config.dsn(self.failover.current_primary())

    def mark_healthy(self, host: str) -> None:
        """Return a replica to the read pool after recovery."""
        self.unhealthy_replicas.discard(host)


class ConnectionPool:
    """
    Threaded psycopg2 connection pool, created lazily.

    Exists so the rest of the module can treat "pooled connections" and "raw
    connections" identically without importing psycopg2 at module load.
    """

    def __init__(self, config: PostgresClusterConfig) -> None:
        self.config = config
        self._pool: Any = None

    def _ensure(self) -> Any:
        if self._pool is not None:
            return self._pool
        try:
            import psycopg2.pool
        except ImportError as e:
            raise ImportError(
                "psycopg2 is required for PostgreSQL. Install it with "
                "`pip install psycopg2-binary` or `pip install .[postgres]`."
            ) from e

        self._pool = psycopg2.pool.ThreadedConnectionPool(
            self.config.pool_min,
            self.config.pool_max,
            **self.config.primary_dsn(),
        )
        logger.info(
            f"PostgreSQL pool ready ({self.config.pool_min}-{self.config.pool_max}) "
            f"against {self.config.primary_host}"
        )
        return self._pool

    def getconn(self) -> Any:
        """Check out a pooled connection."""
        return self._ensure().getconn()

    def putconn(self, conn: Any) -> None:
        """Return a connection to the pool."""
        if self._pool is not None:
            self._pool.putconn(conn)

    def closeall(self) -> None:
        """Close the pool. Safe when never opened."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
