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
   $DATADIR/cache/
   $DATADIR/data/
   $DATADIR/flock.lock
   $DATADIR/indexdb/
   $DATADIR/metadata/
   $DATADIR/snapshots/
   $DATADIR/tmp/
   ```
2. Start services:
   ```
   DATADIR=./path/to/data docker compose up
   ```
   Services will run with the same user and group ID as the owner and group of
   the data directory.
4. Access Grafana dashboard at http://localhost:3000. Note that starting
   Grafana can take a few seconds.
5. Stop services:
   ```
   docker compose down
   ```

### Combining Omnistat databases

To work with multiple Omnistat databases at the same time, create a directory
and copy the desired databases, and then start services with the `MULTIDIR`
variable:
```
MULTIDIR=./path/to/multidir/data docker compose up
```

Databases under `$MULTIDIR` directory will be loaded into a common database
under `$MULTIDIR/_merged` when starting the Docker Compose environment,
resulting in the following hierarchy:
```
$MULTIDIR/database-0/
$MULTIDIR/database-1/
...
$MULTIDIR/_merged/
```
Where `database-*` are just example directory names that store different
Omnistat databases, and `_merged` is the location of the generated database
that combines all other databases in the same directory.
