Docker Compose environment meant to set up the required services to visualize
and analyze data collected with usermode Omniwatch.

Two different services are required to view Omniwatch data:
 1. Prometheus: used to read and query tracing data.
 2. Grafana: used as visualization platform to display collected metrics.

The Docker Compose environment automatically sets up both services, connects
Grafana to Prometheus, and pre-loads a couple of dashboards:
 - `omniwatch-index`: List jobs.
 - `omniwatch-job`: Analyze a single job.

## Deploy

1. Copy Prometheus data collected with Omniwatch to `./prometheus-data`. The
   entire `datadir` defined in the Omniwatch configuration needs to be copied
   (e.g. a `data` directory should be present under `./prometheus-data`).
2. Start services:
```
export PROMETHEUS_USER="$(id -u):$(id -g)"
docker compose up -d
```
3. Access Grafana dashboard at http://localhost:3000. Note that starting
   Grafana can take ~10 seconds.
4. Stop services:
```
docker compose down
```
