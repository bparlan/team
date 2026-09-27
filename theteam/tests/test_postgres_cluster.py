#!/usr/bin/env python3
"""Regression tests for theteam/core/postgres_cluster.py.

Pure-logic only: no psycopg2, no network, no Docker, no sleeps. TCP liveness
is probed through a monkeypatched `socket.create_connection`, so the failover
state machine and the read router are exercised deterministically.
"""

import logging
import os
import sys

import pytest


from theteam.core import postgres_cluster as pg
from theteam.core.postgres_cluster import (
    FailoverError,
    FailoverManager,
    PostgresClusterConfig,
    ReadReplicaRouter,
)


class _NullConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSocket:
    """Records connect attempts; liveness is decided by a fixed host set."""

    def __init__(self, alive=()):
        self.alive = set(alive)
        self.attempts = []

    def create_connection(self, address, timeout=None):
        host, port = address
        self.attempts.append((host, port, timeout))
        if host not in self.alive:
            raise OSError(f"connection refused: {host}")
        return _NullConn()


@pytest.fixture
def fake_socket(monkeypatch):
    """Install a fake TCP layer. `socket` is the stdlib module object, so
    monkeypatch restores it automatically - no cross-test leakage."""
    fake = FakeSocket()
    monkeypatch.setattr(pg.socket, "create_connection", fake.create_connection)
    return fake


# ---------------------------------------------------------------------------
# PostgresClusterConfig.from_env -- PG_* variable mapping
# ---------------------------------------------------------------------------


def test_from_env_maps_pg_variables_to_config():
    """Every PG_* connection variable lands on the matching config field."""
    config = PostgresClusterConfig.from_env(
        {
            "PG_HOST": "pg-internal",
            "PG_STANDBY_HOST": "pg-standby",
            "PG_REPLICA_HOSTS": "r1, r2 ,r3",
            "PG_PORT": "6543",
            "PG_DATABASE": "appdb",
            "PG_USER": "appuser",
            "PG_PASSWORD": "s3cret",
            "PG_POOL_MIN": "2",
            "PG_POOL_MAX": "20",
            "PG_CONNECT_TIMEOUT": "5",
        }
    )

    assert config.primary_host == "pg-internal"
    assert config.standby_host == "pg-standby"
    assert config.replica_hosts == ["r1", "r2", "r3"]
    assert config.port == 6543
    assert config.database == "appdb"
    assert config.user == "appuser"
    assert config.password == "s3cret"
    assert (config.pool_min, config.pool_max) == (2, 20)
    assert config.connect_timeout == 5


def test_from_env_prefers_primary_host_over_host_alias():
    """PG_PRIMARY_HOST is the explicit primary and beats the PG_HOST alias."""
    config = PostgresClusterConfig.from_env(
        {"PG_HOST": "generic", "PG_PRIMARY_HOST": "explicit-primary"}
    )
    assert config.primary_host == "explicit-primary"


def test_from_env_dsn_uses_configured_endpoint():
    """primary_dsn() emits psycopg2 kwargs pointing at the writable primary."""
    config = PostgresClusterConfig.from_env(
        {
            "PG_HOST": "pg-internal",
            "PG_PORT": "6543",
            "PG_DATABASE": "appdb",
            "PG_USER": "appuser",
            "PG_PASSWORD": "s3cret",
            "PG_CONNECT_TIMEOUT": "5",
        }
    )

    assert config.primary_dsn() == {
        "host": "pg-internal",
        "port": 6543,
        "dbname": "appdb",
        "user": "appuser",
        "password": "s3cret",
        "connect_timeout": 5,
    }


def test_to_dict_never_leaks_the_password():
    """Status payloads carry the topology but never the secret."""
    config = PostgresClusterConfig.from_env(
        {"PG_HOST": "pg-internal", "PG_PASSWORD": "super-secret"}
    )

    serialized = config.to_dict()

    assert "super-secret" not in repr(serialized)
    assert "password" not in serialized
    assert serialized["primary_host"] == "pg-internal"


# ---------------------------------------------------------------------------
# DATABASE_URL authority
# ---------------------------------------------------------------------------


