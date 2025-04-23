#!/bin/sh
set -e
python /server_setup.py
exec $@
