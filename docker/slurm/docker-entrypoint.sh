#!/bin/bash

set -e

if [ "$1" = "controller" ]; then
    service munge start
    service slurmctld start

    cp /host-source/docker/slurm/prometheus.yml /etc/prometheus/
    service prometheus start
fi

if [ "$1" = "node" ]; then
    service munge start
    service slurmd start

    # Install omniwatch based on the current working copy of the repository;
    # this docker compose environment is meant to be used for development and
    # testing.
    python3 -m venv /opt/omniwatch

    # Copy omniwatch source to /tmp avoid polluting the host with files
    # generated in the container.
    cp -R /host-source /tmp/omniwatch
    cd /tmp/omniwatch
    /opt/omniwatch/bin/python -m pip install .[query]
    cd
    rm -rf /tmp/omniwatch

    # Enable access from the controller container, which is running the
    # prometheus scraper.
    ip=$(dig +short controller)
    sed "s/127.0.0.1/127.0.0.1, $ip/" /host-source/docker/slurm/omniwatch.slurm \
        > /etc/omniwatch.config

    OMNIWATCH_CONFIG=/etc/omniwatch.config /opt/omniwatch/bin/gunicorn \
        -b 0.0.0.0:8000 omniwatch.node_monitoring:app --daemon
fi

sleep infinity
