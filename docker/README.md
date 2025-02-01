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

1. Copy Omnistat database collected in usermode to a local directory. All the
   contents of the `victoria_datadir` path (defined in the Omnistat
   configuration) need to be copied, typically resulting in the
   following hierarchy:
   ```
   data/cache/
   data/data/
   data/flock.lock
   data/indexdb/
   data/metadata/
   data/snapshots/
   data/tmp/
   ```
2. Start services:
   ```
   DATADIR=./path/to/data docker compose up
   ```
   Services will run with the same user and group ID as the owner and group of
   the data directory. If `DATADIR` is not set, it will default to `./data`.
3. Access Grafana dashboard at http://localhost:3000. Note that starting
   Grafana can take a few seconds.
4. Stop services:
   ```
   docker compose down
   ```

### Combining Omnistat databases

To work with multiple Omnistat databases at the same time: create a directory,
copy the desired Omnistat databases as subdirectories, and start services with
the `MULTIDIR` variable pointing to new directory.

When starting the Docker Compose environment, all the databases under the
`$MULTIDIR` directory will be loaded into a common database that will be used
to visualize all the data.

1. As an example, the following `collection` directory contains two Omnistat
   databases under the `data-{0,1}` subdirectories:
   ```
   collection/data-0/
   collection/data-1/
   ```
2. Start the services with the `MULTIDIR` variable to merge multiple
   databases:
   ```
   MULTIDIR=./path/to/collection docker compose up
   ```
3. While the services are stared, a new database named `_merged` will be
   created:
   ```
   collection/data-0/
   collection/data-1/
   collection/_merged/
   ```
   And once the merged database is ready, all the information from `data-0`
   and `data-1` will be visible in the local Grafana dashboard at
   http://localhost:3000.

It's also possible to copy new databases to the same directory at a later
time. To merge a new database, simply stop the Docker Compose environment and
start it again with the same `docker compose up`. Only newly copied
directories will be loaded into the merged database.
