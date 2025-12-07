#!flask/bin/python

# import logging
# logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

from xascraper import app, db
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import click
from flask_migrate import Migrate

from xascraper import database

migrate = Migrate(app, db, compare_type=True)
# manager = Manager(app)

# manager.add_command('db', MigrateCommand)

# app.cli.add_command(MigrateCommand)


# if __name__ == '__main__':
# 	print("Running migrator!")
# 	manager.run()

