
#pylint: disable-msg=F0401, W0142

from pyramid.config import Configurator
from pyramid.response import Response, FileResponse
from pyramid.exceptions import NotFound
from pyramid.httpexceptions import HTTPFound
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.session import SignedCookieSessionFactory


import pyramid.security as pys
import apiHandler
import webFunctions

import mako.exceptions
from mako.lookup import TemplateLookup


import os.path
users = {"herp" : "wattttttt"}


def userCheck(userid, dummy_request):
	if userid in users:
		return True
	else:
		return False

import logging
import traceback

from settings import settings
import rewrite.database




request_sessions = {}
request_cookies = {}


class PageResource(object):


	db = rewrite.database

	log = logging.getLogger("Main.WebSrv")

	def __init__(self):
		self.base_directory = settings["webCtntPath"]
		self.lookupEngine = TemplateLookup(directories=[self.base_directory], module_directory='./ctntCache')

		self.apiInterface = apiHandler.ApiInterface()


	def getResponse(self, reqPath):

		with open(reqPath, "rb") as fp:
			ret = Response(body=fp.read())
			if reqPath.endswith(".js"):
				ret.content_type = "text/javascript"
			if reqPath.endswith(".css"):
				ret.content_type = "text/css"
			if reqPath.endswith(".ico"):
				ret.content_type = "image/x-icon"

			self.log.info("Request for URL %s, inferred MIME type %s", reqPath, ret.content_type)
			return ret

	def getPage(self, request):
		redir = self.checkAuth(request)
		if redir:
			return redir
		else:
			return self.getPageNoAuth(request)


	def getPageNoAuth(self, request):

		self.log.info("Request from %s for path - %s!", request.remote_addr, request.path)

		reqPath = request.path.lstrip("/")
		if not reqPath:
			reqPath = "index.mako"

		# Check if there is a mako file at the path, and choose that preferentially over other files.
		# Includes adding `.mako` to the path if needed.
		makoPath = reqPath + ".mako"

		absolute_path = os.path.join(self.base_directory, reqPath)
		normalized_path = os.path.normpath(absolute_path)

		mako_absolute_path = os.path.join(self.base_directory, makoPath)
		mako_normalized_path = os.path.normpath(mako_absolute_path)

		if os.path.exists(mako_normalized_path):
			normalized_path = mako_normalized_path
			reqPath = makoPath

		try:
			# Block attempts to access directories outside of the content dir
			if not normalized_path.startswith(self.base_directory):
				raise IOError()

			# Conditionally parse and render mako files.
			if reqPath.endswith(".mako"):
				pgTemplate = self.lookupEngine.get_template(reqPath)
				with self.db.context_sess() as sess:
					pageContent = pgTemplate.render_unicode(request=request, sess=sess, api=self.apiInterface, request_sessions=request_sessions, request_cookies=request_cookies)
				return Response(body=pageContent)
			else:
				absolute_path = os.path.join(self.base_directory, reqPath)
				normalized_path = os.path.normpath(absolute_path)
				return self.getResponse(normalized_path)

		except mako.exceptions.TopLevelLookupException:
			self.log.error("404 Request for page at url: %s", reqPath)
			pgTemplate = self.lookupEngine.get_template("error.mako")
			with self.db.context_sess() as sess:
				pageContent = pgTemplate.render_unicode(request=request, sess=sess, tracebackStr=traceback.format_exc(), error_str="NO PAGE! 404")
			return Response(body=pageContent)
		except:
			self.log.error("Page rendering error! url: %s", reqPath)
			self.log.error(traceback.format_exc())
			pgTemplate = self.lookupEngine.get_template("error.mako")
			with self.db.context_sess() as sess:
				pageContent = pgTemplate.render_unicode(request=request, sess=sess, tracebackStr=traceback.format_exc(), error_str="EXCEPTION! WAT?")
			return Response(body=pageContent)

	def checkAuth(self, request):
		userid = pys.authenticated_userid(request)
		if userid is None:
			self.log.warn("No userID found for request to '%s'. Redirecting to login.", request.path)
			return HTTPFound(location=request.route_url('login'))

	def getImagePathFromID(self, imageID):
		cur = self.conn.cursor()

		ret = cur.execute("SELECT (downloadPath) FROM retrieved_pages WHERE id=%s;", (imageID, ))
		rets = cur.fetchall()
		if not rets:
			raise ValueError("How did an invalid key get queried for?")
		pathS = rets[0][0]
		print("PathS: ", pathS)
		if not settings["dldCtntPath"] in pathS:
			pathS = os.path.join(settings["dldCtntPath"], pathS)
		return pathS

	def getImagePathOffsetName(self, offset, name):
		cur = self.conn.cursor()
		ret = cur.execute("SELECT count(downloadPath) FROM retrieved_pages WHERE artistName=%s;", (name,))
		maxItems = cur.fetchall()[0][0]

		offset = int(offset)
		while offset > maxItems: # Clamp to the valid range, modulo so it loops
			offset -= maxItems

		ret = cur.execute("SELECT (downloadPath) FROM retrieved_pages WHERE artistName=%s LIMIT 1 OFFSET %s;", (name, offset))
		rets = cur.fetchall()
		if not rets:
			raise ValueError("How did an invalid key get queried for?")

		pathS = rets[0][0]
		if not settings["dldCtntPath"] in pathS:
			pathS = os.path.join(settings["dldCtntPath"], pathS)
		return pathS

	def getImageById(self, request):
		redir = self.checkAuth(request)
		if redir:
			return redir

		self.log.info("Request from %s for Image by ID - %s!", request.remote_addr, request.matchdict)
		imagePath = self.getImagePathFromID(request.matchdict["imageID"])
		return FileResponse(imagePath)

	def getImageByArtistOffset(self, request):
		redir = self.checkAuth(request)
		if redir:
			return redir

		self.log.info("Request from %s for Image by artist/offset - %s!", request.remote_addr, request.matchdict)
		imagePath = self.getImagePathOffsetName(request.matchdict["offset"], request.matchdict["artist"])
		return FileResponse(imagePath)


	def getSiteSource(self, request):
		redir = self.checkAuth(request)
		if redir:
			return redir

		siteName   = request.matchdict["siteName"]

		self.log.info("Request from %s for Site Source %s!", request.remote_addr, request.matchdict)
		pgTemplate = self.lookupEngine.get_template("genSiteArtistList.mako")

		with self.db.context_sess() as sess:
			pageContent = pgTemplate.render_unicode(request=request, sess=sess, siteSource=siteName)
		return Response(body=pageContent)


	def getArtistSource(self, request):
		redir = self.checkAuth(request)
		if redir:
			return redir

		siteName   = request.matchdict["siteName"]
		sourceName = request.matchdict["sourceName"]
		pageNumber      = request.matchdict["pageNumber"]

		self.log.info("Request from %s Artist page = %s, %s, %s", request.remote_addr, siteName, sourceName, pageNumber)
		pgTemplate = self.lookupEngine.get_template("genArtistList.mako")
		with self.db.context_sess() as sess:
			pageContent = pgTemplate.render_unicode(request=request, sess=sess, siteSource=siteName, artist=sourceName, pageNumberStr=pageNumber)
		return Response(body=pageContent)



	def getFaCapcha(self, request):
		if 'uuid' not in request.session:
			return HTTPFound(location='/')

		r = request_sessions[request.session['uuid']].get('https://www.furaffinity.net/captcha.jpg')
		resp = Response(body=r.content)
		resp.content_type = 'image/jpeg'

		return resp

	def doFaCaptchaLogin(self, request):
		print(request)
		print(request.method)
		if request.method != "POST":
			return HTTPFound(location='/')
		if 'uuid' not in request.session:
			return HTTPFound(location='/')

		# action:login
		# name:bleh
		# pass:blehhhhh
		# g-recaptcha-response:
		# use_old_captcha:1
		# captcha:qyphba
		# login:Login to FurAffinity

		values = {
			'action'               : 'login',
			'name'                 : request.POST['username'],
			'pass'                 : request.POST['password'],
			'g-recaptcha-response' : "",
			'use_old_captcha'      : 1,
			'captcha'              : request.POST['captcha'],
			'login'                : 'Login to FurAffinity',
		}

		print("Login values:", values)

		r = request_sessions[request.session['uuid']].post('https://www.furaffinity.net/login/', data=values, allow_redirects=False)
		# r = request_sessions[request.session['uuid']].post('https://www.furaffinity.net/login/', data=values)
		# print(r.content)
		print(r)
		print(r.cookies)


		for k, v in r.cookies.iteritems():
			print("Cookie: ", k, v)
		print(r.cookies.get_dict())

		print("---------session----------")
		print(request_sessions[request.session['uuid']].cookies)
		for k, v in request_sessions[request.session['uuid']].cookies.iteritems():
			print("Cookie: ", k, v)
		print(request_sessions[request.session['uuid']].cookies.get_dict())



		# Flush cookies into file.
		wg = webFunctions.WebGetRobust()
		for cookie in request_sessions[request.session['uuid']].cookies:
			wg.addCookie(cookie)
		wg.syncCookiesFromFile()


		return HTTPFound(location='/fa-manual-login')



	def sign_in_out(self, request):
		username = request.POST.get('username')
		password = request.POST.get('password')
		if username:
			self.log.info("Login attempt: u = %s, pass = %s", username, password)
			if username in users and users[username] == password:
				self.log.info("Successful Login!")
				age = 60*60*24*32
				headers = pys.remember(request, username, max_age='%d' % age)

				reqPath = request.path.lstrip("/")

				reqPath = reqPath + ".mako"
				pgTemplate = self.lookupEngine.get_template(reqPath)
				pageContent = pgTemplate.render_unicode(request=request)
				return Response(body=pageContent, headers=headers)

			else:
				self.log.warning("Invalid user. Deleting cookie.")
				headers = pys.forget(request)
		else:
			self.log.warning("No user specified - Deleting cookie.")
			headers = pys.forget(request)

		return HTTPFound(location=request.route_url('login'))


	def getApi(self, request):
		return self.apiInterface.handleApiCall(request)

