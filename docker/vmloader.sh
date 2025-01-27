#!/bin/sh
#
# vmloader -- Start Victoria Metrics with optional database merge
#
# Start Victoria Metrics to serve data under the /data directory.
# When the MERGE variable is set to 1, the /data directory will be used as a
# source of several databases that will be merged into /data/_merged.
#
# Merge sequentially starts a Victoria Metrics instance for each source
# database, exports the data to a file, and then imports it into the target
# database.

TARGET_URL=localhost:9090
TARGET_DIR=/data
if [ "$MERGE" == "1" ]; then
    TARGET_DIR=/data/_merged
fi

SOURCE_URL=localhost:8428
SOURCE_DIR=/data

MAX_ATTEMPTS=10
CHECK_INTERVAL=1

DATA_FILE=/tmp/data.bin

VM_BIN=/victoria-metrics-prod
VM_ARGS="-retentionPeriod=3y"

# Check Victoria Metrics server in the given address, making sure it's running
# and ready for requests. If it's not running, retry $MAX_ATTEMPTS times
# before giving up. Returns 0 if check is successful, otherwise returns 1.
check_victoriametrics() {
    local base_url=$1
    local check_url=$base_url/-/healthy
    local num_attempts=0
    while [ $num_attempts -lt $MAX_ATTEMPTS ]; do
        num_attempts=$(($num_attempts + 1))
        curl -s --fail --head $check_url > /dev/null
        if [ $? -eq 0 ]; then
            echo "Server $base_url ready after $num_attempts attempt(s)"
            return 0
        fi
        sleep $CHECK_INTERVAL
    done
    echo "Server $base_url is not ready after $MAX_ATTEMPTS attempts"
    return 1
}

# Ensure Victoria Metrics server is no longer running by checking the lock file
# is available. Times out after 10s.
check_victoriametrics_lock() {
    local path=$1/flock.lock
    local timeout=10
    local elapsed_time=0
    local interval=1 

    while true; do
        # Subshell to acquire database lock. Returns 0 if lock can be acquired.
        (
            flock -x -n 200 && {
                exit 0
            }
        exit 1
        ) 200>"$path"

        if [ $? -eq 0 ]; then
            return 0
        fi

        if [ "$elapsed_time" -ge "$timeout" ]; then
            echo "Error: server active after stopping it: $path"
            exit 1
        fi

        sleep $interval
        elapsed_time=$((elapsed_time + interval))
    done
}

# Start a Victori Metrics server in the background for merging purposes.
# Returns the PID of the process if successful, otherwise returns 0.
start_merge_victoriametrics() {
    local address=$1
    local path=$2

    # -search.maxConcurrentRequests=1
    $VM_BIN $VM_ARGS \
        -httpListenAddr=$address \
        -storageDataPath=$path \
        -search.disableCache &
    pid=$!
    check_victoriametrics $address
    if [ $? -ne 0 ]; then
        echo "Unable to reach $address"
        return 0
    fi

    return $pid
}

load_databases() {
    echo "Start target Victoria Metrics"
    start_merge_victoriametrics $TARGET_URL $TARGET_DIR
    target_pid=$?
    if [ $target_pid -eq 0 ]; then
        echo "Error: failed to start target Victoria Metrics server"
        exit 1
    fi

    echo "Load job databases"
    num_databases=0
    for i in $SOURCE_DIR/*; do
        if [ ! -d $i ]; then
            continue
        fi

        dir_name=$(basename $i)
        if [ "$dir_name" == "_merged" ]; then
            continue
        fi

        if [ ! -f $i/flock.lock ]; then
            echo "Skip invalid database: $i"
            continue
        fi

        if [ -f $TARGET_DIR/.$dir_name ]; then
            echo "Skip pre-existing database: $i"
            continue
        fi

        echo "Load $i"
        start_merge_victoriametrics $SOURCE_URL $i
        source_pid=$!
        if [ $source_pid -eq 0 ]; then
            echo "Failed to load $i"
            continue
        fi

        echo "Export data from $i"
        curl -s --fail $SOURCE_URL/api/v1/export/native -d 'match[]={__name__!~"vm_.*"}' > $DATA_FILE
        if [ $? -ne 0 ]; then
            echo "Failed to export $i"
            continue
        fi

        # Shutdown source Victoria Metrics
        kill -SIGINT $source_pid

        echo "Import data from $i to $TARGET_URL"
        curl -s --fail -X POST $TARGET_URL/api/v1/import/native -T $DATA_FILE
        if [ $? -ne 0 ]; then
            echo "Failed to import $i"
            continue
        fi

        rm -f $DATA_FILE
        touch $TARGET_DIR/.$dir_name
        num_databases=$(($num_databases + 1))

        check_victoriametrics_lock $i
    done

    echo "Loaded $num_databases database(s) into $TARGET_URL"

    # Shutdown target Victoria Metrics
    kill -SIGINT $target_pid
    check_victoriametrics_lock $TARGET_DIR
}

if [ "$MERGE" == "1" ]; then
    echo "Merge databases under the data directory"
    load_databases
fi

port=$(echo $TARGET_URL | awk -F':' '{print $2}')
exec $VM_BIN $VM_ARGS -httpListenAddr=:$port -storageDataPath=$TARGET_DIR
