#!/bin/sh
#
# omnsitat-load -- Load data and start Victoria Metrics server
#
# If the DATADIR variable is set, start Victoria Metrics to serve data under
# the /data directory. If the MULTIDIR variable is set, the /data directory
# will be used as a source of several databases that will be merged into
# /data/_merged.
#
# Merging is sequential: it starts a Victoria Metrics instance for each source
# database, exports the data to a file, and then imports it into the target
# database.

if [ -z "$DATADIR" ] && [ -z "$MULTIDIR" ]; then
    echo "Warning: DATADIR is not set, defaulting to ./data"
    DATADIR=./data
fi

VOLUME_DIR=/data

# Name of the merged database when using MULTIDIR.
MERGED_NAME="_merged"

# Target database directories in the container and the host.
TARGET_DIR=$VOLUME_DIR
HOST_DIR=$DATADIR

if [ -n "$MULTIDIR" ]; then
    TARGET_DIR=$VOLUME_DIR/$MERGED_NAME
    HOST_DIR=$MULTIDIR/$MERGED_NAME
fi

# Adress of the main Victoria Metrics server.
TARGET_URL=localhost:9090
TARGET_PORT=$(echo $TARGET_URL | awk -F':' '{print $2}')

# Adress to export Victoria Metrics data from source databases when using
# MULTIDIR.
SOURCE_URL=localhost:8428

# Path to the temporary file used for exporting/importing databases.
DATA_FILE=/tmp/data.bin

# Default Victoria Metrics configuration.
VICTORIA_BIN=/victoria-metrics-prod
VICTORIA_ARGS="-retentionPeriod=3y -loggerLevel=ERROR"

# Checks to ensure services are ready. Timeouts and intervals are seconds.
# Victoria Metrics interval and timeout is also used during database merging,
# not just for setting up the final service.
VICTORIA_URL=http://omnistat:9090/-/healthy
VICTORIA_INTERVAL=1
VICTORIA_TIMEOUT=30
GRAFANA_URL=http://grafana:3000/
GRAFANA_INTERVAL=1
GRAFANA_TIMEOUT=30

# Control how long to wait for Victoria Metrics servers when they're stopped.
VICTORIA_LOCK_INTERVAL=1
VICTORIA_LOCK_TIMEOUT=30

# Wait until a given URL is responsive, checking it at the given interval.
# Returns 0 if the URL responds successfully before the timeout threshold,
# otherwise returns 1.
wait_for_url() {
    local url=$1
    local interval=$2
    local timeout=$3

    local start_time=$(date +%s)
    local current_time
    local elapsed_time

    while true; do
        current_time=$(date +%s)
        elapsed_time=$((current_time - start_time))

        if [ $elapsed_time -gt $timeout ]; then
            echo "Warning: access to $url timed out after $timeout seconds"
            return 1
        fi

        curl -s --fail --head $url > /dev/null
        if [ $? -eq 0 ]; then
            return 0
        fi

        sleep $interval
    done
}

# Ensure Victoria Metrics server is no longer running by checking its lock file
# If the lock cannot be acquired, retry until reaching the timeout threshold.
# Returns 0 when the server is no longer running, otherwise abort the execution
# of the script.
check_victoria_down() {
    local path=$1/flock.lock

    local start_time=$(date +%s)
    local current_time
    local elapsed_time

    while true; do
        current_time=$(date +%s)
        elapsed_time=$((current_time - start_time))

        if [ $elapsed_time -gt $VICTORIA_LOCK_TIMEOUT ]; then
            echo "Error: Victoria Metrics server shutdown timeout"
            exit 1
        fi

        # Subshell to acquire database lock. Returns 0 if lock can be acquired.
        (
            flock -x -n 200 && {
                exit 0
            }
            exit 1
        ) 200>"$path"

        # If subshell exits with 0, confirm server is no longer running.
        if [ $? -eq 0 ]; then
            return 0
        fi

        sleep $VICTORIA_LOCK_INTERVAL
    done
}

