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

# Control how long to wait for Victoria Metrics servers when they're
# started and stopped.
MAX_ATTEMPTS_UP=15
INTERVAL_UP=1
MAX_ATTEMPTS_DOWN=15
INTERVAL_DOWN=1

# Default Victoria Metrics configuration.
VICTORIA_BIN=/victoria-metrics-prod
VICTORIA_ARGS="-retentionPeriod=3y -loggerLevel=ERROR"

# Path to the temporary file used for exporting/importing databases.
DATA_FILE=/tmp/data.bin

# Checks to ensure services are ready.
VICTORIA_URL=http://omnistat:9090/-/healthy
GRAFANA_URL=http://grafana:3000/
INTERVAL_SERVICE=1

# Check Victoria Metrics server is running in the given address and it's
# aready for requests. If it's not running, retry $MAX_ATTEMPTS_UP times
# before giving up. Returns 0 if check is successful, otherwise returns 1.
check_victoria_up() {
    local base_url=$1
    local check_url=$base_url/-/healthy
    local num_attempts=0

    while [ $num_attempts -lt $MAX_ATTEMPTS_UP ]; do
        num_attempts=$((num_attempts + 1))
        curl -s --fail --head $check_url > /dev/null
        if [ $? -eq 0 ]; then
            echo ".. Server $base_url ready after $num_attempts attempt(s)"
            return 0
        fi
        sleep $INTERVAL_UP
    done

    echo ".. Server $base_url not ready after $MAX_ATTEMPTS_UP attempts"
    return 1
}

# Ensure Victoria Metrics server is no longer running by checking the lock file
# is available. If the lock cannot be acquired, retry $MAX_ATTEMPTS_DOWN
# times. Returns 0 when the server is no longer running, otherwise abort the
# execution of the script.
check_victoria_down() {
    local path=$1/flock.lock
    local num_attempts=0

    while [ $num_attempts -lt $MAX_ATTEMPTS_DOWN ]; do
        num_attempts=$((num_attempts + 1))

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

        sleep $INTERVAL_DOWN
    done

    echo "Error: Victoria Metrics server still active after $MAX_ATTEMPTS_DOWN attempts"
    exit 1
}

# Start a Victoria Metrics server in the background for merging purposes.
# Returns the PID of the process if successful, otherwise returns 0.
start_victoria() {
    local address=$1
    local path=$2

    $VICTORIA_BIN $VICTORIA_ARGS \
        -httpListenAddr=$address \
        -storageDataPath=$path \
        -search.disableCache &
    pid=$!

    check_victoria_up $address
    if [ $? -ne 0 ]; then
        echo "Unable to reach $address"
        return 0
    fi

    return $pid
}

merge_databases() {
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

while true; do
    curl -s --fail --head $VICTORIA_URL > /dev/null
    if [ $? -eq 0 ]; then
        break
    fi
    sleep $INTERVAL_SERVICE
done

while true; do
    curl -s --fail --head $GRAFANA_URL > /dev/null
    if [ $? -eq 0 ]; then
        break
    fi
    sleep $INTERVAL_SERVICE
done

echo "Omnistat dashboard ready: http://localhost:3000"

wait $pid
