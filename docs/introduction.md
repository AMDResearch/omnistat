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

TODO: include architecture diagram

## User-mode vs System-level monitoring 

TODO

## Software dependencies

The basic minimum dependencies to enable data collection via Omniwatch tools in user-mode are as follows:

* [ROCm](https://rocm.docs.amd.com/en/latest)
* Python dependencies (see top-level requirements.txt)

System administrators wishing to deploy a system-wide GPU monitoring capability with near real-time visualization will also need one or more servers to host two additional services:

* [Grafana](https://github.com/grafana/grafana) - either local instance or can also leverage cloud-based infrastructure
* [Prometheus server](https://prometheus.io/docs/prometheus/latest/getting_started/) - use to periodically poll and aggregate data from multiple compute nodes


## Additional Features

TODO: discuss SLURM integration