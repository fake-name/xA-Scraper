
import uuid
import requests
import WebRequest

from flask import make_response
from flask import render_template
from flask import redirect
from flask import url_for
from flask import request
from flask import session

from settings import settings

from xascraper import app
from xascraper import auth

request_sessions = {}
request_cookies = {}

# @app.route('/watched-api', methods=['GET', 'POST'])
# @auth.login_required
# def watched_api():
# 	return None

@app.route('/fa-manual-login', methods=['GET'])
@auth.login_required
def fa_manual_login():

	if ('uuid' in session) and (not session['uuid'] in request_sessions):
		del session['uuid']

	if 'uuid' not in session:
		session['uuid'] = uuid.uuid1()

		request_sessions[session['uuid']] = requests.session()
		r = request_sessions[session['uuid']].get('https://www.furaffinity.net/login/')

		request_cookies[session['uuid']] = r.cookies['b']



	return render_template('fa-manual-login.html',
							request_sessions = request_sessions,
							settings = settings,
						   )


@app.route('/faCaptchaImage', methods=['GET'])
@auth.login_required
def getFaCapcha():
	if 'uuid' not in session:
		return redirect(url_for("index"))

	r = request_sessions[session['uuid']].get('https://www.furaffinity.net/captcha.jpg')
	resp = make_response(r.content)
	resp.headers['Content-Type'] = 'image/jpeg'
	resp.headers['Content-Disposition'] = 'attachment; filename=img.jpg'

	return resp

@app.route('/doFaCaptchaLogin', methods=['GET', 'POST'])
@auth.login_required
def doFaCaptchaLogin():
	print(request)
	print(request.method)
	if request.method != "POST":
		return redirect(url_for("index"))
	if 'uuid' not in session:
		return redirect(url_for("index"))

	# action:login
	# name:bleh
	# pass:blehhhhh
	# g-recaptcha-response:
	# use_old_captcha:1
	# captcha:qyphba
	# login:Login to FurAffinity

	values = {
		'action'               : 'login',
		'name'                 : request.form['username'],
		'pass'                 : request.form['password'],
		'g-recaptcha-response' : "",
		'use_old_captcha'      : 1,
		'captcha'              : request.form['captcha'],
		'login'                : 'Login to FurAffinity',
	}

	print("Login values:", values)

	r = request_sessions[session['uuid']].post('https://www.furaffinity.net/login/', data=values, allow_redirects=False)
	# r = request_sessions[session['uuid']].post('https://www.furaffinity.net/login/', data=values)
	# print(r.content)
	print(r)
	print(r.cookies)


	for k, v in r.cookies.iteritems():
		print("Cookie: ", k, v)
	print(r.cookies.get_dict())

	print("---------session----------")
	print(request_sessions[session['uuid']].cookies)
	for k, v in request_sessions[session['uuid']].cookies.iteritems():
		print("Cookie: ", k, v)
	print(request_sessions[session['uuid']].cookies.get_dict())



	# Flush cookies into file.
	wg = WebRequest.WebGetRobust()
	for cookie in request_sessions[session['uuid']].cookies:
		wg.addCookie(cookie)
	wg._syncCookiesFromFile()


	return redirect(url_for("fa_manual_login"))


	# config.add_route(name='get-fa-captcha-img',      pattern='/faCaptchaImage')
	# config.add_view(resource.getFaCapcha,            http_cache=0, route_name='get-fa-captcha-img')

	# config.add_route(name='do-fa-captcha-login',     pattern='/doFaCaptchaLogin')
	# config.add_view(resource.doFaCaptchaLogin,       http_cache=0, route_name='do-fa-captcha-login')