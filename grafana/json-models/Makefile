# Makefile to generate dashboard variants.

RMS_DASHBOARDS = rms-global.json rms-node.json
STANDALONE_DASHBOARDS = $(RMS_DASHBOARDS:rms-%=standalone-%)

all: $(STANDALONE_DASHBOARDS)

standalone-%.json: rms-%.json
	./filter-dashboard --input $< \
		--exclude-metrics rmsjob_ \
		--exclude-links Job \
		--replace-name rms:standalone > $@
