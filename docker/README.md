## Environment to view local Omniwatch data

This Docker Compose environment is meant to be used as a tool to visualize
data collected with usermode Omniwatch without the need to use external resources.

Two different services are required to view Omniwatch data:
 - **Prometheus**: used to read and query data.
 - **Grafana**: used as visualization platform to display time series and
   other metrics.

This environment will automatically launch containers, configure both services,
connect Grafana and Prometheus, and pre-load a couple of dashboards:
 - `omniwatch-index`: List all jobs in the stored database.
 - `omniwatch-job`: View details for a single job.

### Deploy

1. Copy Prometheus data collected with Omniwatch to `./prometheus-data`. The
   entire `datadir` defined in the Omniwatch configuration needs to be copied
   (e.g. a `data` directory should be present under `./prometheus-data`).
2. Start services:
   ```
   export PROMETHEUS_USER="$(id -u):$(id -g)"
   docker compose up -d
   ```
   User and group IDs are exported with the `PROMETHEUS_USER` variable to ensure
   the container has the right permissions to read the local data under the
   `./prometheus-data` directory.
4. Access Grafana dashboard at http://localhost:3000. Note that starting
   Grafana can take ~10 seconds.
5. Stop services:
   ```
   docker compose down
   ```
