# Omniwatch

## General

Omniwatch provides a set of utilities to aid cluster administrators or
individual application developers to aggregate scale-out system
metrics via low-overhead sampling across all hosts in a cluster or,
alternatively on a subset of hosts associated with a specific user
job. Omniwatch infrastructure can aid in the collection of key
telemetry from AMD Instinct™ accelerators (on a per-GPU
basis). Relevant target metrics include:

* GPU utilization (occupancy)
* High-bandwidth memory (HBM) usage
* GPU power
* GPU temperature
* GPU clock frequency (Mhz)
* GPU memory clock frequency (Mhz)
* GPU throttling events

The data can be scraped for detailed visualization and analysis via
a combination of [Prometheus](https://prometheus.io/) and
[Grafana](https://github.com/grafana/grafana).


For more information on available features and installation steps
please refer to the online [documentation](https://amdresearch.github.io/omniwatch/).

--- 
Omniwatch is an AMD open source research project and is not supported
as part of the ROCm software stack. We welcome contributions and
feedback from the community. 

Licensing information can be found in the [LICENSE](LICENSE) file.
=======
# Installation of Pre-requisites

```bash
python3 -m pip install -r requirements.txt
```

# To Run as Standalone - Python
```bash
python3 node_monitoring.py [config_file_path]
```
# To Run as Standalone - Executable
```bash
./dist/omniwatch [config_file_path]
```


# To Run as a Service
```bash
sudo cp omniwatch.service /etc/systemd/system/
sudo enable omniwatch
sudo start omniwatch
```



