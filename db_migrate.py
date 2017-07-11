#!flask/bin/python

# import logging
# logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

from rewrite import app, db
from citext import CIText
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

from rewrite import database

Migrate(app, db, compare_type=True)
manager = Manager(app)

# Unfortuntely, this couldn't be hooked into the `db upgrade` command, because it appears the changes to the DB
# are not accessible from the flask sqlalchemy context, even when python is exiting.
# I'm assuming it's because the changes are committed during exit, apparently.
@manager.command
def install_triggers():
	'''
	Install versioning triggers on tables
	'''
	print("Installing triggers")

# This is also true for my indexes, since they use postgres specific extensions.
@manager.command
def install_tgm_idx():
	'''
	Install trigram search indices on tables
	'''
	print("Installing trigram indices")
# This is also true for my indexes, since they use postgres specific extensions.
@manager.command
def install_enum():
	'''
	Install enum type in db
	'''
	print("Installing enum indices")
	db.engine.begin()
	conn = db.engine.connect()

	print("Done")

manager.add_command('db', MigrateCommand)



if __name__ == '__main__':
	print("Running migrator!")
	manager.run()

