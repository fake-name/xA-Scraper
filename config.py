


import os
import sys
import hashlib
import datetime

import string
import random
random.seed()

from settings import SQLALCHEMY_DATABASE_URI  as C_SQLALCHEMY_DATABASE_URI

if len(sys.argv) > 1 and "debug" in sys.argv:
	SQLALCHEMY_ECHO = True



basedir = os.path.abspath(os.path.dirname(__file__))

def get_random(chars):
	rand = [random.choice(string.ascii_letters) for x in range(chars)]
	rand = "".join(rand)
	return rand


class BaseConfig(object):


	SQLALCHEMY_DATABASE_URI = C_SQLALCHEMY_DATABASE_URI
	SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')

	CSRF_ENABLED     = True
	WTF_CSRF_ENABLED = True


	# administrator list
	ADMINS = ['you@example.com']

	# slow database query threshold (in seconds)
	DATABASE_QUERY_TIMEOUT = 0.5

	SEND_FILE_MAX_AGE_DEFAULT = 60*60*12

	# pagination
	POSTS_PER_PAGE = 250

	SQLALCHEMY_TRACK_MODIFICATIONS = False


	# flask-assets
	# ------------
	ASSETS_DEST = 'xascraper/static'

	# The WTF protection doesn't have to persist across
	# execution sessions, since that'll break any
	# active sessions anyways. Therefore, just generate
	# them randomly at each start.
	SECRET_KEY             = get_random(20)
	WTF_CSRF_SECRET_KEY    = get_random(20)

