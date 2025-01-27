FROM victoriametrics/victoria-metrics

RUN apk update && apk add curl su-exec

COPY vmloader.sh /usr/local/bin/vmloader
COPY entrypoint.sh /usr/local/bin/entrypoint

RUN chmod 0777 /usr/local/bin/vmloader

ENTRYPOINT ["/usr/local/bin/entrypoint"]
