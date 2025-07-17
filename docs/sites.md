# Site-Specific Instructions

```eval_rst
.. toctree::
   :glob:
   :maxdepth: 4
```

## ORNL

This section provides instructions for running user-mode Omnistat on ORNL's
Frontier supercomputer with pre-installed versions from AMD Research.

**Prerequisites**:
- User account on Frontier
- Familiarity with SLURM job submission

### Running jobs on Frontier

Omnistat is preinstalled on Frontier so users only need to setup their module environment appropriately and add
several commands to their SLURM job scripts.

The following video demonstrates a complete Omnistat workflow on Frontier
using an interactive 2-node job. You'll see how to: load the Omnistat module
and initialize data collection, monitor system metrics during application
execution, stop data collection, and generate a performance report.

<video width="640" controls>
  <source src="https://github.com/user-attachments/assets/cc574241-0c3e-4cc2-8f7c-fadaa6e6c0c1" type="video/mp4">
</video>
<p></p>

The version of Omnistat installed on Frontier also includes a convenience wrapper
for teams running their own Python stack who may wish to avoid any pollution
with the application's Python environment. A SLURM job script example highlighting
use of the wrapper utility before and after executing a GPU application is highlighted below:

```eval_rst
.. code-block:: bash
   :caption: Example Frontier SLURM job using wrapper, highlighting changes needed to run Omnistat
   :emphasize-lines: 9-11,17-19

   #!/bin/bash
   #SBATCH -A <project_id>
   #SBATCH -J omnistat
   #SBATCH -N 2
   #SBATCH -t 01:00:00
   #SBATCH -S 0

   # Setup and launch Omnistat (wrapper version)
   ml use /autofs/nccs-svm1_sw/crusher/amdsw/modules
   ml omnistat-wrapper
   ${OMNISTAT_WRAPPER} usermode --start --interval 1.0

   # Your GPU application here
   srun ./your_application

   # Tear down Omnistat
   ${OMNISTAT_WRAPPER} usermode --stopexporters
   ${OMNISTAT_WRAPPER} query --interval 1.0 --job ${SLURM_JOB_ID} --pdf omnistat.${SLURM_JOB_ID}.pdf
   ${OMNISTAT_WRAPPER} usermode --stopserver
```

### Storage

By default, Omnistat databases are stored in Lustre, under the
`/lustre/orion/$(SLURM_JOB_ACCOUNT)/scratch/$(USER)/omnistat/$(SLURM_JOB_ID)`
directory. It's possible to override the default path using the
`OMNISTAT_VICTORIA_DATADIR` environment variable as highlighted in the following example.

```eval_rst
.. code-block:: bash
   :caption: Storing data under /tmp and copying it after running
   :emphasize-lines: 11,21

   #!/bin/bash
   #SBATCH -A <project_id>
   #SBATCH -J omnistat
   #SBATCH -N 2
   #SBATCH -t 01:00:00
   #SBATCH -S 0

   # Setup and launch Omnistat (wrapper version)
   ml use /autofs/nccs-svm1_sw/crusher/amdsw/modules
   ml omnistat-wrapper
   export OMNISTAT_VICTORIA_DATADIR=/tmp/omnistat/${SLURM_JOB_ID}
   ${OMNISTAT_WRAPPER} usermode --start --interval 1.0

   # Your GPU application here
   srun ./your_application

   # Tear down Omnistat
   ${OMNISTAT_WRAPPER} usermode --stopexporters
   ${OMNISTAT_WRAPPER} query --interval 1.0 --job ${SLURM_JOB_ID} --pdf omnistat.${SLURM_JOB_ID}.pdf
   ${OMNISTAT_WRAPPER} usermode --stopserver
   mv /tmp/omnistat/${SLURM_JOB_ID} data_omnistat.${SLURM_JOB_ID}
```

```{note}
Omnistat databases require `flock` support, which is available in Lustre and
local filesystems like `/tmp`. Data can't be stored directly under Frontier's
`$HOME`, but it can be moved there after running.
```

### Data Analysis

After job completion, transfer the archived Omnistat data to your local machine
for analysis using the Docker environment described in the [user-mode
guide](installation/user-mode.md#exploring-results-locally).
