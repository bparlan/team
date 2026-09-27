#!/usr/bin/env python3
"""
Process entry point: `python -m theteam`.

Serves the metrics/health endpoints that the container healthcheck and
Prometheus scrape. Without arguments it runs the production observability
server; the interactive UI and task-stack entry points remain in
`theteam.__init__.main`.
"""

import logging
import os
import sys

logging.basicConfig(
    level=os.environ.get("THETEAM_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

def _metrics_port() -> int:
    """Resolve the metrics listen port from the environment."""
    try:
        return int(os.environ.get("THETEAM_METRICS_PORT", "8000"))
    except ValueError:
        logger.warning("Invalid THETEAM_METRICS_PORT, defaulting to 8000")
        return 8000

def main(argv=None) -> int:
    """Run the observability server until interrupted."""
    from theteam.core.metrics import MetricsCollector
    from theteam.core.unified_loop import UnifiedLoop, LoopConfig

    argv = list(sys.argv[1:] if argv is None else argv)
    project_root = os.environ.get("THETEAM_PROJECT_ROOT", os.getcwd())

    loop = UnifiedLoop(
        project_root,
        LoopConfig(loop_id="theteam", project_root=project_root),
    )
    loop.start()

    collector = MetricsCollector(port=_metrics_port())
    collector.bind(loop=loop, limiter=loop.resource_limiter)
    if not collector.start_http_server():
        logger.error("Metrics endpoint failed to start; exiting so the healthcheck restarts us")
        loop.stop()
        return 1

    logger.info("theteam running; serving /metrics and /health")
    try:
        while True:
            # The loop runs its own scheduler thread; this thread just blocks.
            threading_wait()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        collector.stop()
        loop.stop()
    return 0


def threading_wait() -> None:
    """Block the main thread, waking periodically so signals land promptly."""
    import threading

    threading.Event().wait(3600)


if __name__ == "__main__":
    sys.exit(main())
