#!/bin/bash
# Task Stack Daemon - Cron-like wrapper
# Runs the task stack daemon in the background

PROJECT_ROOT="/Users/bparlan/devcode/team"
DAEMON="$PROJECT_ROOT/theteam/subskills/task_stack/daemon.py"
PID_FILE="$PROJECT_ROOT/.mp/theteam/task-stack.pid"

case "$1" in
    start)
        echo "Starting Task Stack Daemon..."
        cd "$PROJECT_ROOT"
        python3 "$DAEMON" start
        ;;
    stop)
        echo "Stopping Task Stack Daemon..."
        python3 "$DAEMON" stop
        ;;
    status)
        python3 "$DAEMON" status
        ;;
    restart)
        python3 "$DAEMON" stop
        sleep 1
        python3 "$DAEMON" start
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac

exit 0