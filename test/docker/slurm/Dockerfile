FROM rocm/dev-ubuntu-22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        bind9-dnsutils \
        munge \
        openssh-server \
        prometheus \
        python3-venv \
        slurm-client \
        slurmctld \
        slurmd \
        vim \
        wget

RUN mkdir /var/spool/slurmctld && \
    mkdir /var/spool/slurmd && \
    chown slurm.slurm /var/spool/slurm*

COPY docker/slurm/slurm.conf /etc/slurm/

COPY docker/slurm/docker-entrypoint.sh /usr/local/bin/entrypoint

ENTRYPOINT ["/usr/local/bin/entrypoint"]
