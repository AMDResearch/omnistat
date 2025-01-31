# User-mode execution

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

In user-mode executions, Omnistat data collectors and a companion VictoriaMetrics
server are deployed temporarily on hosts assigned to a user's job, as
highlighted in {numref}`fig-user-mode`. The following assumptions are made
throughout the rest of this user-mode installation discussion:

__Assumptions__:
* [ROCm](https://rocm.docs.amd.com/en/latest/) v6.1 or newer is pre-installed
  on all GPU hosts.
* Installer has access to a distributed file-system; if no distributed
  file-system is present, installation steps need to be repeated across all nodes.


## Omnistat software installation

To begin, we download the Omnistat software and install necessary Python
dependencies. Per the assumptions above, we download and install Omnistat in a
path accessible from all nodes.

1. Download and expand latest release version.
   ```shell-session
   [user@login]$ REPO=https://github.com/AMDResearch/omnistat
   [user@login]$ curl -OLJ ${REPO}/archive/refs/tags/v{__VERSION__}.tar.gz
   [user@login]$ tar xfz omnistat-{__VERSION__}.tar.gz
   ```

2. Install dependencies.
   ```shell-session
   [user@login]$ cd omnistat-v{__VERSION__}
   [user@login]$ pip install --user -r requirements.txt
   [user@login]$ pip install --user -r requirements-query.txt
   ```

```{note}
Omnistat can also be installed as a Python package. Create a virtual
environment, and install Omnistat and its dependencies from the top
directory of the release.
```shell-session
[user@login]$ cd omnistat-v{__VERSION__}
[user@login]$ python -m venv ~/venv/omnistat
[user@login]$ ~/venv/omnistat/bin/python -m pip install .[query]
```

3. Download a **single-node** VictoriaMetrics server. Assuming a `victoria-metrics` server is not already present on the system,
   download and extract a [precompiled binary](https://github.com/VictoriaMetrics/VictoriaMetrics/releases/latest) from upstream. This binary can generally be stored in any directory accessible by the user, but the path to the binary will need to be known during the next section when configuring user-mode execution. Note that VictoriaMetrics provides a larger number binary releases and we typically use the `victoria-metrics-linux-amd64` variant on x86_64 clusters.

## Configuring user-mode Omnistat

For user-mode execution, Omnistat includes additional options in the `[omnistast.usermode]` section of the runtime configuration file. A portion of the [default](https://github.com/AMDResearch/omnistat/blob/main/omnistat/config/omnistat.default) config file is highlighted below with the lines in yellow indicating settings to confirm or customize for your local environment.

```eval_rst
.. code-block:: ini
   :caption: Sample Omnistat configuration file
   :emphasize-lines: 2,4,8,11,12,13

    [omnistat.collectors]
    port = 8001
    enable_rocm_smi = True
    enable_rms = True

    [omnistat.collectors.rms]
    job_detection_mode = file-based
    job_detection_file = /tmp/omni_rmsjobinfo_user

    [omnistat.usermode]
    ssh_key = ~/.ssh/id_rsa
    victoria_binary = /path/to/victoria-metrics
    victoria_datadir = data_prom
    victoria_logfile = vic_server.log
    push_frequency_mins = 5
  ```

## Running Jobs

To enable user-mode data collection for a specifid job, add logic within your job script to start and stop the collection mechanism before and after running your desired application(s).  Omnistat includes an `omnistat-usermode` utility to help automate this process and the examples below highlight the steps for simple SLURM and Flux job scripts.  Note that the lines highlighted in
yellow need to be customized for the local installation path.


   ### SLURM example
```eval_rst
.. code-block:: bash
   :emphasize-lines: 6-7
   :caption: Example SLURM job file using user-mode Omnistat with a 10 second sampling interval

   #!/bin/bash
   #SBATCH -N 8
   #SBATCH -n 16
   #SBATCH -t 02:00:00

    export OMNISTAT_CONFIG=/path/to/omnistat.config
    export OMNISTAT_DIR=/path/to/omnistat

    # Beginning of job - start data collector
    ${OMNISTAT_DIR}/omnistat-usermode --start --interval 10

    # Run application(s) as normal
    srun <options> ./a.out
    
    # End of job -  stop data collection, generate summary and store collected data by jobid
    ${OMNISTAT_DIR}/omnistat-usermode --stopexporters
    ${OMNISTAT_DIR}/omnistat-query --job ${SLURM_JOB_ID} --interval 10
    ${OMNISTAT_DIR}/omnistat-usermode --stopserver
    mv data_prom data_prom_${SLURM_JOB_ID}
  ```

  ### Flux example

```eval_rst
.. code-block:: bash
   :emphasize-lines: 8-9
   :caption: Example FLUX job file using user-mode Omnistat with a 1 second sampling interval

   #!/bin/bash
   #flux: -N 8
   #flux: -n 16
   #flux: -t 2h

   jobid=`flux getattr jobid`

   export OMNISTAT_CONFIG=/path/to/omnistat.config
   export OMNISTAT_DIR=/path/to/omnistat

   # Beginning of job - start data collector
   ${OMNISTAT_DIR}/omnistat-usermode --start --interval 1

   # Run application(s) as normal
   flux run <options> ./a.out

   # End of job -  stop data collection, generate summary and store collected data by jobid
   ${OMNISTAT_DIR}/omnistat-usermode --stopexporters
   ${OMNISTAT_DIR}/omnistat-query --job ${jobid} --interval 1
   ${OMNISTAT_DIR}/omnistat-usermode --stopserver
   mv data_prom data_prom.${jobid}
  ```

 In both examples above, the `omnistat-query` utility is used at the end of the job to query collected telemetry (prior to shutting down the server) for the assigned jobid. This should embed an ascii summary for the job similar to the [report card](query_report_card) example mentioned in the Overview directly within the recorded job output.

## Exploring results with a local Docker environment

To explore results generated for user-mode executions of Omnistat, we provide
a Docker environment that will automatically launch the required services
locally. That includes Prometheus to read and query the stored data, and
Grafana as visualization platform to display time series and other metrics.

To explore results:

1. Copy Prometheus data collected with Omnistat to `./prometheus-data`. The
   entire `datadir` defined in the Omnistat configuration needs to be copied
   (e.g. a `data` directory should be present under `./prometheus-data`).
2. Start services:
   ```shell-session
   [user@login]$ export PROMETHEUS_USER="$(id -u):$(id -g)"
   [user@login]$ docker compose up -d
   ```
   User and group IDs are exported with the `PROMETHEUS_USER` variable to ensure
   the container has the right permissions to read the local data under the
   `./prometheus-data` directory.
4. Access Grafana dashboard at [http://localhost:3000](http://localhost:3000).
   Note that starting Grafana can take a few seconds.
5. Stop services:
   ```shell-session
   [user@login]$ docker compose down
   ```

## Exporting time series data

To explore and process raw Omnistat data without relying on the Docker
environment or a Prometheus/VictoriaMetrics server, the `omnistat-query` tool
has an option to export all time series data to a CSV file.

```eval_rst
.. code-block:: bash
   :caption: Using the export option in `omnistat-query`

   ${OMNISTAT_DIR}/omnistat-query --job ${jobid} --interval 1 --export data.csv
  ```

Exported data can be easily loaded as a data frame using tools like Pandas for
further processing.

```eval_rst
.. code-block:: python
   :caption: Python script to read exported time series as a Pandas data frame

   import pandas

   df = pandas.read_csv("data.csv", header=[0, 1, 2], index_col=0)

   # Select a single metric
   df["rocm_utilization_percentage"]

   # Select a single metric and node
   df["rocm_utilization_percentage"]["node01"]

   # Select a single metric, node, and GPU
   df["rocm_utilization_percentage"]["node01"]["0"]

   # Select GPU Utilization and GPU Memory Utilization for GPU ID 0 in all nodes
   df.loc[:, pandas.IndexSlice[["rocm_utilization_percentage", "rocm_vram_used_percentage"], :, ["0"]]]

  ```

```eval_rst
.. code-block:: python
   :caption: Python script to plot average GPU Utilization per node

   import pandas
   import matplotlib.pyplot as plt

   df = pandas.read_csv("data.csv", header=[0, 1, 2], index_col=0)
   df.index = pandas.to_datetime(df.index)

   # Create a new dataframe with node averages
   node_mean_df = df["rocm_utilization_percentage"].T.groupby(level=['instance']).mean().T

   node_mean_df.plot(linewidth=1)
   plt.title("Mean utilization per node")
   plt.xlabel("Time")
   plt.ylabel("GPU Utilization (%)")
   plt.show()
  ```
