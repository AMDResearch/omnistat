# Grafana Dashboards

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

Dashboards allow cluster telemetry data to be visualized interactively in near real-time.
Omnistat provides several sample dashboards for cluster-wide deployments that vary depending on whether resource manager integration is desired or not (screenshots of the variants with resource manager integration enabled are highlighted in [Example Screenshots](#example-screenshots)). JSON sources for example dashboards that can be used in local deployments are highlighted below. Note that in addition to querying GPU data gathered with the Omnistat data collector, these example dashboards assume that [node-exporter](https://github.com/prometheus/node_exporter) data is also being collected.

- *RMS* dashboards provide integration with *Resource Managers* like
  SLURM.
  - [Global Dashboard](https://github.com/AMDResearch/omnistat/blob/main/grafana/json-models/rms-global.json):
    provides an overview of the system, cluster-level telemetry for allocated
    and unallocated nodes, and job indices.
  - [Node Dashboard](https://github.com/AMDResearch/omnistat/blob/main/grafana/json-models/rms-node.json):
    job allocation timeline and detailed metrics for a single node in the
    cluster.
  - [Job Dashboard](https://github.com/AMDResearch/omnistat/blob/main/grafana/json-models/rms-job.json):
    provides detailed time-series data, load distribution, and other metrics for
    a single job.
- *Standalone* dashboards are meant to work without a resource manager.
  - [Global Dashboard](https://github.com/AMDResearch/omnistat/blob/main/grafana/json-models/standalone-global.json):
    provides an overview of the system and cluster-level telemetry.
  - [Node Dashboard](https://github.com/AMDResearch/omnistat/blob/main/grafana/json-models/standalone-node.json):
    detailed metrics for a single node in the cluster.


## Import dashboards

After [installing and configuring Omnistat](installation/system-install),
ensure the Prometheus data source has been added to Grafana, and then import
the sample dashboards.

To add a data source to Grafana:
1. Click **Connections** in the left-side menu.
2. Enter "Prometheus" in the search dialog, and click the **Prometheus** button
   under the search box.
3. Configure the new Prometehus data source following instructions and provide
   the hostname and port where Omnistat's Prometheus server is running.

To import a dashboard:
1. Click **Dashboards** in the left-side menu.
2. Click **New** and select **New Dashboard** from the drop-down menu.
3. On the dashboard, click **+ Add visualization**.
4. Upload the dashboard JSON file.

Sample dashboards are configured using standard default values for settings
such as network ports, but may require changes depending on the environment.
The following variables represent the most relevant dashboard settings:
- `source`: Name of the Prometheus data source where the data is stored.
   Defaults to `prometheus`.
- `node_exporter_port`: Port of the Prometheus Node Exporter. Defaults to `9100`.

To configure a dashboard:
1. Open a dashboard in edit mode.
2. Click **Dashboard settings** located at the top of the page.
3. Click **Variables**.
4. Click the desired variable and update its value.

(example-screenshots)=
## Example screenshots

![Global dashboard screenshot](images/dashboard-global.png)

![Node dashboard screenshot](images/dashboard-node.png)

![Job dashboard screenshot](images/dashboard-job.png)