def test_database_url_overrides_pg_variables():
    """DATABASE_URL is authoritative for the whole connection identity."""
    config = PostgresClusterConfig.from_env(
        {
            "PG_HOST": "pg-internal",
            "PG_PORT": "5432",
            "PG_USER": "pguser",
            "PG_PASSWORD": "pgpass",
            "PG_DATABASE": "pgdb",
            "DATABASE_URL": "postgresql://urluser:urlpass@db.internal:6543/appdb",
        }
    )

    assert config.primary_host == "db.internal"
    assert config.port == 6543
    assert config.user == "urluser"
    assert config.password == "urlpass"
    assert config.database == "appdb"


def test_database_url_percent_decodes_password():
    """A password holding URL metacharacters must reach the server literally.

    urlparse does not decode userinfo, so `p%40ss%3Aword%2Fx` would otherwise be
    sent verbatim and every connection would fail authentication.
    """
    config = PostgresClusterConfig.from_env(
        {"DATABASE_URL": "postgresql://svc:p%40ss%3Aword%2Fx%23q%3Fr@db.internal/appdb"}
    )

    assert config.password == "p@ss:word/x#q?r"
    assert config.primary_dsn()["password"] == "p@ss:word/x#q?r"


def test_database_url_percent_decodes_username_and_database():
    """Percent-escapes in the user and database segments are decoded too."""
    config = PostgresClusterConfig.from_env(
        {"DATABASE_URL": "postgresql://app%2Duser:pw@db.internal:5432/app%2Ddb"}
    )

    assert config.user == "app-user"
    assert config.database == "app-db"


def test_database_url_without_password_keeps_pg_password():
    """A URL with no userinfo password must not blank the configured secret."""
    config = PostgresClusterConfig.from_env(
        {
            "PG_PASSWORD": "pgpass",
            "DATABASE_URL": "postgresql://svc@db.internal:6543/appdb",
        }
    )

    assert config.password == "pgpass"


def test_malformed_database_url_port_falls_back_to_pg_settings(caplog):
    """A non-numeric port degrades to PG_* settings; startup must not crash."""
    env = {
        "PG_HOST": "pg-internal",
        "PG_PORT": "5433",
        "PG_USER": "pguser",
        "PG_PASSWORD": "pgpass",
        "PG_DATABASE": "pgdb",
        "DATABASE_URL": "postgresql://urluser:urlpass@db.internal:notaport/appdb",
    }

    with caplog.at_level(logging.WARNING, logger=pg.__name__):
        config = PostgresClusterConfig.from_env(env)

    assert "malformed DATABASE_URL" in caplog.text
    assert config.port == 5433
    # The URL is rejected as a unit: no half-applied credentials leak through.
    assert config.primary_host == "pg-internal"
    assert config.user == "pguser"
    assert config.password == "pgpass"
    assert config.database == "pgdb"


def test_unparseable_database_url_keeps_pg_settings():
    """A URL without a usable authority is ignored entirely."""
    config = PostgresClusterConfig.from_env(
        {
            "PG_HOST": "pg-internal",
            "PG_PASSWORD": "pgpass",
            "DATABASE_URL": "not-a-url-at-all",
        }
    )

    assert config.primary_host == "pg-internal"
    assert config.password == "pgpass"


# ---------------------------------------------------------------------------
# ReadReplicaRouter
# ---------------------------------------------------------------------------


def test_router_round_robins_across_healthy_replicas(fake_socket):
    """Reads rotate over every healthy replica instead of pinning the first."""
    fake_socket.alive.update({"r1", "r2", "r3"})
    config = PostgresClusterConfig(
        primary_host="primary1", replica_hosts=["r1", "r2", "r3"]
    )
    router = ReadReplicaRouter(config, FailoverManager(config))

    first_three = [router.read_conn()["host"] for _ in range(3)]

    assert sorted(first_three) == ["r1", "r2", "r3"]


@pytest.mark.parametrize("replicas_up", [[], ["r1"]])
def test_router_never_reads_from_the_standby(fake_socket, replicas_up):
    """The standby is not serving reads until promoted, so it must never be a
    read target - not even when every replica is down and the standby is the
    only reachable node besides the primary."""
    fake_socket.alive.update({"primary1", "standby1", *replicas_up})
    config = PostgresClusterConfig(
        primary_host="primary1", standby_host="standby1", replica_hosts=["r1", "r2"]
    )
    router = ReadReplicaRouter(config, FailoverManager(config))

    targets = [router.read_conn()["host"] for _ in range(5)]

    assert "standby1" not in targets
    assert set(targets) <= {"r1", "primary1"}


