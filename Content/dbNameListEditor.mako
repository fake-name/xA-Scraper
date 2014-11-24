## -*- coding: utf-8 -*-
<!DOCTYPE html>

<html>
<head>
	<meta charset="utf-8">
	<title>WAT WAT IN THE BATT</title>
	<link rel="stylesheet" href="style.css">

	<script type="text/javascript" src="/js/jquery-2.1.0.min.js"></script>
	<script type="text/javascript">

		function ajaxSuccess(reqData, statusStr, jqXHR)
		{
			console.log("Ajax request succeeded");
			console.log("Content = ", reqData);
			console.log("StatusStr - ", statusStr);
			console.log("jqXHR", jqXHR);
			ctnt = JSON.parse(reqData);
			console.log(ctnt);
			var text = reqData;
			text = text.replace(/ +/g,' ').replace(/(\r\n|\n|\r)/gm,"");
			if (ctnt["Status"] == "Error")
			{
				window.alert("Error!\n"+ctnt["Message"])
			}
			else
			{
				window.alert("Succeeded!\n"+ctnt["Message"])
				// location.reload();

			}


		};
		function ToggleEdit(rowId)
		{
			if ($('#rowid_'+rowId+' #view').is(":visible"))
			{
				$('#rowid_'+rowId+' #view').each(function(){ $(this).hide(); })
				$('#rowid_'+rowId+' #edit').each(function(){ $(this).show(); })
				$('#buttonid_'+rowId).text("Ok")

			}
			else
			{
				$('#rowid_'+rowId+' #view').each(function(){ $(this).show(); })
				$('#rowid_'+rowId+' #edit').each(function(){ $(this).hide(); })
				$('#buttonid_'+rowId).text("Edit")

				var ret = ({});

				$('#rowid_'+rowId+' #edit').map(function()
				{
					var inputF = $(this).find('input:first');

					ret["id"] = rowId;
					if (inputF.is(":checkbox"))
					{
						ret[""+inputF.attr('name')] = inputF.prop('checked');
					}
					else
					{
						ret[""+inputF.attr('name')] = inputF.val();
					}

				});
				if (!$.isEmptyObject(ret))
				{
					ret["change-artist-name"] = true;
					$.ajax("api", {"data": ret, success: ajaxSuccess})
				}



			}
		};


	</script>
</head>

<%startTime = time.time()%>

<%namespace name="sideBar" file="genNavBar.mako"/>

<%!
# Module level!
import time
import datetime
from babel.dates import format_timedelta
import os.path

import logging
from settings import settings

logger =  logging.getLogger("Main.WebSrv")



%>





<%def name="genNameListManagementTable(siteShortName, nameTupList)">
	<span>

		<h2 style='display: inline-block' > ${settings[siteShortName]["dlDirName"]}</h2>
	</span>

	<form>
		Add new artist:
		<input type="hidden" name="target" value="addName">
		<input type="hidden" name="add", value="True">
		<input type="hidden" name="site", value="${siteShortName}">
		<div style="display: inline-block;">
			<td><input type="text" name="artistName", value="" size=50></td>
		</div>
		<input type="submit" value="Add">
	</form>
	<button style='display: inline-block' class="btn_${siteShortName}">Show List</button>
	<div class='toggle_${siteShortName}' style='display: none'>
		<table border="1px" style="width:800px;">
			<tr>
					<th class="uncoloured padded" width="670px">Artist Name</th>
					<th class="uncoloured padded" width="30px">Del</th>
			</tr>

			% for uId, artistName in nameTupList:
				<tr id='rowid_${uId}'>

					<td>
						<span id="view"> ${artistName} </span>
						<span id="edit" style="display:none">
							<input type="text" name="aName" style="box-sizing: border-box; width: 100%; -moz-box-sizing: border-box; -webkit-box-sizing: border-box;" value="${artistName}">

						</span>
					</td>

					<td>
						&nbsp;<a href="#" id='buttonid_${uId}' onclick="ToggleEdit('${uId}');return false;">Edit</a>&nbsp;
					</td>
				</tr>
			% endfor

		</table>
	</div>

	<script>
	$(".btn_${siteShortName}").click(function() {

		$(".toggle_${siteShortName}").toggle(200);

	});​
	</script>

</%def>


<%


def getNameDict():

	ret = cur.execute('SELECT id, siteName, artistName FROM %s;' % settings["dbConf"]["namesDb"])
	rets = ret.fetchall()

	items = {}
	for uId, site, name in rets:
		if not site in items:
			items[site] = [(uId, name)]
		else:
			items[site].append((uId, name))

	return items


def processGetArgs(args):
	print("Args", args)

	for key, value in args.items():
		print("	", key, value)

%>

<%



if request.params:
	api.handleApiCall(request)


cur = sqlCon.cursor()



siteNameDict = getNameDict()

sites = [settings[key]['shortName'] for key in settings['artSites']]


sites = []
for key in settings.keys():
	if not isinstance(settings[key], dict):
		continue

	if 'user-url' in settings[key]:
		sites.append(key)
sites.sort()

for site in sites:
	if not site in siteNameDict:
		siteNameDict[site] = []


%>

<body>

<div>

	${sideBar.getSideBar(sqlCon)}
	<div class="maindiv" style="width:1020">

		<div class="subdiv mtMainId">
			<div class="contentdiv">
				<h3>Site Fetched Names</h3>

				<div>

				</div>
				<hr>
			</div>
		</div>

		% for site in sites:
			<div class="subdiv ${site}Id">
				<div class="contentdiv">
					${genNameListManagementTable(site, siteNameDict[site])}
				</div>
			</div>
		% endfor

	</div>
<div>


<%
stopTime = time.time()
timeDelta = stopTime - startTime
%>

<p>This page rendered in ${timeDelta} seconds.</p>

</body>
</html>