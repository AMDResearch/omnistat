## Test Environment with SLURM

Test environment based on a containerized SLURM cluster.

The provided Docker Compose environment creates a containerized SLURM cluster,
and installs the working copy of Omnistat in the container at run time. It is
meant to help make development easier, and enables testing without relying on
access to real clusters.

### Deploy

From the root directory of the project:

1. Start containers.
   ```
   docker compose -f test/docker/slurm/compose.yaml up -d
   ```

2. Submit a SLURM job.
   ```
   docker exec slurm-controller-1 bash -c "cd /jobs; sbatch --wrap='sleep 10'"
   ```

3. Run tests with `pytest`, or check Prometheus data, which is exposed to the
   host and can be accessed at [http://localhost:9090](http://localhost:9090).

4. Stop containers.
   ```
   docker compose -f test/docker/slurm/compose.yaml down
   ```
