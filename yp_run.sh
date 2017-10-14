#!/usr/bin/env bash

# source venv/bin/activate
python3 -m rewrite.modules.yiff_party.yiff_scrape


until python3 -m rewrite.modules.yiff_party.yiff_scrape drain; do
    echo "Server 'python3 -m rewrite.modules.yiff_party.yiff_scrape drain' crashed with exit code $?.  Respawning.." >&2
    sleep 1
done
