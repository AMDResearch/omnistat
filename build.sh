pyinstaller -D -F -n omniwatch --hidden-import prometheus_client --hidden-import flask --exclude-module amdsmi "node_monitoring.py"

