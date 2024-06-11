# Installation

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

## System-wide deployment

### Node-level deployment (client)

#### Installation with pip in a virtual environment

1. Create a virtual environment, with Python 3.8, 3.9, or 3.10.
   ```
   python -m venv /opt/omniwatch
   ```

2. Install omniwatch in virtual environment. The virtual environment can also
   be used by sourcing the `./opt/omniwatch/bin/activate` file, and that way
   there is no need to keep using the complete `./venv/bin` path every time.
   In this guide we use the complete path for clarity.
   ```
   /opt/omniwatch/bin/python -m pip install .
   ```
   Alternatively, use the following line to install Omniwatch with the
   optional dependencies for the `omniwatch-query` tool.
   ```
   /opt/omniwatch/bin/python -m pip install .[query]
   ```

3. Launch the node monitor with `gunicorn` in the virtual environment.
   ```
   /opt/omniwatch/bin/gunicorn -b 0.0.0.0:8000 "omniwatch.node_monitoring:app"
   ```
   This will read the default configuration file that is installed in the
   package. To use a different configuration file, use the `OMNIWATCH_CONFIG`
   environment variable.
   ```
   OMNIWATCH_CONFIG=/path/to/config/file /opt/omniwatch/bin/gunicorn -b 0.0.0.0:8000 "omniwatch.node_monitoring:app"
   ```
   And to launch standalone scripts:
   ```
   /opt/omniwatch/bin/omniwatch-util # Utility to help run in user mode in SLURM cluster
   /opt/omniwatch/bin/omniwatch-annotate # Annotate executions in SLURM jobs
   /opt/omniwatch/bin/omniwatch-query # Query
   ```

For system level installation, the virtual environment for Omniwatch can be
created under `/opt/omniwatch` as described in the Ansible example below. The
service file will then need to have the following line:
```
ExecStart=/opt/omniwatch/bin/gunicorn -b 0.0.0.0:8000 "omniwatch.node_monitoring:app"
```
With the configuration file defined in a `Environment` line.

### Prometheus installation and configuration (server)

```
global:
  scrape_interval: 30s
  evaluation_interval: 5s

alerting:
  alertmanagers:
    - static_configs:
        - targets:

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "omniwatch"
    scrape_interval: 30s
    scrape_timeout: 5s
    static_configs:
      - targets:
        - compute-00:8000
        - compute-01:8000
        - compute-02:8000
        - compute-03:8000
```

### Ansible example



```
- hosts: all
  vars:
    - omniwatch_url: git@github.com:AMDResearch/omniwatch.git
    - omniwatch_tmp: /tmp/omniwatch-install
    - omniwatch_dir: /opt/omniwatch

  tasks:
    - name: Fetch copy of omniwatch repository for installation
      git:
        repo: "{{ omniwatch_url }}"
        dest: "{{ omniwatch_tmp }}"
        version: jorda/python-package
        single_branch: true

    - name: Install omniwatch in virtual environment
      pip:
        name: "{{ omniwatch_tmp }}[query]"
        virtualenv: "{{ omniwatch_dir }}"
        virtualenv_command: /usr/bin/python3 -m venv

    - name: Create configuration directory
      file:
        path: /etc/omniwatch
        state: directory
        mode: "0755"

    - name: Copy configuration file
      copy:
        remote_src: true
        src: "{{ omniwatch_tmp }}/omniwatch/config/omniwatch.default"
        dest: /etc/omniwatch/config
        mode: "0644"

    - name: Copy service file
      copy:
        remote_src: true
        src: "{{ omniwatch_tmp }}/omniwatch.service"
        dest: /etc/systemd/system
        mode: "0644"

    - name: Enable service
      service:
        name: omniwatch
        enabled: yes
        state: started

    - name: Delete temporary installation files
      file:
        path: "{{ omniwatch_tmp }}"
        state: absent
```

---

## User-mode execution with SLURM

### Local docker environment

