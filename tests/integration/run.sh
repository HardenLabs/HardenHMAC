#!/bin/bash
# Cross-language HMAC integration test orchestrator
# Starts all servers, runs all clients, reports results
#
# Usage: bash run.sh
#
# Prerequisites:
#   - .NET 8 SDK (for C# server/client)
#   - Python 3.10+ with pip (for Python server/client)
#   - Node.js 18+ with npm (for TypeScript server/client)
#   - Go 1.21+ (optional, for Go server/client)

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()
ALL_RESULTS=""
FAIL_COUNT=0
PASS_COUNT=0
SKIP_COUNT=0

cleanup() {
    echo ""
    echo "=== Cleaning up ==="
    if [ ${#PIDS[@]} -gt 0 ]; then
        for pid in "${PIDS[@]}"; do
            kill "$pid" 2>/dev/null || true
        done
    fi
    wait 2>/dev/null || true
}
trap cleanup EXIT

# Wait for a TCP port to become available
wait_for_port() {
    local port=$1
    local name=$2
    local max_wait=$3
    local elapsed=0

    while ! nc -z localhost "$port" 2>/dev/null; do
        if [ "$elapsed" -ge "$max_wait" ]; then
            echo "ERROR: $name did not start within ${max_wait}s on port $port"
            return 1
        fi
        sleep 0.5
        elapsed=$((elapsed + 1))
    done
    echo "  $name ready on port $port (${elapsed}s)"
    return 0
}

# Check which languages are available
has_dotnet=false
has_python=false
has_node=false
has_go=false

if command -v dotnet &>/dev/null; then
    has_dotnet=true
    echo "[OK] dotnet found: $(dotnet --version)"
else
    echo "[SKIP] dotnet not found"
fi

if command -v python3 &>/dev/null; then
    has_python=true
    echo "[OK] python3 found: $(python3 --version 2>&1)"
else
    echo "[SKIP] python3 not found"
fi

if command -v node &>/dev/null; then
    has_node=true
    echo "[OK] node found: $(node --version)"
else
    echo "[SKIP] node not found"
fi

if command -v go &>/dev/null; then
    has_go=true
    echo "[OK] go found: $(go version)"
else
    echo "[SKIP] go not found (Go tests will be skipped)"
fi

echo ""

# ============================================================
# Kill any leftover processes on test ports
# ============================================================
for port_name in csharp python typescript go; do
    port_num=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/config.json'))['ports'].get('$port_name', ''))" 2>/dev/null || true)
    if [ -n "$port_num" ]; then
        existing=$(lsof -ti:"$port_num" 2>/dev/null || true)
        if [ -n "$existing" ]; then
            echo "Killing existing process on port $port_num..."
            echo "$existing" | xargs kill -9 2>/dev/null || true
        fi
    fi
done
sleep 1

# ============================================================
# Build phase (before starting servers, to avoid slow startups)
# ============================================================
echo "=== Build phase ==="

if $has_dotnet; then
    echo "  Building C# server..."
    dotnet build "$SCRIPT_DIR/servers/csharp/Server.csproj" -c Release --nologo -v q 2>&1 | tail -1
    echo "  Building C# client..."
    dotnet build "$SCRIPT_DIR/clients/csharp/Client.csproj" -c Release --nologo -v q 2>&1 | tail -1
fi

if $has_python; then
    echo "  Checking Python dependencies..."
    python3 -c "import fastapi, uvicorn, httpx" 2>/dev/null || {
        echo "  Installing Python dependencies..."
        pip3 install -q fastapi uvicorn httpx 2>&1 | tail -1
    }
fi

if $has_node; then
    echo "  Building TypeScript SDK..."
    (cd "$SCRIPT_DIR/../../sdk/typescript/packages/hmac" && npm install --silent 2>&1 | tail -1 && npm run build --silent 2>&1 | tail -1)

    echo "  Installing TypeScript server dependencies..."
    (cd "$SCRIPT_DIR/servers/typescript" && npm install --silent 2>&1 | tail -1)

    echo "  Installing TypeScript client dependencies..."
    (cd "$SCRIPT_DIR/clients/typescript" && npm install --silent 2>&1 | tail -1)
fi

if $has_go; then
    echo "  Building Go server..."
    (cd "$SCRIPT_DIR/servers/go" && go build -o /dev/null . 2>&1 | tail -1)
    echo "  Building Go client..."
    (cd "$SCRIPT_DIR/clients/go" && go build -o /dev/null . 2>&1 | tail -1)
fi

echo ""

# ============================================================
# Start servers
# ============================================================
echo "=== Starting servers ==="

if $has_dotnet; then
    echo "  Starting C# server..."
    dotnet run --project "$SCRIPT_DIR/servers/csharp/Server.csproj" -c Release --no-build --nologo \
        > "$SCRIPT_DIR/servers/csharp/server.log" 2>&1 &
    PIDS+=($!)
fi

if $has_python; then
    echo "  Starting Python server..."
    python3 "$SCRIPT_DIR/servers/python/server.py" \
        > "$SCRIPT_DIR/servers/python/server.log" 2>&1 &
    PIDS+=($!)
fi

if $has_node; then
    echo "  Starting TypeScript server..."
    (cd "$SCRIPT_DIR/servers/typescript" && npx tsx server.ts) \
        > "$SCRIPT_DIR/servers/typescript/server.log" 2>&1 &
    PIDS+=($!)
fi

if $has_go; then
    echo "  Starting Go server..."
    (cd "$SCRIPT_DIR/servers/go" && go run .) \
        > "$SCRIPT_DIR/servers/go/server.log" 2>&1 &
    PIDS+=($!)
fi

echo ""
echo "=== Waiting for servers ==="

# Read ports from config.json
CSHARP_PORT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/config.json'))['ports']['csharp'])" 2>/dev/null || echo 9100)
PYTHON_PORT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/config.json'))['ports']['python'])" 2>/dev/null || echo 9101)
TS_PORT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/config.json'))['ports']['typescript'])" 2>/dev/null || echo 9102)
GO_PORT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/config.json'))['ports']['go'])" 2>/dev/null || echo 9103)

SERVER_READY_CSHARP=false
SERVER_READY_PYTHON=false
SERVER_READY_TS=false
SERVER_READY_GO=false

if $has_dotnet; then
    if wait_for_port "$CSHARP_PORT" "C# server" 30; then
        SERVER_READY_CSHARP=true
    fi
fi

if $has_python; then
    if wait_for_port "$PYTHON_PORT" "Python server" 15; then
        SERVER_READY_PYTHON=true
    fi
fi

if $has_node; then
    if wait_for_port "$TS_PORT" "TypeScript server" 15; then
        SERVER_READY_TS=true
    fi
fi

if $has_go; then
    if wait_for_port "$GO_PORT" "Go server" 15; then
        SERVER_READY_GO=true
    fi
fi

echo ""

# ============================================================
# Run clients
# ============================================================
echo "=== Running clients ==="

run_client() {
    local name=$1
    local cmd=$2
    local output

    echo "  Running $name..."
    output=$(eval "$cmd" 2>&1) || true
    echo "$output"
    ALL_RESULTS="$ALL_RESULTS"$'\n'"$output"
}

if $has_dotnet; then
    run_client "C# client" \
        "dotnet run --project '$SCRIPT_DIR/clients/csharp/Client.csproj' -c Release --no-build --nologo"
fi

if $has_python; then
    run_client "Python client" \
        "python3 '$SCRIPT_DIR/clients/python/client.py'"
fi

if $has_node; then
    run_client "TypeScript client" \
        "cd '$SCRIPT_DIR/clients/typescript' && npx tsx client.ts"
fi

if $has_go; then
    run_client "Go client" \
        "cd '$SCRIPT_DIR/clients/go' && go run ."
fi

echo ""

# ============================================================
# Results summary
# ============================================================
echo "=== Results Matrix ==="
echo ""

PASS_COUNT=$(echo "$ALL_RESULTS" | grep -c "^PASS" || true)
FAIL_COUNT=$(echo "$ALL_RESULTS" | grep -c "^FAIL" || true)
SKIP_COUNT=$(echo "$ALL_RESULTS" | grep -c "^SKIP" || true)
TOTAL=$((PASS_COUNT + FAIL_COUNT))

# Print header
printf "%-20s | %-15s | %-15s | %-15s | %-15s\n" "" "csharp-server" "python-server" "ts-server" "go-server"
printf "%-20s-+-%-15s-+-%-15s-+-%-15s-+-%-15s\n" "--------------------" "---------------" "---------------" "---------------" "---------------"

for client in "csharp-client" "python-client/httpx" "python-client/requests" "typescript-client/fetch" "typescript-client/axios" "go-client"; do
    row=""
    for server in "csharp-server" "python-server" "typescript-server" "go-server"; do
        get_result=$(echo "$ALL_RESULTS" | grep "$client -> $server GET" | head -1)
        post_result=$(echo "$ALL_RESULTS" | grep "$client -> $server POST" | head -1)

        get_status="--"
        post_status="--"

        if echo "$get_result" | grep -q "^PASS"; then
            get_status="OK"
        elif echo "$get_result" | grep -q "^FAIL"; then
            get_status="FAIL"
        fi

        if echo "$post_result" | grep -q "^PASS"; then
            post_status="OK"
        elif echo "$post_result" | grep -q "^FAIL"; then
            post_status="FAIL"
        fi

        cell="${get_status}/${post_status}"
        row="$row$(printf " | %-15s" "$cell")"
    done
    printf "%-20s%s\n" "$client" "$row"
done

echo ""
echo "--- Granular validation (per-endpoint opt-in) ---"
echo ""
printf "%-20s | %-15s | %-15s | %-15s | %-15s\n" "" "csharp-server" "python-server" "ts-server" "go-server"
printf "%-20s-+-%-15s-+-%-15s-+-%-15s-+-%-15s\n" "--------------------" "---------------" "---------------" "---------------" "---------------"

for client in "csharp-client" "python-client" "typescript-client" "go-client"; do
    row=""
    for server in "csharp-server" "python-server" "typescript-server" "go-server"; do
        health_result=$(echo "$ALL_RESULTS" | grep "$client -> $server GET /health" | head -1)
        nohmac_result=$(echo "$ALL_RESULTS" | grep "$client/nohmac -> $server GET" | head -1)

        health_status="--"
        nohmac_status="--"

        if echo "$health_result" | grep -q "^PASS"; then
            health_status="OK"
        elif echo "$health_result" | grep -q "^FAIL"; then
            health_status="FAIL"
        fi

        if echo "$nohmac_result" | grep -q "^PASS"; then
            nohmac_status="OK"
        elif echo "$nohmac_result" | grep -q "^FAIL"; then
            nohmac_status="FAIL"
        fi

        cell="${health_status}/${nohmac_status}"
        row="$row$(printf " | %-15s" "$cell")"
    done
    printf "%-20s%s\n" "$client" "$row"
done

echo ""
echo "Legend: GET/POST status per cell (OK = 200, FAIL = error, -- = skipped)"
echo "Granular: health(200)/nohmac(400) per cell"
echo ""
echo "Total: $PASS_COUNT passed, $FAIL_COUNT failed, $SKIP_COUNT skipped out of $TOTAL tests"

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo ""
    echo "FAILURES:"
    echo "$ALL_RESULTS" | grep "^FAIL" || true
    echo ""
    exit 1
fi

if [ "$PASS_COUNT" -eq 0 ]; then
    echo ""
    echo "WARNING: No tests ran. Check that at least one language runtime is installed."
    exit 1
fi

echo ""
echo "All $PASS_COUNT tests passed."
exit 0
