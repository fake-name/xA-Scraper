## -*- coding: utf-8 -*-
<!DOCTYPE html>


<%startTime = time.time()%>
<%namespace name="sideBar" file="genNavBar.mako"/>

<html>
<head>
	<meta charset="utf-8">

	<title>WAT WAT IN THE ERRORS</title>
	<link rel="stylesheet" href="style.css">


</head>

<%!
# Module level!
import time
import datetime
from babel.dates import format_timedelta
import os.path

from settings import settings

%>



<%

# ------------------------------------------------------------------------
# This is the top of the main
# page generation section.
# Execution begins here
# ------------------------------------------------------------------------

cur = sqlCon.cursor()



if "db" in request.params:
	if request.params["db"] == "da":
		showInMT = False

	elif request.params["db"] == "fa":
		showNotInMT = False


# nt.dirNameProxy = nt.()  # dirListFunc() is provided by the resource



# mtMonRunLast = format_timedelta(delta, locale='en_US')

# for item in nt.dirNameProxy:
# 	print item
contentSources = {}
for key in settings["artSites"]:
	contentSources[settings[key]["shortName"]] = settings[key]

print(contentSources)

%>

<body>

<div>

	${sideBar.getSideBar(sqlCon)}
	<div class="maindiv">

		<div class="subdiv buMonId" style="padding: 5px;">
			<h1>Errored pages</h1>
			<div class="" style="white-space:nowrap; display: inline-block;">
				Specific Scraper
				<ul style="width: 100px;">
					<li> <a href="errLists?db=da">Deviant Art</a></li>
					<li> <a href="errLists?db=fa">Fur Affinity</a></li>
					<li> <a href="errLists?db=hf">Hentai Foundry</a></li>
					<li> <a href="errLists?db=px">Pixiv</a></li>
					<li> <a href="errLists">All</a></li>

				</ul>
			</div>
			<hr>
			<%
			itemKeys = list(contentSources.keys())
			itemKeys.sort()
			%>
			% if "db" in request.params and request.params["db"] in contentSources:
				${genSourceErrorTable(contentSources[request.params["db"]]["dlDirName"], contentSources[request.params["db"]]["shortName"], lim=None)}
			% else:
				<h2>Invalid table name!</h2>
			% endif
			% if not "db" in request.params:
				% for key in itemKeys:
					${genSourceErrorTable(contentSources[key]["dlDirName"], contentSources[key]["shortName"], lim=50)}
				% endfor
			% endif
		</div>

	</div>
<div>


<%def name="genSourceErrorTable(niceName, tableName, lim=None)">
	<div>
		<div style="margin-top: 10px;">
			<h2>${niceName}</h2>
		</div>
		<table border="1px">
			<tr>
				<th class="padded" width="100">Artist</th>
				<th class="padded" width="600">Source page URL</th>
				<th class="padded" width="200">Time</th>
			</tr>
			<%
				if not lim:
					lim = None # Get all the rows
				cur.execute('SELECT * FROM %s WHERE siteName=%%s ORDER BY retreivalTime DESC LIMIT %%s;' % settings["dbConf"]["erroredPagesDb"], (tableName, lim))
				errLinks = cur.fetchall()

			%>

			% for uid, siteName, aName, url, timestamp in errLinks:
				<tr>
					<td class="padded">${aName.title()}</td>
					<td class="padded"><a href='${url}'>${url}</a></td>
					<td class="padded">${timestamp}</td>


				</tr>
			% endfor

		</table>
	</div>
</%def>



<%
stopTime = time.time()
timeDelta = stopTime - startTime
%>

<p>This page rendered in ${timeDelta} seconds.</p>

</body>
</html>