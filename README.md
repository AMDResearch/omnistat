# Installation of Pre-requisites

```bash
python3 -m pip install -r requirements.txt
```

# To Run as Standalone - Python
```bash
python3 node_monitoring.py [config_file_path]
```
# To Run as Standalone - Executable
```bash
./dist/omniwatch [config_file_path]
```


# To Run as a Service
```bash
sudo cp omniwatch.service /etc/systemd/system/
sudo enable omniwatch
sudo start omniwatch
```


