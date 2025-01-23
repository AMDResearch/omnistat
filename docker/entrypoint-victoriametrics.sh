#!/bin/sh

reference_dir=/victoria-metrics-data

if [ ! -d $reference_dir ]; then
	echo "Missing $reference_dir directory"
	exit 1
fi

uid=$(stat -c "%u" $reference_dir)
gid=$(stat -c "%g" $reference_dir)

echo "Executing as user $uid:$gid"
exec su-exec $uid:$gid /victoria-metrics-prod "$@"
