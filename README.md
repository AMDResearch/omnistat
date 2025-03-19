[![Documentation](https://github.com/AMDResearch/omnistat/actions/workflows/docs.yml/badge.svg)](https://amdresearch.github.io/omnistat/)
[![System mode](https://github.com/AMDResearch/omnistat/actions/workflows/test.yml/badge.svg)](https://github.com/AMDResearch/omnistat/actions/workflows/test.yml)
[![User mode - Pull](https://github.com/AMDResearch/omnistat/actions/workflows/test-user-pull.yml/badge.svg)](https://github.com/AMDResearch/omnistat/actions/workflows/test-user-pull.yml)
[![User mode - Push](https://github.com/AMDResearch/omnistat/actions/workflows/test-user-push.yml/badge.svg)](https://github.com/AMDResearch/omnistat/actions/workflows/test-user-push.yml)


# Omnistat

## General

Omnistat provides a set of utilities to aid cluster administrators or
individual application developers to aggregate scale-out system
metrics via low-overhead sampling across all hosts in a cluster or,
alternatively on a subset of hosts associated with a specific user
job. Omnistat infrastructure can aid in the collection of key
telemetry from AMD Instinct™ accelerators (on a per-GPU
basis). Relevant target metrics include:

* GPU utilization (occupancy)
* High-bandwidth memory (HBM) usage
* GPU power
* GPU temperature
* GPU clock frequency
* GPU memory clock frequency
* GPU block error counts
* GPU throttling events
* Inventory information
  * ROCm driver version
  * GPU type
  * GPU vBIOS version

The data can be scraped for detailed visualization and analysis via a
combination of [Prometheus](https://prometheus.io/) /
[VictoriaMetrics](https://github.com/VictoriaMetrics/VictoriaMetrics)
and [Grafana](https://github.com/grafana/grafana). Users can also
generate PDF reports summarizing resource utilization on a per job
basis with SLURM entirely in user-space.


For more information on available features and installation steps
please refer to the online [documentation](https://amdresearch.github.io/omnistat/).

--- 
Omnistat is an AMD open source research project and is not supported
as part of the ROCm software stack. We welcome contributions and
feedback from the community. 

Licensing information can be found in the [LICENSE](LICENSE) file.
