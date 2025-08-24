#!/bin/bash

# Get the absolute path of current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.bot.pid"
LOG_DIR="$SCRIPT_DIR/logs"

echo "Claude Proxy Status"
echo "==================="

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    
    # Check if the process exists
    if ps -p "$PID" > /dev/null 2>&1; then
        # Verify it's actually our python process
        PROCESS_CMD=$(ps -p "$PID" -o command= 2>/dev/null || echo "")
        PROCESS_CWD=$(lsof -p "$PID" -a -d cwd -Fn 2>/dev/null | grep '^n' | cut -c2- || echo "")
        
        if [[ "$PROCESS_CMD" == *"python"*"main.py"* ]] && [[ "$PROCESS_CWD" == "$SCRIPT_DIR" ]]; then
            echo "Status: RUNNING"
            echo "PID: $PID"
            
            # Show process info
            echo ""
            echo "Process info:"
            ps -p "$PID" -o pid,vsz,rss,pcpu,pmem,etime,command
            
            # Show latest log file
            if [ -d "$LOG_DIR" ]; then
                LATEST_LOG=$(ls -t "$LOG_DIR"/bot_*.log 2>/dev/null | head -1)
                if [ -n "$LATEST_LOG" ]; then
                    echo ""
                    echo "Latest log file: $LATEST_LOG"
                    echo "Last 10 lines:"
                    echo "---"
                    tail -n 10 "$LATEST_LOG"
                fi
            fi
        else
            echo "Status: STOPPED (stale PID file)"
            echo "PID file exists but process is not our bot"
        fi
    else
        echo "Status: STOPPED (stale PID file)"
        echo "Bot is not running"
    fi
else
    echo "Status: STOPPED"
    echo "Bot is not running (no PID file)"
fi