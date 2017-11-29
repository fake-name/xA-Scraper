
from settings import settings
from settings import SQLALCHEMY_DATABASE_URI  as C_SQLALCHEMY_DATABASE_URI


import os
import sys
import hashlib
import datetime

import string
import random
random.seed()

if len(sys.argv) > 1 and "debug" in sys.argv:
	SQLALCHEMY_ECHO = True


REFETCH_INTERVAL = datetime.timedelta(days=7*3)

basedir = os.path.abspath(os.path.dirname(__file__))

def get_random(chars):
	rand = [random.choice(string.ascii_letters) for x in range(chars)]
	rand = "".join(rand)
	return rand


class BaseConfig(object):

	DATABASE_IP            = settings['postgres']["address"]
	DATABASE_DB_NAME       = settings['postgres']["database"]
	DATABASE_USER          = settings['postgres']["username"]
	DATABASE_PASS          = settings['postgres']["password"]


	SQLALCHEMY_DATABASE_URI = C_SQLALCHEMY_DATABASE_URI
	SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')

	CSRF_ENABLED = True
	WTF_CSRF_ENABLED = True


	# administrator list
	ADMINS = ['you@example.com']

	# slow database query threshold (in seconds)
	DATABASE_QUERY_TIMEOUT = 0.5

	SEND_FILE_MAX_AGE_DEFAULT = 60*60*12

	# pagination
	TAGS_PER_PAGE = 50
	GENRES_PER_PAGE = 50
	SERIES_PER_PAGE = 50

	POSTS_PER_PAGE = 250
	MAX_SEARCH_RESULTS = 50

	FEED_ITEMS_PER_PAGE = 150
	SQLALCHEMY_TRACK_MODIFICATIONS = False

	RESOURCE_DIR = settings['webCtntPath']

	# flask-assets
	# ------------
	ASSETS_DEST = 'rewrite/static'

	# The WTF protection doesn't have to persist across
	# execution sessions, since that'll break any
	# active sessions anyways. Therefore, just generate
	# them randomly at each start.
	SECRET_KEY             = get_random(20)
	WTF_CSRF_SECRET_KEY    = get_random(20)

