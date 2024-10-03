# Makefile to generate dashboard variants.

SOURCE_ALL = $(shell find source/ -name '*.json')
SOURCE_SYSTEM = $(shell find source/ -name '*.json' ! -name 'job*.json')

RMS = $(SOURCE_ALL:source/%=json-models/rms-%)
STANDALONE = $(SOURCE_SYSTEM:source/%=json-models/standalone-%)

all: $(RMS) $(STANDALONE)

json-models/rms-%.json: source/%.json
	./scripts/filter-dashboard --input $< \
		--exclude-metrics rocm_throttle_events \
		--replace-name Source:RMS > $@

json-models/standalone-%.json: json-models/rms-%.json
	./scripts/filter-dashboard --input $< \
		--exclude-metrics rmsjob_ \
		--exclude-links Job \
		--replace-name RMS:Standalone > $@
