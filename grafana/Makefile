# Makefile to generate dashboard variants.

SOURCE_ALL = $(shell find source/ -name '*.json')
SOURCE_SYSTEM = $(shell find source/ -name '*.json' ! -name 'job*.json')
SOURCE_USER = $(shell find source/ -name '*.json' ! -name 'node*.json')
SOURCE_DOCKER = $(shell find source/ -name '*.json' ! -name 'node*.json')

RMS = $(SOURCE_ALL:source/%=json-models/system/rms-%)
STANDALONE = $(SOURCE_SYSTEM:source/%=json-models/system/standalone-%)
USER = $(SOURCE_USER:source/%=json-models/user/%)
DOCKER = $(SOURCE_USER:source/%=json-models/docker/%)

all: $(RMS) $(STANDALONE) $(USER) $(DOCKER)

json-models/system/rms-%.json: source/%.json
	./scripts/filter-dashboard --input $< \
		--exclude-metrics rocm_throttle_events network_rx_bytes network_tx_bytes \
		--replace-name Source:RMS > $@

json-models/system/standalone-%.json: json-models/system/rms-%.json
	./scripts/filter-dashboard --input $< \
		--exclude-metrics rmsjob_ \
		--exclude-links Job \
		--replace-name RMS:Standalone > $@

json-models/user/global.json: source/global.json
	./scripts/filter-dashboard --input $< \
		--include-title "Job Index" \
		--exclude-links Node \
		--expand-rows \
		--replace-name Source:User > $@

json-models/user/job.json: source/job.json
	./scripts/filter-dashboard --input $< \
		--replace-name Source:User > $@

# Dashboards used in the local docker-based Grafana are the same as the
# user-level dashboards, excluding panels that use node-exporter metrics since
# those are not included in usermode executions.
json-models/docker/%.json: json-models/user/%.json
	./scripts/filter-dashboard --input $< \
		--exclude-metrics node_ > $@
