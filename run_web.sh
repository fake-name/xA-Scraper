#!/usr/bin/env bash

# Halt on errors.
set -e

# # This is just a very minimal script that starts the scraper.
# echo "Updating local git repo"
# git fetch --all
# git pull


# echo "Available branches:"
# git --no-pager branch -a | cat


# echo "Current release:"
# git --no-pager log -1 | cat

if [ -d "venv" ]
then
	echo "Venv exists. Activating!"
	source venv/bin/activate
else
	echo "No Venv! Checking dependencies are installed."
	sudo apt-get install build-essential -y
	sudo apt-get install libxml2 libxslt1-dev python3-dev libz-dev -y

	echo "Creating venv."

	python3 -m venv --without-pip venv
	wget https://bootstrap.pypa.io/get-pip.py
	./venv/bin/python3 get-pip.py
	rm get-pip.py
	source venv/bin/activate
	./venv/bin/pip install requests
fi;

echo "Checking dependencies are up-to-date."
./venv/bin/pip install --upgrade -r requirements.txt

echo "Checking database is up-to-date."
python3 db_migrate.py db upgrade
echo "Checking namelist for duplicates."
python3 -m manage name-clean
echo "Launching executable."
python3 ./main_web.py
