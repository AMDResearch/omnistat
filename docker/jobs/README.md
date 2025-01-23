## Jobs

This directory is meant to contain Victoria Metrics databases for different
jobs. Databases in this directory are imported into the main Victoria Metrics
database.

Databases are currently only imported when launching the Docker Compose
environment. Each database is imported once. To force reloading all the
databases in this directory, use the `FORCE_RELOAD` environment variable:
```
FORCE_RELOAD=1 docker-compose up -d
```