def test_router_falls_back_to_primary_when_all_replicas_are_down(fake_socket):
    """An outage on the replica side must not stop reads."""
    fake_socket.alive.add("primary1")
    config = PostgresClusterConfig(primary_host="primary1", replica_hosts=["r1", "r2"])
    router = ReadReplicaRouter(config, FailoverManager(config))

    conn = router.read_conn()

    assert conn["host"] == "primary1"
    assert conn["dbname"] == config.database
    assert router.healthy_replicas() == []


def test_router_skips_dead_replica_and_marks_it_unhealthy(fake_socket):
    """A failing TCP check removes that replica from the read pool."""
    fake_socket.alive.update({"primary1", "r2"})
    config = PostgresClusterConfig(primary_host="primary1", replica_hosts=["r1", "r2"])
    router = ReadReplicaRouter(config, FailoverManager(config))

    assert router.read_conn()["host"] == "r2"
    assert router.unhealthy_replicas == {"r1"}
    assert router.healthy_replicas() == ["r2"]


def test_mark_healthy_returns_a_recovered_replica_to_the_pool(fake_socket):
    """Recovery is what makes a previously dead replica eligible again."""
    fake_socket.alive.update({"primary1", "r1", "r2"})
    config = PostgresClusterConfig(primary_host="primary1", replica_hosts=["r1", "r2"])
    router = ReadReplicaRouter(config, FailoverManager(config))
    router.unhealthy_replicas.add("r2")

    router.mark_healthy("r2")

    assert router.healthy_replicas() == ["r1", "r2"]


def test_router_follows_the_promoted_primary_after_failover(fake_socket):
    """After promotion the read fallback targets the new primary, not the
    demoted one."""
    fake_socket.alive.add("standby1")
    config = PostgresClusterConfig(
        primary_host="primary1", standby_host="standby1", replica_hosts=["r1"]
    )
    failover = FailoverManager(config)
    failover.failover()
    router = ReadReplicaRouter(config, failover)

    assert router.read_conn()["host"] == "standby1"


# ---------------------------------------------------------------------------
# FailoverManager
# ---------------------------------------------------------------------------


def test_is_host_alive_uses_the_configured_port_and_timeout(fake_socket):
    """Liveness is a TCP connect against the cluster endpoint."""
    fake_socket.alive.add("primary1")
    config = PostgresClusterConfig(primary_host="primary1", port=6543, connect_timeout=5)
    manager = FailoverManager(config)

    assert manager.is_host_alive("primary1") is True
    assert fake_socket.attempts == [("primary1", 6543, 5)]


def test_is_host_alive_is_false_for_down_and_unset_hosts(fake_socket):
    """A refused connect and a missing host both read as 'not alive'."""
    fake_socket.alive.add("primary1")
    config = PostgresClusterConfig(primary_host="primary1")
    manager = FailoverManager(config)

    assert manager.is_host_alive("dead-host") is False
    assert manager.is_host_alive(None) is False


def test_failover_promotes_standby_when_primary_is_unreachable(fake_socket):
    """A dead primary promotes the standby and makes it the write target."""
    fake_socket.alive.add("standby1")
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")
    manager = FailoverManager(config)

    promoted = manager.failover()

    assert promoted == "standby1"
    assert manager.current_primary() == "standby1"
    assert manager.status()["failovers"] == 1


def test_failover_counter_only_counts_real_promotions(fake_socket):
    """A refused promotion and a re-promotion behave correctly on a flap."""
    fake_socket.alive.add("standby1")
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")
    manager = FailoverManager(config)

    assert manager.failover() == "standby1"
    assert manager.status()["failovers"] == 1

    # The promoted node is back and healthy: no second failover.
    fake_socket.alive.clear()
    fake_socket.alive.add("standby1")
    with pytest.raises(FailoverError, match="still alive"):
        manager.failover()
    assert manager.status()["failovers"] == 1
    assert manager.current_primary() == "standby1"

    # The promoted node then dies with no standby left: no third promotion.
    fake_socket.alive.clear()
    with pytest.raises(FailoverError, match="unreachable"):
        manager.failover()
    assert manager.status()["failovers"] == 1


