# Grafana Dashboards

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

## Import dashboards

Dashboards allow showing real-time cluster telemetry data in a visual form.
Omnistat provides two sample dashboards:
- [Global Dashboard](https://github.com/AMDResearch/omnistat/blob/main/grafana/json-models/slurm-global.json):
  includes an overview of the system, job indices, and cluster-level telemetry.
- [Job Dashboard](https://github.com/AMDResearch/omnistat/blob/main/grafana/json-models/slurm-job.json):
  includes more detailed time-series data and other metrics for a particular
  job.

After installing and configuring Omnistat, ensure the Prometheus data source
has been added to Grafana, and then import the sample dashboards.

To import a dashboard:
1. Click Dashboards in the left-side menu.
2. Click New and select New Dashboard from the drop-down menu.
3. On the dashboard, click + Add visualization.

## Example screenshots

![Global dashboard screenshot](images/dashboard-global.png)

![Job dashboard screenshot](images/dashboard-job.png)
