FROM victoriametrics/victoria-metrics

RUN apk update && apk add curl su-exec

COPY load.sh /usr/local/bin/omnistat-load
COPY entrypoint.sh /usr/local/bin/entrypoint

RUN chmod 0777 /usr/local/bin/omnistat-load

ENTRYPOINT ["/usr/local/bin/entrypoint"]
