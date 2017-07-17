## -*- coding: utf-8 -*-
<!DOCTYPE html>

<%!
import time
from settings import settings

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
		$(document).ready(multiImagePopup);
	</script>



</head>

<%namespace name="sideBar" file="genNavBar.mako"/>

<%

shortnames = contentSources.keys()
print(shortnames)
print(siteSource)
%>


<H2>INDEX</H2>

<body>

% if siteSource in shortnames:
	<%

		niceName = contentSources[siteSource]["dlDirName"]
		print(shortnames)
		# artistName, pageUrl, retreivalTime
		cur.execute('SELECT distinct(artistName) FROM retrieved_pages WHERE siteName=%s;', (siteSource, ))
		artistName = cur.fetchall()
		artistName = [link[0] for link in artistName]
		artistName.sort()

	%>

	<div>
		${sideBar.getSideBar(sqlCon)}
		<div class="maindiv">
			<div class="subdiv mtMainId">
				<div class="contentdiv">

					<div style="margin-top: 10px;">
					<h2>${niceName}</h2>
					</div>
					<table border="1px">
						<tr>
							<th class="padded" width="950">Artist</th>
							<th class="padded" width="50">Items</th>
						</tr>


						% for aName in artistName:
							<tr>
								<%

									cur.execute('SELECT count(pageUrl) FROM retrieved_pages WHERE siteName=%s AND artistName=%s;', (siteSource, aName))
									itemCount = cur.fetchall()
									count = 0
								%>

								<td class="padded showTT" artistID="${aName}"><a href='/source/byartist/${siteSource}/${aName}/1'>${aName}</a></td>
								<td class="padded">${itemCount[0][0]}</td>


							</tr>
						% endfor

					</table>

				</div>
			</div>
		</div>
	<div>

% else:
	<h3> Invalid SiteSource!</h3>
% endif



<%
stopTime = time.time()
timeDelta = stopTime - startTime
%>

<p>This page rendered in ${timeDelta} seconds.</p>

</body>
</html>