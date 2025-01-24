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

1. Copy Omnistat database collected in usermode to `./data`.  All the contents
   of the `victoria_datadir` path (defined in the Omnistat configuration) need
   to be copied, typically resulting in the following hierarchy:
   ```
   ./data/cache/
   ./data/data/
   ./data/flock.lock
   ./data/indexdb/
   ./data/metadata/
   ./data/snapshots/
   ./data/tmp/
   ```
2. Start services:
   ```
   docker compose up -d
   ```
   Services will run with the same user and group ID as the owner and group of
   the `./data` directory.
4. Access Grafana dashboard at http://localhost:3000. Note that starting
   Grafana can take a few seconds.
5. Stop services:
   ```
   docker compose down
   ```

### Combining several Omnistat databases

Copying a single Omnistat database to `./data` works well to visualize a single
execution. To work with several Omnistat databases, copy them to different
subdirectories under `./data.d`. For instance:
```
./data.d/database-0/
./data.d/database-0/cache/
./data.d/database-0/data/
./data.d/database-0/flock.lock
./data.d/database-0/indexdb/
./data.d/database-0/metadata/
./data.d/database-0/snapshots/
./data.d/database-0/tmp/
./data.d/database-1/
...
```
Where `database-0` and `database-1` are just example names used to store two
different Omnistat databases.

Databases under the `./data.d` directory are imported into a common database
when starting the Docker Compose environment. Note that importing databases
with this approach means the main database under `./data` will be modified.

Each database is imported once. To force reloading all the databases, use the
`FORCE_RELOAD` environment variable:
```
FORCE_RELOAD=1 docker-compose up -d
```