def test_failover_refuses_while_the_primary_is_healthy(fake_socket):
    """A healthy primary must never be demoted - no gratuitous split brain."""
    fake_socket.alive.update({"primary1", "standby1"})
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")
    manager = FailoverManager(config)

    with pytest.raises(FailoverError, match="still alive"):
        manager.failover()

    assert manager.current_primary() == "primary1"
    assert manager.status()["failovers"] == 0


def test_failover_raises_when_no_writable_node_remains(fake_socket):
    """Primary and standby both down means no write target exists."""
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")
    manager = FailoverManager(config)

    with pytest.raises(FailoverError, match="unreachable"):
        manager.failover()

    assert manager.current_primary() == "primary1"


def test_failover_raises_when_no_standby_is_configured(fake_socket):
    """Without a standby there is nothing to promote."""
    fake_socket.alive.clear()
    config = PostgresClusterConfig(primary_host="primary1")
    manager = FailoverManager(config)

    with pytest.raises(FailoverError, match="unreachable"):
        manager.failover()


def test_status_reports_topology_and_per_host_liveness(fake_socket):
    """status() is the health payload: one boolean per configured node."""
    fake_socket.alive.update({"primary1", "standby1", "r1"})
    config = PostgresClusterConfig(
        primary_host="primary1",
        standby_host="standby1",
        replica_hosts=["r1", "r2"],
    )
    manager = FailoverManager(config)

    status = manager.status()

    assert status["primary"] == "primary1"
    assert status["standby"] == "standby1"
    assert status["replicas"] == ["r1", "r2"]
    assert status["primary_alive"] is True
    assert status["standby_alive"] is True
    assert status["replica_alive"] == {"r1": True, "r2": False}
    assert status["last_error"] is None


def test_status_records_the_promotion_cause(fake_socket):
    """`last_error` names the promoted and failed nodes for operator triage."""
    fake_socket.alive.add("standby1")
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")
    manager = FailoverManager(config)

    manager.failover()

    assert "standby1" in manager.status()["last_error"]
    assert "primary1" in manager.status()["last_error"]

def test_failover_actually_promotes_the_standby(fake_socket):
    """Repointing `primary` at a standby is NOT promotion.

    A standby that has not been promoted stays read-only, so a failover that
    only reassigns the hostname yields a "primary" that rejects every write.
    The promotion callback must be invoked with the new primary, and it must
    run BEFORE the host is recorded.
    """
    fake_socket.alive.add("standby1")
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")

    promoted = []
    manager = FailoverManager(config, promote=promoted.append)

    assert manager.failover() == "standby1"
    assert promoted == ["standby1"], "failover() never promoted the standby"


def test_promotion_happens_before_the_primary_is_reassigned(fake_socket):
    """Ordering matters: a promotion that runs afterwards is a split brain.

    If the host is recorded first, a promotion failure or a concurrent read
    would already see the standby as the write target while it is still
    read-only. The recorder captures which is which.
    """
    fake_socket.alive.add("standby1")
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")

    events = []

    def promote(host):
        # At promotion time the manager must still consider the old primary.
        events.append(("promote", host, manager.current_primary()))

    manager = FailoverManager(config, promote=promote)
    manager.failover()

    assert events == [("promote", "standby1", "primary1")]
    assert manager.current_primary() == "standby1"


def test_failover_without_a_promote_callback_still_records_the_host(fake_socket):
    """No callback configured: the host is recorded, for liveness-only use."""
    fake_socket.alive.add("standby1")
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")
    manager = FailoverManager(config)

    assert manager.failover() == "standby1"
    assert manager.current_primary() == "standby1"


def test_no_promotion_is_attempted_when_the_primary_is_healthy(fake_socket):
    """A healthy primary must not trigger promotion of anyone."""
    fake_socket.alive.update({"primary1", "standby1"})
    config = PostgresClusterConfig(primary_host="primary1", standby_host="standby1")

    promoted = []
    manager = FailoverManager(config, promote=promoted.append)

    with pytest.raises(FailoverError):
        manager.failover()
    assert promoted == []
