#!/usr/bin/env python3
"""
Database implementation for theteam.

This module provides database functionality with migrations and connection pooling,
supporting both SQLite (for prototyping) and PostgreSQL (for production).
"""

from __future__ import annotations

import os
import json
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union, Iterator
from pathlib import Path
from contextlib import contextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Phase 4: production PostgreSQL cluster (pooling, read replicas, failover).
#
# Imported inside the three properties that need it, not here. This module is
# on the import path of `theteam.core.state_manager`, which `theteam/__init__`
# imports, so an eager import here meant every `import theteam` loaded the
# PostgreSQL cluster layer (pool, failover, read replicas) - a database tier
# §5.1 never places in this stack. Nothing in the product constructs a
# DatabaseManager with `use_sqlite=False`, so that cost was paid for code no
# caller reached. The objects were already constructed lazily inside the
# properties; this only moves the module load to match.
#
# `ConnectionPool` is aliased because this module defines its own generic
# SQLite pool class further down, and the local definition must keep winning
# for existing callers.

class DatabaseConfig:
    """Database configuration."""
    def __init__(self, db_path: str = "theteam.db",
                 connection_pool_size: int = 10,
                 pool_timeout: int = 30,
                 use_sqlite: bool = True,
                 postgresql_config: Optional[Dict[str, Any]] = None):
        self.db_path = db_path
        self.connection_pool_size = connection_pool_size
        self.pool_timeout = pool_timeout
        self.use_sqlite = use_sqlite
        self.postgresql_config = postgresql_config or {}
        self._pool: List[Any] = []
        self._pool_lock = threading.Lock()

    def get_connection(self):
        """Get a database connection from the pool."""
        with self._pool_lock:
            if not self._pool:
                raise TimeoutError(f"Could not get database connection within {self.pool_timeout} seconds")
            return self._pool.pop()

    def release_connection(self, conn):
        """Release a connection back to the pool."""
        with self._pool_lock:
            self._pool.append(conn)

    def _create_connection_pool(self):
        """Create database connection pool."""
        self._pool.clear()
        
        if self.use_sqlite:
            import sqlite3
            try:
                # Create connection pool
                for _ in range(self.connection_pool_size):
                    conn = sqlite3.connect(self.db_path, timeout=30)
                    conn.row_factory = sqlite3.Row
                    self._pool.append(conn)
            except Exception as e:
                logger.error(f"Error creating SQLite connection pool: {e}")
                # Try to clean up
                if 'conn' in locals():
                    try:
                        conn.close()
                    except OSError as e:
                        logger.warning(f"Failed to close connection during cleanup: {e}")
        else:
            # PostgreSQL connection (simplified implementation)
            try:
                import psycopg2
                from psycopg2 import pool

                # Create connection pool
                self._db_pool = pool.SimpleConnectionPool(
                    1, self.connection_pool_size,
                    **self.postgresql_config
                )

                # Get connections from pool
                for _ in range(self.connection_pool_size):
                    conn = self._db_pool.getconn()
                    self._pool.append(conn)

            except ImportError:
                raise ImportError("psycopg2 required for PostgreSQL")
            except Exception as e:
                logger.error(f"Error creating PostgreSQL connection pool: {e}")

    def close_all_connections(self):
        """Close all connections in the pool."""
        with self._pool_lock:
            for conn in self._pool:
                try:
                    conn.close()
                except OSError as e:
                    logger.warning(f"Failed to close connection during cleanup: {e}")
            self._pool.clear()

    def get_pool_size(self) -> int:
        """Get current pool size."""
        return len(self._pool)

    def get_available_connections(self) -> int:
        """Get number of available connections."""
        return len(self._pool)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all_connections()
class Migration:
    """Database migration."""

    def __init__(self, version: str, name: str, up_sql: str, down_sql: str):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql

    def get_version(self) -> str:
        """Get migration version."""
        return self.version

    def get_name(self) -> str:
        """Get migration name."""
        return self.name

    def execute_up(self, conn):
        """Execute the migration up."""
        try:
            conn.executescript(self.up_sql)
            logger.info(f"Migration {self.version} ({self.name}): Up executed")
        except Exception as e:
            logger.error(f"Error executing migration {self.version} up: {e}")
            raise

    def execute_down(self, conn):
        """Execute the migration down."""
        try:
            conn.executescript(self.down_sql)
            logger.info(f"Migration {self.version} ({self.name}): Down executed")
        except Exception as e:
            logger.error(f"Error executing migration {self.version} down: {e}")
            raise
