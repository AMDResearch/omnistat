# User-mode execution

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

## Installing Omnistat

1. Create a virtual environment in a shared directory, with Python 3.8, 3.9,
   or 3.10.
   ```
   $ python -m venv ~/omnistat
   ```

2. From to root directory of the Omnistat repository, install omnistat in
   the virtual environment.
   ```
   $ ~/omnistat/bin/python -m pip install .[query]
   ```

## Running a SLURM Job

In the SLURM job script, add the following lines to start and stop the data
collection before and after running the application.

```
export OMNISTAT_CONFIG=~/omnistat/omnistat.config

# Start data collector
~/omnistat/bin/omnistat-util --start --interval 1

# Run application
sleep 10

# Stop data collector
~/omnistat/bin/omnistat-util --stop

# Query server to generate job report
~/omnistat/bin/omnistat-util --startserver
~/omnistat/bin/omnistat-util --job ${SLURM_JOB_ID}
~/omnistat/bin/omnistat-util --stopserver
```

## Exploring results with a local Docker environment

To explore results generated for user-mode executions of Omnistat, we provide
a Docker environment that will automatically launch the required services
locally. That includes Prometheus to read and query the stored data, and
Grafana as visualization platform to display time series and other metrics.

To explore results:

1. Copy Prometheus data collected with Omnistat to `./prometheus-data`. The
   entire `datadir` defined in the Omnistat configuration needs to be copied
   (e.g. a `data` directory should be present under `./prometheus-data`).
2. Start services:
   ```
   $ export PROMETHEUS_USER="$(id -u):$(id -g)"
   $ docker compose up -d
   ```
   User and group IDs are exported with the `PROMETHEUS_USER` variable to ensure
   the container has the right permissions to read the local data under the
   `./prometheus-data` directory.
4. Access Grafana dashboard at [http://localhost:3000](http://localhost:3000).
   Note that starting Grafana can take a few seconds.
5. Stop services:
   ```
   $ docker compose down
   ```
