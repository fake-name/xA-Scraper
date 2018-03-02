#!/usr/bin/env bash

# source venv/bin/activate

# python3 -m rewrite.modules.yiff_party.yiff_scrape drain
# python3 -m rewrite.modules.yiff_party.yiff_scrape no_namelist
python3 -m rewrite.modules.yiff_party.yiff_scrape


while true;
do
    python3 -m rewrite.modules.yiff_party.yiff_scrape drain
    echo "Server 'python3 -m rewrite.modules.yiff_party.yiff_scrape drain' crashed with exit code $?.  Respawning.." >&2
    sleep 1
done;
