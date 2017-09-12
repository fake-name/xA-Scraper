
import os.path
import traceback

from flask import redirect
from flask import url_for
from flask import request
from flask import g
from flask import jsonify
from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from rewrite import app
from rewrite import auth
from rewrite import db
from rewrite import database

import main
from settings import settings




def getResponse(message, error=False, shouldReload=True):
	ret = {
		'error'   : error,
		'message' : message,
		'reload'  : shouldReload,
	}
	return ret


def change_artist_name(params):
	# ImmutableMultiDict([('mode', 'change-artist-name'), ('id', '1395'), ('aName', 'bor')])


	return getResponse("Not implemented yet", error=True)

	# return getResponse("Succeeded", error=False)

def add_artist_name(params):
	# ImmutableMultiDict([('artistName', ''), ('target', 'addName'), ('site', 'as'), ('add', 'True'), ('mode', 'add-artist-name')])

	assert 'artistName' in params
	assert 'target'     in params
	assert 'site'       in params
	assert 'add'        in params
	assert 'mode'       in params
	assert params['artistName'],                  "Artist name cannot be empty"
	assert params['target'] == 'addName',         "Wrong add-artist name"
	assert params['add']    == 'True',            "Wrong add-artist name"
	assert params['mode']   == 'add-artist-name', "Wrong add-artist name"

	allowed_modes = [tmp[-1] for tmp in main.JOBS]
	assert params['site'] in allowed_modes, "Site %s not in available modes: %s" % (params['site'], allowed_modes)

	return getResponse("Succeeded", error=False)




DISPATCH_MAP = {
	'change-artist-name' : change_artist_name,
	'add-artist-name'    : add_artist_name,
}

def handle_api(params):
	print("API Call!")
	print(params)

	if not 'mode' in params:
		return getResponse(message="No mode parameter!", error=True)

	if params['mode'] not in DISPATCH_MAP:
		return getResponse(message="Unknown mode parameter!", error=True)

	try:
		return DISPATCH_MAP[params['mode']](params)
	except AssertionError as e:
		traceback.print_exc()
		return getResponse("Error processing API request: '%s'!" % e, error=True)







@app.route('/api', methods=['POST'])
@auth.login_required
def api():
	ret = handle_api(request.form)
	resp = jsonify(ret)
	resp.status_code = 200
	resp.mimetype="application/json"
	return resp

	# watched = db.session.query(database.ScrapeTargets).all()

	# watched_sorted = {}
	# for row in watched:
	# 	watched_sorted.setdefault(row.site_name, [])
	# 	watched_sorted[row.site_name].append(row)

	# skeys = [key for key in watched_sorted.keys()]
	# skeys.sort()

	# for skey in skeys:
	# 	watched_sorted[skey].sort(key=lambda r:r.artist_name.lower())

	# return render_template('watched-names-editor.html',
	# 						watched_sorted = watched_sorted,
	# 						skeys          = skeys,
	# 					   )
