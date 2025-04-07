# Grafana Dashboards

Omnistat provides several sample Grafana dashboards for cluster-wide
deployments that vary depending on the target environment. For example,
whether resource manager integration is desired or not.

Dashboard variants are automatically generated from *source* available under
the `source` directory. *Source* dashboards include supersets of panels, which
can be filtered out using the `filter-dashboard` script.

The following table shows a list of the sample pre-generated dashboards are
distributed with Omnistat, along with their supported panels:

| Dashboard    | ROCm                   | RMS                | Node Exporter          |
| :---:        | :---:                  | :---:              | :---:                  |
| `source`     | :heavy_check_mark:[^1] | :heavy_check_mark: | :heavy_check_mark:[^2] |
| `rms`        | :heavy_check_mark:     | :heavy_check_mark: | :heavy_check_mark:[^2] |
| `standalone` | :heavy_check_mark:     |                    | :heavy_check_mark:[^2] |

[^1]: Includes throttling events (experimental).
[^2]: Includes CPU, memory, IO, ethernet, and IB panels.

## Generate Custom Dashboards

The `filter-dashboard` script can also be used to generate new customized
dashboards with different subsets of panels. For example, the following command
can be used to generate a dashboard with support for ROCm and RMS metrics,
excluding panels that use metrics from Node Exporter:

```
./scripts/filter-dashboard -i json-models/rms-global.json --exclude-metrics node_
```

Note that dashboard variants cannot be imported into the same Grafana instance
with the same name.  If loading multiple dashboard variants is important, use
the `--replace-name` flag as follows:

```
./scripts/filter-dashboard -i json-models/rms-global.json --exclude-metrics node_ --replace-name RMS:RMSNoNode
```

## Synchronize Dashboards

The `sync-dashboard` script can be used to keep track of remote dashboards and
update them when new versions are available. It supports two operations: 1)
downloading dashboards from a remote Grafana server to a local directory, and
2) uploading dashboards from a local directory to a remote Grafana server.

It requires a Grafana API token, which can be generated using a [Grafana
Service Account](https://grafana.com/docs/grafana/latest/administration/service-accounts/).
Set the `GRAFANA_API_TOKEN` environment variable with the token.
For example:

```
GRAFANA_API_TOKEN=$(command-to-get-secret-token) ./scripts/sync-dashboard --grafana-url "https://grafana.example.com" download
```
