#!/usr/bin/env bash

# source venv/bin/activate

# python3 -m xascraper.modules.yiff_party.yiff_scrape drain
# python3 -m xascraper.modules.yiff_party.yiff_scrape no_namelist
# python3 -m xascraper.modules.yiff_party.yiff_scrape


while true;
do
    python3 -m xascraper.modules.yiff_party.yiff_scrape local
    echo "Server 'python3 -m xascraper.modules.yiff_party.yiff_scrape drain' crashed with exit code $?.  Respawning in 300 seconds.." >&2
    sleep 300
done;
