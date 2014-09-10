## -*- coding: utf-8 -*-
<!DOCTYPE html>

<%!
import time
from settings import settings
import datetime
%>
<%
startTime = time.time()

contentSources = {}
for key in settings["artSites"]:
	contentSources[settings[key]["shortName"]] = settings[key]


cur = sqlCon.cursor()
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
		<div class="subdiv daId">
			<div class="contentdiv">
				${genSourceErrorTable(contentSources["da"]["dlDirName"], "da", lim=50)}

			</div>
		</div>
		<div class="subdiv faId">
			<div class="contentdiv">
				${genSourceErrorTable(contentSources["fa"]["dlDirName"], "fa", lim=50)}


			</div>
		</div>

		<div class="subdiv hfId">
			<div class="contentdiv">
				${genSourceErrorTable(contentSources["hf"]["dlDirName"], "hf", lim=50)}


			</div>
		</div>
		<div class="subdiv pxId">
			<div class="contentdiv">
				${genSourceErrorTable(contentSources["px"]["dlDirName"], "px", lim=50)}


			</div>
		</div>

	</div>
<div>


<%def name="genSourceErrorTable(niceName, siteName, lim=100)">
	<div>
		<div style="margin-top: 10px;">
			<h2>${niceName}</h2>
		</div>
		<table border="1px">
			<tr>
				<th class="padded" width="100px">Artist</th>
				<th class="padded" width="30px">Src</th>
				<th class="padded" width="600px">Image Source Page URL</th>
				<th class="padded" width="150px">Download Time</th>
			</tr>
			<%
				if not lim:
					lim = -1 # Get all the rows
				# artistName, pageUrl, retreivalTime
				cur.execute('SELECT id, siteName, artistName, pageUrl, retreivalTime FROM retrieved_pages WHERE siteName=? ORDER BY retreivalTime DESC LIMIT ?;', (siteName, lim))
				pageLinks = cur.fetchall()
				urlLut = {
					"da" : "http://%s.deviantart.com/",
					"fa" : "http://www.furaffinity.net/user/%s/",
					"hf" : "http://www.hentai-foundry.com/user/%s/profile",
					"px" : "http://www.pixiv.net/member.php?id=%s"
				}
			%>


			% for uid, siteName, aName, url, timestamp in pageLinks:
				<tr>
					<td class="padded" style=" overflow: hidden;">
						<div style="width: 100px;">
							<a href="/source/byartist/${siteName}/${aName}/1">${aName.title()}</a>
						</div>
					</td>
					<td class="padded"><a href="${urlLut[siteName] % aName}">[src]</a></td>
					<td class="padded showTT" imageID="${uid}"><a href='${url}'>${url}</a></td>
					<td class="padded">${str(datetime.datetime.fromtimestamp(timestamp)).split(".")[0]}</td>
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