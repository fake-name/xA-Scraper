
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


# from app import lm



# @lm.user_loader
# def load_user(id):
# 	return Users.query.get(int(id))

# % for key in keys:
# 	<%

# 	cur.execute('SELECT COUNT(*) FROM errored_pages WHERE siteName=%s;', (key, ))
# 	errs = cur.fetchone()[0]

# 	cur.execute('SELECT COUNT(*) FROM retrieved_pages WHERE siteName=%s;', (key, ))
# 	succeed = cur.fetchone()[0]

# 	%>


def get_source_list():

	contentSources = {}
	for key in settings.keys():
		if not isinstance(settings[key], dict):
			continue

		if 'user-url' in settings[key]:
			contentSources[key] = settings[key]


	targets = db.session.query(database.ScrapeTargets).all()

	return contentSources


def aggregate_table(page=1, count=app.config['POSTS_PER_PAGE'], site_filter=None, artist_filter=None):
	releases = db.session.query(database.ArtItem) \
		.filter(database.ArtItem.state == "complete") \
		.order_by(desc(database.ArtItem.addtime)) \
		.options(joinedload('artist'))     \
		.options(joinedload('files'))      \
		.options(joinedload('tags'))

	if site_filter:
		print("Doing site-filter!")
		subq = db.session.query(database.ScrapeTargets.id) \
			.filter(database.ScrapeTargets.site_name == site_filter)

		releases = releases.filter(database.ArtItem.artist_id.in_(subq))
		print("Query:", releases)

	if artist_filter:
		releases = releases.filter(database.ArtItem.artist_id == artist_filter)


	releases_paginated = releases.paginate(page, count, False)

	return releases_paginated

@app.after_request
def after_request(response):
	for query in get_debug_queries():
		if query.duration >= app.config['DATABASE_QUERY_TIMEOUT']:
			app.logger.warning(
				"SLOW QUERY: %s\nParameters: %s\nDuration: %fs\nContext: %s\n" %
				(query.statement, query.parameters, query.duration,
				 query.context))

	db.session.rollback()
	return response


@app.teardown_appcontext
def shutdown_session(exception=None):
	db.session.remove()


@app.errorhandler(404)
def not_found_error(dummy_error):
	print("404. Wat?")
	return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(dummy_error):
	db.session.rollback()
	print("Internal Error!")
	print(dummy_error)
	print(traceback.format_exc())
	# print("500 error!")
	return render_template('500.html'), 500


def error_page(error_title, error_message):
	return render_template('error.html',
				error_title   = error_title,
				error_message = error_message,
		)





@app.route('/', methods=['GET'])
@app.route('/<int:pagenum>', methods=['GET'])
@app.route('/index', methods=['GET'])
@auth.login_required
def index(pagenum=1):
	source_list = get_source_list()
	release_table = aggregate_table(page=pagenum)

	return render_template('index.html',
						   source_list  = source_list,
						   title        = 'Home',
						   data         = release_table,
						   )





@app.route('/source/by-site/<site_name>/<int:pagenum>', methods=['GET'])
@app.route('/source/by-site/<site_name>/', methods=['GET'])
@app.route('/source/by-site/<site_name>', methods=['GET'])
@auth.login_required
def view_by_site(site_name, pagenum=1):
	if 'page' in request.args and pagenum == 1:
		try:
			pagenum = int(request.args['page'])
		except ValueError:
			return error_page("That's not a number!", "The page number '%s' is not actually a number"
				% (request.args['page'], ))
	print("view_by_site, page:", pagenum)
	valid_sitenanes = [tmp[-1] for tmp in main.JOBS]
	if site_name not in valid_sitenanes:
		return error_page("Invalid site-name!", "The site-name '%s' is not in the "
			"valid site-name list %s" % (site_name, valid_sitenanes))

	# return error_page("Wat!", "Unavailable due to performance issues")

	source_list = get_source_list()
	release_table = aggregate_table(page=pagenum, site_filter=site_name)

	return render_template('index.html',
						   source_list = source_list,
						   title       = 'Home',
						   data        = release_table,
						   )




@app.route('/source/by-artist/<int:artist_id>/<int:pagenum>', methods=['GET'])
@app.route('/source/by-artist/<int:artist_id>/', methods=['GET'])
@app.route('/source/by-artist/<int:artist_id>', methods=['GET'])
@auth.login_required
def view_by_artist(artist_id, pagenum=1):

	source_list = get_source_list()

	print(request.args)
	if 'page' in request.args and pagenum == 1:
		try:
			pagenum = int(request.args['page'])
		except ValueError:
			return error_page("That's not a number!", "The page number '%s' is not actually a number"
				% (request.args['page'], ))

	release_table = aggregate_table(page=pagenum, artist_filter=artist_id, count=5)

	return render_template('single_artist_view.html',
						   source_list = source_list,
						   data        = release_table,
						   )




@app.route('/images/byid/<int:img_id>', methods=['GET'])
@auth.login_required
def fetch_image_fileid(img_id):

	img_row = db.session.query(database.ArtFile) \
		.filter(database.ArtFile.id == img_id)    \
		.scalar()

	if not img_row:
		return not_found_error(None)

	return send_file(os.path.join(settings['dldCtntPath'], img_row.fspath))

