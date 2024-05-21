# Introduction

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

Welcome to the documentation area for the **Omniwatch** project.  Use the navigation links on the left-hand side of this page to access more information on installation and capabilities.

[Browse Omniwatch source code on Github](https://github.com/AMDResearch/omniwatch)

## What is Omniwatch?

Omniwatch provides a set of utilities to aid cluster administrators or individual application developers to aggregate scale-out system metrics via low-overhead sampling across all hosts in a cluster or, alternatively on a subset of hosts associated with a specific user job. At its core, Omniwatch was designed to aid collection of key telemetry from AMD Instinct(tm) accelerators (on a per-GPU basis). Relevant target metrics include:

* GPU utilization (occupancy)
* High-bandwidth memory (HBM) usage
* GPU power
* GPU temperature
* GPU clock frequency (Mhz)
* GPU memory clock frequency (Mhz)
* GPU throttling events

To enable scalable collection of these metrics, Omniwatch provides a python-based [Prometheus](https://prometheus.io) client that supplies instantaneous metric values on-demand for periodic polling by a companion Prometheus server.

## User-mode vs System-level monitoring 

Omniwatch utilities can be deployed with two primary use-cases in mind that differ based on the end-consumer and whether the user has administrative rights or not.  The use cases are denoted as follows:

1. __System-wide monitoring__: requires administrative rights and is typically used to monitor all GPU hosts within a given cluster in a 24x7 mode of operation. Use this approach to support system-wide telemetry collection for all user workloads and optionally, provide job-level insights for systems running the [SLURM](https://slurm.schedmd.com) workload manager.
1. __User-mode monitoring__: does not require administrative rights and can be run entirely within user-space. This case is typically exercised by end application users running on production SLURM clusters who want to gather telemetry data within a single SLURM job allocation.  Frequently, this approach is performed entirely within a command-line `ssh` environment but Omniwatch includes support for downloading data after a job for visualization with a dockerized Grafana environment. Alternatively, standalone query utilities can be used to summarize collected metrics at the conclusion of a SLURM job.

To demonstrate the overall data collection architecture employed by Omniwatch in these two modes of operation, the following diagrams highlight the data collector layout and life-cycle for both cases.

![System Mode](images/architecture_system-mode.png)
![User Mode](images/architecture_user-mode.png)

In the __system-wide monitoring__ case, a system administrator enables data collectors permanently on all relevant hosts within the cluster and configures a Prometheus server to periodically poll these nodes (e.g. at 1 minute or 5 minute intervals). The Prometheus server typically runs on the cluster head node (or separate administrative host) and does not require GPU resources locally. For real-time and historical queries, the system administrator also enables a Grafana instance that queries the Prometheus datastore to provide a variety of visualizations with collected data. Example visualization panels using this approach are highlighted in the [Grafana](./grafana.md) section.

Conversely, in the __user-mode__ case,  Omniwatch data collector(s) and a companion prometheus server are deployed temporarily on hosts assigned to a user's SLURM job.  At the end of the job, Omniwatch utilities can query cached telemetry data to summarize GPU utilization details or it can be visualized offline after the job completes. An example command-line summary from this user-mode approach is highlighted as follows:

```none
----------------------------------------
Omniwatch Report Card for Job # 44092
----------------------------------------

Job Overview (Num Nodes = 1, Machine = Snazzy Cluster)
 --> Start time = 2024-05-17 10:14:00
 --> End   time = 2024-05-17 10:19:00

GPU Statistics:

           | Utilization (%)  |  Memory Use (%)  | Temperature (C)  |    Power (W)     |
     GPU # |    Max     Mean  |    Max     Mean  |    Max     Mean  |    Max     Mean  |
    ------------------------------------------------------------------------------------
         0 |  100.00   55.56  |   95.09   63.40  |   61.00   52.89  |  300.00  177.67  |
         1 |  100.00   44.33  |   94.97   63.32  |   64.00   54.11  |  387.00  160.22  |
         2 |  100.00   55.56  |   94.92   63.28  |   60.00   51.11  |  304.00  176.78  |
         3 |  100.00   55.56  |   94.78   63.20  |   58.00   48.89  |  354.00  184.67  |

--
Query execution time = 0.1 secs
Version = 0.2.0
```

## Software dependencies

The basic minimum dependencies to enable data collection via Omniwatch tools in user-mode are as follows:

* [ROCm](https://rocm.docs.amd.com/en/latest)
* Python dependencies (see top-level requirements.txt)

System administrators wishing to deploy a system-wide GPU monitoring capability with near real-time visualization will also need one or more servers to host two additional services:

* [Grafana](https://github.com/grafana/grafana) - either local instance or can also leverage cloud-based infrastructure
* [Prometheus server](https://prometheus.io/docs/prometheus/latest/getting_started/) - used to periodically poll and aggregate data from multiple compute nodes


## Additional Features

TODO: discuss SLURM integration