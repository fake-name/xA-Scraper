
import os.path
import traceback
from settings import settings

from flask import render_template
from flask import flash
from flask import redirect
from flask import url_for
from flask import request
from flask import g
from flask import send_file
from flask_login import login_user
from flask_login import logout_user
from flask_login import current_user
from flask_login import login_required
from itsdangerous import URLSafeTimedSerializer
from itsdangerous import BadSignature
from flask_sqlalchemy import get_debug_queries
from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from rewrite import app
from rewrite import auth
from rewrite import db
from rewrite import database

import main




@app.route('/watched-names', methods=['GET'])
@auth.login_required
def watched_names():

	watched = db.session.query(database.ScrapeTargets).all()

	watched_sorted = {}
	for row in watched:
		watched_sorted.setdefault(row.site_name, [])
		watched_sorted[row.site_name].append(row)

	skeys = [key for key in watched_sorted.keys()]
	skeys.sort()

	for skey in skeys:
		watched_sorted[skey].sort(key=lambda r:r.artist_name.lower())

	return render_template('watched-names-editor.html',
							watched_sorted = watched_sorted,
							skeys          = skeys,
						   )
