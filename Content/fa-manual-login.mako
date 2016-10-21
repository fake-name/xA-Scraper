## -*- coding: utf-8 -*-
<!DOCTYPE html>

<%!
import time
from settings import settings
import datetime
from pprint import pprint
import requests
import uuid
%>
<%
startTime = time.time()

cur = sqlCon.cursor()


urlLut = {}
contentSources = {}
for key in settings.keys():
	print("Key: ", key)
	if not isinstance(settings[key], dict):
		continue

	if 'user-url' in settings[key]:
		urlLut[key] = settings[key]['user-url']

		contentSources[key] = settings[key]


%>

<html>
<head>
	<meta charset="utf-8">
	<title>WAT WAT IN THE DOWNLOAD</title>
	<link rel="stylesheet" type="text/css" href="/style.css">
	<script type="text/javascript" src="/js/jquery-2.1.0.min.js"></script>
	<script type="text/javascript" src="/js/popupViewer.js"></script>


	<script type="text/javascript">
		$(document).ready(singleImagePopup);
	</script>


</head>

<%namespace name="sideBar" file="genNavBar.mako"/>



<H2>INDEX</H2>

<body>


<div>
	${sideBar.getSideBar(sqlCon)}
	<div class="maindiv">
		<%


		if 'uuid' not in request.session:
			request.session['uuid'] = uuid.uuid1()

			request_sessions[request.session['uuid']] = requests.session()
			r = request_sessions[request.session['uuid']].get('https://www.furaffinity.net/login/')

			request_cookies[request.session['uuid']] = r.cookies['b']

		else:

			print(request_sessions[request.session['uuid']].cookies)


		%>

		<div class="subdiv">
			<div class="contentdiv">
				<div style="margin-top: 10px;">
					<h2>Manual FA login due to captcha douchiness.</h2>
				</div>

				% if 'a' in request_sessions[request.session['uuid']].cookies and 'b' in request_sessions[request.session['uuid']].cookies:
					You appear to have a FA login cookie!
				%else:
					<form method="POST" action="/doFaCaptchaLogin">
						<input type="text" name="username" placeholder="Username" value="${settings['fa']['username']}"><br>
						<input type="password" name="password" placeholder="Password" value="${settings['fa']['password']}"><br>
						<img src="/faCaptchaImage"><br>
						<input type="text" name="captcha" placeholder="Captcha text"><br>
						<button type="submit">Login</button>
					</form>
				% endif

			</div>
		</div>


	</div>
<div>




<%
stopTime = time.time()
timeDelta = stopTime - startTime
%>

<p>This page rendered in ${timeDelta} seconds.</p>

</body>
</html>