class DatabaseMigrations:
    """
    Database migration management.

    Handles schema migrations, versioning, and rollback capabilities.
    """

    def __init__(self, db_path: str = "theteam.db", use_sqlite: bool = True):
        self.db_path = db_path
        self.use_sqlite = use_sqlite
        self.migrations: Dict[str, Migration] = {}
        self._register_migrations()

    def _register_migrations(self):
        """Register all migrations."""
        # Migration 001: Initial schema
        self.migrations["001"] = Migration(
            version="001",
            name="Initial schema",
            up_sql=self._get_initial_schema_sql(),
            down_sql=self._get_initial_schema_down_sql()
        )

        # Migration 002: Add event log table
        self.migrations["002"] = Migration(
            version="002",
            name="Event log table",
            up_sql=self._get_event_log_schema_sql(),
            down_sql=self._get_event_log_schema_down_sql()
        )

        # Migration 003: Add WAL table
        self.migrations["003"] = Migration(
            version="003",
            name="WAL table",
            up_sql=self._get_wal_schema_sql(),
            down_sql=self._get_wal_schema_down_sql()
        )

        # Migration 004: Add correlation IDs
        self.migrations["004"] = Migration(
            version="004",
            name="Correlation IDs",
            up_sql=self._get_correlation_ids_sql(),
            down_sql=self._get_correlation_ids_down_sql()
        )

        # Migration 005: Add rate limiting
        self.migrations["005"] = Migration(
            version="005",
            name="Rate limiting",
            up_sql=self._get_rate_limiting_sql(),
            down_sql=self._get_rate_limiting_down_sql()
        )

    def _get_initial_schema_sql(self) -> str:
        """Get SQL for initial schema migration."""
        return """
        -- Create state table
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version TEXT NOT NULL,
            checksum TEXT NOT NULL,
            correlation_id TEXT,
            created_at TEXT NOT NULL
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_state_updated_at ON state(updated_at);
        CREATE INDEX IF NOT EXISTS idx_state_version ON state(version);
        CREATE INDEX IF NOT EXISTS idx_state_correlation_id ON state(correlation_id);

        -- Create metadata table
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- Insert initial metadata
        INSERT OR REPLACE INTO metadata (key, value, updated_at)
        VALUES ('schema_version', '1.0', ?);
        """.replace("?", datetime.now(timezone.utc).isoformat())

    def _get_initial_schema_down_sql(self) -> str:
        """Get SQL for initial schema rollback."""
        return """
        DROP TABLE IF EXISTS state;
        DROP TABLE IF EXISTS metadata;
        """

    def _get_event_log_schema_sql(self) -> str:
        """Get SQL for event log schema migration."""
        return """
        -- Create event_log table
        CREATE TABLE IF NOT EXISTS event_log (
            event_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            data TEXT NOT NULL,
            prev_event_id TEXT,
            event_hash TEXT NOT NULL,
            correlation_id TEXT,
            schema_version TEXT DEFAULT 'event_v1',
            created_at TEXT NOT NULL
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_event_log_event_type ON event_log(event_type);
        CREATE INDEX IF NOT EXISTS idx_event_log_correlation_id ON event_log(correlation_id);
        CREATE INDEX IF NOT EXISTS idx_event_log_schema_version ON event_log(schema_version);

        -- Add foreign key constraint (if supported)
        DO $$ BEGIN
            ALTER TABLE event_log ADD CONSTRAINT fk_event_log_prev_event
            FOREIGN KEY (prev_event_id) REFERENCES event_log(event_id);
        EXCEPTION WHEN duplicate_object THEN
            -- Foreign key already exists
            NULL;
        END $$;
        """

    def _get_event_log_schema_down_sql(self) -> str:
        """Get SQL for event log schema rollback."""
        return """
        DROP TABLE IF EXISTS event_log;
        """

    def _get_wal_schema_sql(self) -> str:
        """Get SQL for WAL schema migration."""
        return """
        -- Create wal table
        CREATE TABLE IF NOT EXISTS wal (
            entry_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            operation TEXT NOT NULL,
            data TEXT NOT NULL,
            data_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_wal_timestamp ON wal(timestamp);
        CREATE INDEX IF NOT EXISTS idx_wal_operation ON wal(operation);
        """

    def _get_wal_schema_down_sql(self) -> str:
        """Get SQL for WAL schema rollback."""
        return """
        DROP TABLE IF EXISTS wal;
        """

    def _get_correlation_ids_sql(self) -> str:
        """Get SQL for correlation IDs migration."""
        return """
        -- Update state table to include correlation_id
        ALTER TABLE state ADD COLUMN correlation_id TEXT;

        -- Update event_log table to include correlation_id
        ALTER TABLE event_log ADD COLUMN correlation_id TEXT;

        -- Create index for correlation_id in state
        CREATE INDEX IF NOT EXISTS idx_state_correlation_id ON state(correlation_id);

        -- Create index for correlation_id in event_log
        CREATE INDEX IF NOT EXISTS idx_event_log_correlation_id ON event_log(correlation_id);
        """

    def _get_correlation_ids_down_sql(self) -> str:
        """Get SQL for correlation IDs rollback."""
        return """
        -- Drop correlation_id indexes
        DROP INDEX IF EXISTS idx_state_correlation_id;
        DROP INDEX IF EXISTS idx_event_log_correlation_id;

        -- Remove correlation_id columns
        ALTER TABLE state DROP COLUMN correlation_id;
        ALTER TABLE event_log DROP COLUMN correlation_id;
        """

    def _get_rate_limiting_sql(self) -> str:
        """Get SQL for rate limiting migration."""
        return """
        -- Create rate_limits table
        CREATE TABLE IF NOT EXISTS rate_limits (
            id TEXT PRIMARY KEY,
            component TEXT NOT NULL,
            count INTEGER NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_rate_limits_component ON rate_limits(component);
        CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_start, window_end);

        -- Create cleanup trigger for old rate limit entries
        CREATE TRIGGER IF NOT EXISTS cleanup_rate_limits
        AFTER INSERT ON rate_limits
        WHEN (SELECT COUNT(*) FROM rate_limits) > 10000
        BEGIN
            DELETE FROM rate_limits
            WHERE id IN (
                SELECT id FROM rate_limits
                ORDER BY created_at ASC
                LIMIT 1000
            );
        END;
        """

    def _get_rate_limiting_down_sql(self) -> str:
        """Get SQL for rate limiting rollback."""
        return """
        DROP TRIGGER IF EXISTS cleanup_rate_limits;
        DROP TABLE IF EXISTS rate_limits;
        """

    def get_all_migrations(self) -> List[Migration]:
        """Get all migrations."""
        return sorted(self.migrations.values(), key=lambda m: m.version)

    def get_applied_migrations(self, conn) -> List[str]:
        """Get list of applied migration versions."""
        try:
            cursor = conn.execute("SELECT version FROM metadata WHERE key = 'schema_version'")
            row = cursor.fetchone()
            if row:
                return row['version'].split(',')
            return []
        except Exception:
            return []

    def migrate(self, conn, target_version: Optional[str] = None):
        """
        Apply migrations up to the target version.

        Args:
            conn: Database connection
            target_version: Target version (defaults to latest)
        """
        all_migrations = self.get_all_migrations()
        applied_migrations = self.get_applied_migrations(conn)

        for migration in all_migrations:
            if target_version and migration.get_version() > target_version:
                break
            if migration.get_version() not in applied_migrations:
                try:
                    migration.execute_up(conn)
                    # Update metadata
                    cursor = conn.execute(
                        "UPDATE metadata SET version = version || ',' || ?, updated_at = ? WHERE key = 'schema_version'",
                        (migration.get_version(), datetime.now(timezone.utc).isoformat())
                    )
                except Exception as e:
                    logger.error(f"Error executing migration {migration.get_version()}: {e}")
                    raise

    def get_status(self, conn) -> str:
        """Get database migration status."""
        try:
            cursor = conn.execute("SELECT version FROM metadata WHERE key = 'schema_version'")
            row = cursor.fetchone()
            if row:
                return row['version']
            return "No migrations applied"
        except Exception:
            return "Error getting migration status"