def buildApp():

	resource = PageResource()

	authn_policy = AuthTktAuthenticationPolicy('lolwattttt', hashalg='sha256', callback=userCheck)
	authz_policy = ACLAuthorizationPolicy()
	session_factory = SignedCookieSessionFactory('LOLWUTTTTTT')


	config = Configurator()

	config.set_authentication_policy(authn_policy)
	config.set_authorization_policy(authz_policy)
	config.set_session_factory(session_factory)

	config.add_route(name='get-fa-captcha-img',      pattern='/faCaptchaImage')
	config.add_view(resource.getFaCapcha,            http_cache=0, route_name='get-fa-captcha-img')

	config.add_route(name='do-fa-captcha-login',     pattern='/doFaCaptchaLogin')
	config.add_view(resource.doFaCaptchaLogin,       http_cache=0, route_name='do-fa-captcha-login')

	config.add_route(name='login',                   pattern='/login')
	config.add_route(name='do_login',                pattern='/login-check')
	config.add_route(name='auth',                    pattern='/login')
	config.add_route(name='root',                    pattern='/')
	config.add_route(name='get-image-by-id',         pattern='/images/byid/{imageID}')
	config.add_route(name='get-image-by-offset',     pattern='/images/byoffset/{artist}/{offset}')
	config.add_route(name='get-site-source',         pattern='/source/bysite/{siteName}')
	config.add_route(name='get-artist-source',       pattern='/source/byartist/{siteName}/{sourceName}/{pageNumber}')
	config.add_route(name='api',                     pattern='/api')
	config.add_route(name='leaf',                    pattern='/*page')

	config.add_view(resource.getPageNoAuth,          http_cache=0, route_name='login')
	config.add_view(resource.sign_in_out,            http_cache=0, route_name='do_login')
	config.add_view(resource.getPage,                http_cache=0, route_name='root')
	config.add_view(resource.getImageById,           http_cache=0, route_name='get-image-by-id')
	config.add_view(resource.getImageByArtistOffset, http_cache=0, route_name='get-image-by-offset')
	config.add_view(resource.getSiteSource,          http_cache=0, route_name='get-site-source')
	config.add_view(resource.getArtistSource,        http_cache=0, route_name='get-artist-source')
	config.add_view(resource.getPage,                http_cache=0, route_name='leaf')
	config.add_view(resource.getApi,                 http_cache=0, route_name='api')
	config.add_view(resource.getPage,                http_cache=0, context=NotFound)



	config.add_view(route_name='auth', match_param='action=in', renderer='string', request_method='POST')
	config.add_view(route_name='auth', match_param='action=out', renderer='string')

	app = config.make_wsgi_app()


	return app


app = buildApp()
