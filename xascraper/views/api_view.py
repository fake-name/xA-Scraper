
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
from xascraper import app
from xascraper import auth
from xascraper import db
from xascraper import database

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
	assert 'mode'       in params
	assert params['mode']   == 'change-artist-name', "Wrong Mode?"

	assert 'id'        in params
	assert 'aName'     in params

	assert params['id'],                  "Artist id cannot be empty"
	assert params['aName'].strip(),                  "Artist name cannot be empty"

	try:
		aid = int(params['id'])
	except ValueError:
		assert False, "Artist id not an integer?"

	have_item = db.session.query(database.ScrapeTargets)                      \
		.filter(database.ScrapeTargets.id == params['id'])         \
		.scalar()

	assert have_item, "No artist for ID?"
	old_name = have_item.artist_name
	new_name = params['aName'].strip()
	have_item.artist_name = new_name
	db.session.commit()


	return getResponse("Updated artist from name '%s' to name '%s' for site '%s'." %
		(old_name, new_name, have_item.site_name),
		error=False)

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

	allowed_modes = [tmp[-1] for tmp in main.JOBS] + [tmp[-1] for tmp in main.JOBS_DISABLED]
	assert params['site'] in allowed_modes, "Site %s not in available modes: %s" % (params['site'], allowed_modes)


	params['artistName'] = params['artistName'].strip()

	have_item = db.session.query(database.ScrapeTargets)                      \
		.filter(database.ScrapeTargets.site_name == params['site'])         \
		.filter(database.ScrapeTargets.artist_name.ilike(params['artistName'])) \
		.scalar()

	if have_item:
		db.session.commit()
		return getResponse("Error: Artist '%s' for site '%s' already fetched!" %
			(params['site'], params['artistName']),
			error=True)

	new = database.ScrapeTargets(
		site_name   = params['site'],
		artist_name = params['artistName'],
		)

	db.session.add(new)
	db.session.commit()

	return getResponse("Added artist '%s' for site '%s'." %
		(params['site'], params['artistName']),
		error=False)




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
		ret = DISPATCH_MAP[params['mode']](params)
		print("API Response:", ret)
		return ret
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
