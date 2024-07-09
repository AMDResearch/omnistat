#!/bin/bash

# Default repository and execution path
path=/source/

# Run packaged script When Omnistat is installed as a package
if [[ -f /opt/omnistat/bin/omnistat-rms-env ]]; then
    path=/opt/omnistat/bin/
fi

cd $path && ./omnistat-rms-env
