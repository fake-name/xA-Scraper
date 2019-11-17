

from flask import render_template

from xascraper import app
from xascraper import auth
from xascraper import db
from xascraper import database

import plugins


@app.route('/watched-names', methods=['GET'])
@auth.login_required
def watched_names():

	watched = db.session.query(database.ScrapeTargets).all()

	watched_sorted = {}
	for row in watched:
		watched_sorted.setdefault(row.site_name, [])
		watched_sorted[row.site_name].append(row)

	# We pre-populate with the active plugin keys.
	# This needs to be maintained for added plugins.
	skeys = [key for key in watched_sorted.keys()]   \
		+ [tmp[-1] for tmp in plugins.JOBS]          \
		+ [tmp[-1] for tmp in plugins.JOBS_DISABLED]
	skeys = list(set(skeys))

	skeys.sort()

	non_editable_keys = ['pat', 'yp', 'px']

	for bad in non_editable_keys:
		if bad in skeys:
			skeys.remove(bad)

	for skey in skeys:
		watched_sorted.setdefault(skey, [])
		watched_sorted[skey].sort(key=lambda r:r.artist_name.lower())

	return render_template('watched-names-editor.html',
							watched_sorted = watched_sorted,
							skeys          = skeys,
						   )