# Start a Victoria Metrics server in the background for merging purposes.
# Returns the PID of the process if successful, otherwise returns 0.
start_victoria() {
    local address=$1
    local path=$2

    local pid
    local url

    $VICTORIA_BIN $VICTORIA_ARGS \
        -httpListenAddr=$address \
        -storageDataPath=$path \
        -search.disableCache &
    pid=$!

    url=$address/-/healthy
    wait_for_url $url $VICTORIA_INTERVAL $VICTORIA_TIMEOUT
    if [ $? -ne 0 ]; then
        echo "Unable to reach $address"
        return 0
    fi

    return $pid
}

merge_databases() {
    local target_pid
    local source_pid
    local num_databases
    local db_name

    start_victoria $TARGET_URL $TARGET_DIR
    target_pid=$?
    if [ $target_pid -eq 0 ]; then
        echo "Error: failed to start target Victoria Metrics server"
        exit 1
    fi

    num_databases=0
    for i in $VOLUME_DIR/*; do
        db_name=$(basename $i)

        if [ ! -d $i ] || [ "$db_name" == "$MERGED_NAME" ]; then
            continue
        fi

        if [ ! -f $i/flock.lock ] || [ ! -d $i/data ]; then
            echo "Skip invalid database: $db_name"
            continue
        fi

        if [ -f $TARGET_DIR/.$db_name ]; then
            echo "Skip pre-existing database: $db_name"
            continue
        fi

        echo "Loading $db_name"
        start_victoria $SOURCE_URL $i
        source_pid=$!
        if [ $source_pid -eq 0 ]; then
            echo ".. Warning: Failed to load $i"
            continue
        fi

        echo ".. Exporting data from $db_name"
        curl -s --fail $SOURCE_URL/api/v1/export/native -d 'match[]={__name__!~"vm_.*"}' > $DATA_FILE
        if [ $? -ne 0 ]; then
            echo ".. Warning: Failed to export $db_name"
            continue
        fi

        # Shutdown source Victoria Metrics
        kill -SIGINT $source_pid

        echo ".. Merging data from $db_name to $HOST_DIR"
        curl -s --fail -X POST $TARGET_URL/api/v1/import/native -T $DATA_FILE
        if [ $? -ne 0 ]; then
            echo ".. Warning: Failed to import $i"
            continue
        fi

        rm -f $DATA_FILE
        touch $TARGET_DIR/.$db_name
        num_databases=$(($num_databases + 1))

        check_victoria_down $i
    done

    echo "Loaded $num_databases new database(s)"

    # Shutdown target Victoria Metrics
    kill -SIGINT $target_pid
    check_victoria_down $TARGET_DIR
}

if [ -n "$DATADIR" ] && [ -n "$MULTIDIR" ]; then
    echo "Error: only one of DATADIR and MULTIDIR can be set simultaneously"
    exit 1
fi

if [ -n "$DATADIR" ] && [ ! -f $TARGET_DIR/flock.lock ]; then
    echo "Error: invalid Omnistat data directory $HOST_DIR"
    exit 1
fi

if [ -n "$MULTIDIR" ]; then
    echo "Merging databases under $MULTIDIR to $HOST_DIR"
    merge_databases
fi

echo "Starting Victoria Metrics using $HOST_DIR"
$VICTORIA_BIN $VICTORIA_ARGS \
    -httpListenAddr=:$TARGET_PORT \
    -storageDataPath=$TARGET_DIR &
pid=$!

wait_for_url $VICTORIA_URL $VICTORIA_INTERVAL $VICTORIA_TIMEOUT
if [ $? -ne 0 ]; then
    echo "Error: Victoria Metrics not responding"
    exit 1
fi

wait_for_url $GRAFANA_URL $GRAFANA_INTERVAL $GRAFANA_TIMEOUT
if [ $? -ne 0 ]; then
    echo "Error: Grafana not responding"
    exit 1
fi

echo "Omnistat dashboard ready: http://localhost:3000"

wait $pid
