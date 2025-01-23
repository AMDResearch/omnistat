#!/bin/sh

SOURCE_URL=localhost:8428
TARGET_URL=victoriametrics:9090

MAX_ATTEMPTS=10
CHECK_INTERVAL=1

check_victoriametrics() {
	base_url=$1
	check_url=$base_url/-/healthy
	num_attempts=0
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

echo "Start data loader"

check_victoriametrics $TARGET_URL
if [ $? -ne 0 ]; then
	echo "Error: unable to reach $TARGET_URL"
	exit 1
fi

echo "Load job databases (force reload $FORCE_RELOAD)"

num_databases=0
for i in /jobs/*; do
	if [ ! -d $i ]; then
		continue
	fi

	if [ ! -f $i/flock.lock ]; then
		echo "Skip invalid database: $i"
		continue
	fi

	if [ "$FORCE_RELOAD" != "1" ] && [ -f $i/.omnistat-loaded ]; then
		echo "Skip pre-existing database: $i"
		continue
	fi

	echo "Load $i"

	/victoria-metrics-prod \
		-httpListenAddr=$SOURCE_URL \
		-storageDataPath=$i \
		-search.disableCache &
	pid=$!

	check_victoriametrics $SOURCE_URL
	if [ $? -ne 0 ]; then
		echo "Failed to load $i: unable to reach $SOURCE_URL"
		continue
	fi

	echo "Export data $i"
	curl -s --fail $SOURCE_URL/api/v1/export/native -d 'match[]={__name__!~"vm_.*"}' > /tmp/data.bin
	if [ $? -ne 0 ]; then
		echo "Failed to export $i"
		continue
	fi

	# Shutdown local Victoria Metrics 
	kill -SIGINT $pid

	echo "Import $i"
	curl -s --fail -X POST $TARGET_URL/api/v1/import/native -T /tmp/data.bin
	if [ $? -ne 0 ]; then
		echo "Failed to import $i"
		continue
	fi

	rm -f /tmp/data.bin
	touch $i/.omnistat-loaded
	num_databases=$(($num_databases + 1))
done

echo "Loaded $num_databases database(s) into $TARGET_URL"

exit 0