class ConnectionPool:
    """
    Generic connection pool implementation.

    Manages a pool of connections for database and other resources.
    """

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._connections: List[Any] = []
        self._lock = threading.Lock()

    def get_connection(self):
        """Get a connection from the pool."""
        with self._lock:
            if not self._connections:
                raise Exception("No available connections")
            return self._connections.pop()

    def release_connection(self, conn):
        """Release a connection back to the pool."""
        with self._lock:
            if len(self._connections) < self.max_size:
                self._connections.append(conn)

    def close_all(self):
        """Close all connections."""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except OSError as e:
                    logger.warning(f"Failed to close connection: {e}")
            self._connections.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()
class TheTeamDatabase:
    """
    TheTeam database implementation.

    Provides database operations with connection pooling, migrations, and
    transaction support for theteam application.
    """

    def __init__(self, db_path: str = "theteam.db", use_sqlite: bool = True):
        self.db_path = db_path
        self.use_sqlite = use_sqlite
        self._conn = None

    def connect(self):
        """Connect to the database."""
        if self.use_sqlite:
            import sqlite3
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        else:
            import psycopg2
            self._conn = psycopg2.connect(
                host=self.db_path,
                user="postgres",
                password="postgres",
                database="postgres"
            )

    def close(self):
        """Close the database connection."""
        if self._conn:
            try:
                self._conn.close()
            except OSError as e:
                logger.warning(f"Failed to close database connection: {e}")
            self._conn = None

    def execute(self, sql: str, params: Tuple = ()):
        """Execute SQL statement."""
        try:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"Error executing SQL: {e}")
            self._conn.rollback()
            raise

    def fetch_one(self, sql: str, params: Tuple = ()):
        """Fetch single row."""
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetch_all(self, sql: str, params: Tuple = ()):
        """Fetch all rows."""
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
class DatabaseManager:
    """
    Database manager for theteam.

    Provides database operations with connection pooling, migrations, and
    transaction support. Wraps database operations with error handling
    and transaction management.
    """

    def __init__(self, db_path: str = "theteam.db", use_sqlite: bool = True,
                 pg_config: Optional[PostgresClusterConfig] = None):
        self.db_path = db_path
        self.use_sqlite = use_sqlite
        self._conn = None
        self._migrations = DatabaseMigrations(db_path, use_sqlite)
        # Phase 4: production PostgreSQL support. Lazily constructed so SQLite
        # callers (including `state_manager`) pay nothing.
        self.pg_config = pg_config
        self._failover: Optional["FailoverManager"] = None
        self._replicas: Optional["ReadReplicaRouter"] = None
        self._pool: Optional["PostgresConnectionPool"] = None

    def _cluster_config(self) -> "PostgresClusterConfig":
        """Explicit config if supplied, else the environment's."""
        from theteam.core.postgres_cluster import PostgresClusterConfig
        return self.pg_config or PostgresClusterConfig.from_env()

    @property
    def connection_pool(self) -> "PostgresConnectionPool":
        """Lazily built psycopg2 pool for the primary. SQLite users never touch this."""
        from theteam.core.postgres_cluster import ConnectionPool as PostgresConnectionPool
        if self._pool is None:
            self._pool = PostgresConnectionPool(self._cluster_config())
        return self._pool

    @property
    def failover_manager(self) -> "FailoverManager":
        """Failover manager bound to the configured cluster."""
        from theteam.core.postgres_cluster import FailoverManager
        if self._failover is None:
            self._failover = FailoverManager(self._cluster_config())
        return self._failover

    @property
    def replica_router(self) -> "ReadReplicaRouter":
        """Read router sharing the same failover state as the manager."""
        from theteam.core.postgres_cluster import ReadReplicaRouter
        if self._replicas is None:
            self._replicas = ReadReplicaRouter(self._cluster_config(), self.failover_manager)
        return self._replicas
    def execute_on_replica(self, sql: str, params: Tuple = ()) -> Optional[Any]:
        """
        Run a read query against a replica, falling back to the primary.

        Returns None when no connection can be established, so a replica
        outage degrades rather than breaks the caller.
        """
        try:
            import psycopg2
        except ImportError:
            logger.warning("psycopg2 not installed; replica read unavailable")
            return None

        dsn = self.replica_router.read_conn()
        conn = None
        try:
            conn = psycopg2.connect(**dsn)
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Replica read failed on {dsn.get('host')}: {e}")
            return None
        finally:
            if conn is not None:
                conn.close()

    def get_failover_status(self) -> Dict[str, Any]:
        """Report cluster topology and liveness for health endpoints."""
        return self.failover_manager.status()

    def ensure_primary(self) -> bool:
        """
        Promote the standby if the current primary has gone away.

        Called from the health path so recovery is automatic rather than
        requiring an operator to notice. Returns True if a promotion happened.
        """
        manager = self.failover_manager
        if manager.is_host_alive(manager.current_primary()):
            return False
        try:
            promoted = manager.failover()
        except FailoverError as e:
            logger.error(f"Failover not possible: {e}")
            return False
        logger.warning(f"Promoted {promoted} to primary")
        return True

    def check_replicas(self) -> Dict[str, bool]:
        """
        Re-probe every replica and return those that have recovered.

        Without this, a replica excluded during an outage stays excluded for
        the life of the process even after it comes back.
        """
        router = self.replica_router
        recovered: Dict[str, bool] = {}
        for host in self._cluster_config().replica_hosts:
            alive = self.failover_manager.is_host_alive(host)
            recovered[host] = alive
            if alive:
                router.mark_healthy(host)
            else:
                router.unhealthy_replicas.add(host)
        return recovered

    def connect(self):
        """
        Connect to the database.

        PostgreSQL connections come from the configured cluster pool, so the
        primary host, credentials and pool bounds all come from
        `PostgresClusterConfig` instead of being hardcoded.
        """
        if self.use_sqlite:
            import sqlite3
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        else:
            # Recover automatically if the configured primary is down.
            self.ensure_primary()
            self._conn = self.connection_pool.getconn()

    def close(self):
        """Close the database connection, returning it to the pool if pooled."""
        if self._conn:
            try:
                if self.use_sqlite:
                    self._conn.close()
                else:
                    self.connection_pool.putconn(self._conn)
            except Exception as e:
                logger.warning(f"Failed to close database connection: {e}")
            self._conn = None

    def close_pool(self):
        """Close the whole connection pool. Safe to call when never opened."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None

    def execute(self, sql: str, params: Tuple = ()):
        """Execute SQL statement."""
        try:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"Error executing SQL: {e}")
            self._conn.rollback()
            raise

    def fetch_one(self, sql: str, params: Tuple = ()):
        """Fetch single row."""
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetch_all(self, sql: str, params: Tuple = ()):
        """Fetch all rows."""
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def run_migrations(self):
        """Run database migrations."""
        try:
            self._migrations.migrate(self._conn)
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            raise

    def get_status(self):
        """Get database status."""
        return self._migrations.get_status(self._conn)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
class DatabaseHelper:
    """
    Database helper for theteam.

    Provides database operations with connection pooling, migrations, and
    transaction support. Wraps database operations with error handling
    and transaction management.
    """

    def __init__(self, db_path: str = "theteam.db", use_sqlite: bool = True):
        self.db_path = db_path
        self.use_sqlite = use_sqlite
        self.db_manager = DatabaseManager(db_path, use_sqlite)

    def connect(self):
        """Connect to the database."""
        self.db_manager.connect()

    def close(self):
        """Close the database connection."""
        self.db_manager.close()

    def execute(self, sql: str, params: Tuple = ()):
        """Execute SQL statement."""
        return self.db_manager.execute(sql, params)

    def fetch_one(self, sql: str, params: Tuple = ()):
        """Fetch single row."""
        return self.db_manager.fetch_one(sql, params)

    def fetch_all(self, sql: str, params: Tuple = ()):
        """Fetch all rows."""
        return self.db_manager.fetch_all(sql, params)

    def run_migrations(self):
        """Run database migrations."""
        self.db_manager.run_migrations()

    def get_status(self):
        """Get database status."""
        return self.db_manager.get_status()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()