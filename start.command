#!/bin/bash
cd "$(dirname "$0")"
nohup /usr/bin/python3 main.py > /tmp/mac-proximity-unlock.log 2>&1 &
