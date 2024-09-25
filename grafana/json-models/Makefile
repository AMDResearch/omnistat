all: standalone-global.json standalone-node.json

standalone-global.json: rms-global.json
	./make-standalone -i $< > $@

standalone-node.json: rms-node.json
	./make-standalone -i $< > $@

