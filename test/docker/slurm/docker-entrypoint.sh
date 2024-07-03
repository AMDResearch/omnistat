#!/bin/bash

set -e

if [ "$1" = "controller" ]; then
    service munge start
    service slurmctld start

    cp /host-source/test/docker/slurm/prometheus.yml /etc/prometheus/
    service prometheus start
fi

if [ "$1" = "node" ]; then
    service munge start
    service slurmd start

    # Install omnistat based on the current working copy of the repository;
    # this docker compose environment is meant to be used for development and
    # testing.
    python3 -m venv /opt/omnistat

    # Copy omnistat source to /tmp avoid polluting the host with files
    # generated in the container.
    cp -R /host-source /tmp/omnistat
    cd /tmp/omnistat
    /opt/omnistat/bin/python -m pip install .[query]
    cd
    rm -rf /tmp/omnistat

    # Enable access from the controller container, which is running the
    # prometheus scraper.
    ip=$(dig +short controller)
    sed "s/127.0.0.1/127.0.0.1, $ip/" \
        /host-source/test/docker/slurm/omnistat.slurm > /etc/omnistat.config

    OMNISTAT_CONFIG=/etc/omnistat.config /opt/omnistat/bin/gunicorn \
        -b 0.0.0.0:8000 omnistat.node_monitoring:app --daemon
fi

sleep infinity
