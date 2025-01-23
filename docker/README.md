## Environment to view local Omnistat data

This Docker Compose environment is meant to be used as a tool to visualize
data collected with usermode Omnistat without the need to use external
resources.

Two different services are required to view Omnistat data:
 - **Victoria Metrics**: used to read and query data.
 - **Grafana**: used as visualization platform to display time series and
   other metrics.

This environment will automatically launch containers, configure both services,
connect Grafana and Victoria Metrics, and pre-load a couple of dashboards:
 - `omnistat-index`: List all jobs in the stored database.
 - `omnistat-job`: View details for a single job.

### Deploy

1. Copy Omnistat data collected with Omnistat to `./victoria-metrics-data`. All
   the contents of the `victoria_datadir` defined in the Omnistat configuration
   needs to be copied (e.g. `data`, `indexdb`, `metadata` directories and a
   `flock.lock` file should be present under `./victoria-metrics-data`).
2. Start services:
   ```
   docker compose up -d
   ```
   Services will run with the same user and group ID as the owner and group of
   the `./victoria-metrics-data` directory.
4. Access Grafana dashboard at http://localhost:3000. Note that starting
   Grafana can take a few seconds.
5. Stop services:
   ```
   docker compose down
   ```
