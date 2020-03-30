#!/usr/bin/env bash

echo "Interrupting mvbs process..."
python ~/app/mvbs.py stop

echo "Forwarding /dev/serial0 to uCenter on port 2020..."
sudo socat tcp-listen:2020,reuseaddr /dev/serial0,b115200,raw,echo=0

echo "Disconnected"
