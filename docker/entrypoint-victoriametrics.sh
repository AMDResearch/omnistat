#!/bin/sh
#
# entrypoint-victoriametrics - Switch user running Victoria Metrics container
#
# Script to switch user running in the container to the same owner as the
# given reference directory. Switching the user ensures the permissions of
# files generated during the execution of the container under the reference
# directory match the user in the host.

reference_dir=/victoria-metrics-data

if [ ! -d $reference_dir ]; then
	echo "Missing $reference_dir directory"
	exit 1
fi

uid=$(stat -c "%u" $reference_dir)
gid=$(stat -c "%g" $reference_dir)

echo "Executing as user $uid:$gid"
exec su-exec $uid:$gid /victoria-metrics-prod "$@"
