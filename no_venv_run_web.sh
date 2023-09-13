#!/usr/bin/env bash

# Halt on errors.
set -e

# echo "Checking database is up-to-date."
# python3 db_migrate.py db upgrade
# echo "Checking namelist for duplicates."
# python3 -m manage name-clean
# echo "Launching executable."

while true; do
	python3 ./main_web.py;
	sleep 60;
done;
