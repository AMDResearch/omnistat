#!/bin/bash

set -e

TEST_OMNISTAT_EXECUTION=${TEST_OMNISTAT_EXECUTION:-source}

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
    # testing. Copy entire directory to avoid polluting the host with files
    # generated in the container.
    cp -R /host-source /source

    # Enable access from the controller container, which is running the
    # prometheus scraper.
    ip=$(dig +short controller)
    sed "s/127.0.0.1/127.0.0.1, $ip/" \
        /host-source/test/docker/slurm/omnistat.slurm > /etc/omnistat.config

    # Create a Python virtual environment to install Omnistat and/or its
    # dependencies.
    python3 -m venv /opt/omnistat
    . /opt/omnistat/bin/activate

    cd /source

    case "$TEST_OMNISTAT_EXECUTION" in
        "source")
            echo "Executing Omnistat from uninstalled source"
            path=.
            pip install -r requirements.txt
            pip install -r requirements-query.txt
            ;;
        "package")
            echo "Executing Omnistat from installed package"
            path=/opt/omnistat/bin
            pip install .[query]
            cd # Change directory to avoid loading uninstalled module
            ;;
        *)
            echo "Unknown TEST_OMNISTAT_EXECUTION value"
            exit 1
            ;;
    esac

    OMNISTAT_CONFIG=/etc/omnistat.config $path/omnistat-monitor
fi

sleep infinity
