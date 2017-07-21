import os
import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_debugtoolbar import DebugToolbarExtension
from flask_httpauth import HTTPBasicAuth
import datetime

import urllib.parse

from . import database

app = Flask(__name__, static_folder='static', static_url_path='/static')

import sys
if "debug" in sys.argv:
	print("Flask running in debug mode!")
	app.debug = True

app.config.from_object('config.BaseConfig')
app.jinja_env.add_extension('jinja2.ext.do')
auth = HTTPBasicAuth()
db = SQLAlchemy(app)


users = {"herp" : "wattttttt"}

@auth.get_password
def get_pw(username):
	if username in users:
		return users.get(username)
	return None



if "debug" in sys.argv:
	print("Installing debug toolbar!")
	toolbar = DebugToolbarExtension(app)


"""
URLify Extension for Python-Markdown
=====================================

Converts URLs in the markdown text to clickable links.
"""

import re
from markdown.preprocessors import Preprocessor
from markdown.extensions import Extension

urlfinder = re.compile(r'((([A-Za-z]{3,9}:(?:\/\/)?)(?:[\-;:&=\+\$,\w]+@)?[A-Za-z0-9\.\-]+(:[0-9]+)?|'
					   r'(?:www\.|[\-;:&=\+\$,\w]+@)[A-Za-z0-9\.\-]+)((?:/[\+~%/\.\w\-_]*)?\??'
					   r'(?:[\-\+=&;%@\.\w_]*)#?(?:[\.!/\\\w]*))?)')


class URLify(Preprocessor):
	def run(self, lines):
		return [urlfinder.sub(r'<\1>', line) for line in lines]


class URLifyExtension(Extension):
	def extendMarkdown(self, md, md_globals):
		md.preprocessors.add('urlify', URLify(md), '_end')

from flask.ext.markdown import Markdown
Markdown(app, safe_mode='escape', extensions=[URLifyExtension()])

# ========================================================


from . import views
from . import database

CACHE_SIZE = 5000
userIdCache = {}
tlGroupIdCache = {}


def format_js_date(din):
	return din.strftime("%Y/%m/%d %H:%M")

def date_now():
	return datetime.datetime.today().strftime("%Y/%M/%d %H:%M")

def aentry_to_nice_name(site_name, aname):
	if site_name == 'pat':
		meta = json.loads(aname)
		return meta[1][0].title()
	else:
		return aname.title()

def release_entry_to_nice_url(site_name, releasemeta):
	if site_name == 'sf':
		meta = json.loads(releasemeta)
		return meta['url']
	else:
		return releasemeta

def ago(then):
	now = datetime.datetime.now()
	delta = now - then

	d = delta.days
	h, s = divmod(delta.seconds, 3600)
	m, s = divmod(s, 60)
	labels = ['d', 'h', 'm', 's']
	dhms = ['%s %s' % (i, lbl) for i, lbl in zip([d, h, m, s], labels)]
	for start in range(len(dhms)):
		if not dhms[start].startswith('0'):
			break
	for end in range(len(dhms)-1, -1, -1):
		if not dhms[end].startswith('0'):
			break
	return ', '.join(dhms[start:end+1])

def terse_ago(then):
	print(then)
	now = datetime.datetime.now()
	if then > now:
		return "Wat?"
	delta = now - then

	d = delta.days
	h, s = divmod(delta.seconds, 3600)
	m, s = divmod(s, 60)
	labels = ['d', 'h', 'm', 's']
	dhms = ['%s %s' % (i, lbl) for i, lbl in zip([d, h, m, s], labels)]
	for start in range(len(dhms)):
		if not dhms[start].startswith('0'):
			break
	# for end in range(len(dhms)-1, -1, -1):
	# 	if not dhms[end].startswith('0'):
	# 		break
	if d > 0:
		dhms = dhms[:2]
	elif h > 0:
		dhms = dhms[1:3]
	else:
		dhms = dhms[2:]
	return ', '.join(dhms)

@app.context_processor
def utility_processor():
	return dict(
			release_entry_to_nice_url  = release_entry_to_nice_url,
			aentry_to_nice_name        = aentry_to_nice_name,
			format_js_date             = format_js_date,
			date_now                   = date_now,
			terse_ago                  = terse_ago,
			ago                        = ago,
			min                        = min,
			max                        = max,
			)



