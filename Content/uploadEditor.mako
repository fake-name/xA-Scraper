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
			if (ctnt["Status"] == "Success")
			{
				window.alert("Succeeded!\n"+ctnt["Message"])
				if (ctnt['reload'] == true)
					location.reload();
			}
			else
			{
				window.alert("Error!\n"+ctnt["Message"])


			}


		};
		function ToggleEdit(rowId)
		{
			console.log('Visibility:', $('#rowid_'+rowId+' #view').is(":visible"))
			console.log('Object:', $('#rowid_'+rowId+' #view'))

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
					var inputF = $(this).find('select:first');

					ret["id"] = rowId;


					ret[""+inputF.attr('name')] = inputF.val();


				});
				if (!$.isEmptyObject(ret))
				{
					ret["change-upload-status"] = true;
					$.ajax("api", {"data": ret, success: ajaxSuccess})
				}

			}
		};

		function newRow()
		{
			console.log("New Row");
			var ret = ({});
			ret["add-new-row"] = true;
			$.ajax("api", {"data": ret, success: ajaxSuccess})
		}

	</script>
</head>

## <input type="text" name="${settings["ulConf"][srcKey]}" style="box-sizing: border-box; width: 100%; -moz-box-sizing: border-box; -webkit-box-sizing: border-box;" value="keyVal">

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




<%def name="getNameFromId(inId)">
	<%

	cur = sqlCon.cursor()
	ret = cur.execute('SELECT siteName, artistName FROM {table} WHERE id=?;'.format(table=settings["dbConf"]["namesDb"]), (inId, ))
	rets = ret.fetchall()
	if rets:
		return rets.pop()
	else:
		return None, None
	%>
</%def>


<%def name="getDropbox(srcId, selectId=None)">
	<%

	cur = sqlCon.cursor()
	ret = cur.execute('SELECT id, artistName FROM {table} WHERE siteName=?;'.format(table=settings["dbConf"]["namesDb"]), (srcId, ))
	rets = ret.fetchall()

	%>
	<select name="aname_${srcId}">
		<option value="" ${'selected="selected"' if not selectId else ''}>--</option>
		% for aId, name in rets:
			<option value="${aId}" ${'selected="selected"' if selectId == aId else ''} >${name.title()}</option>
		% endfor
	</select>
</%def>



<%def name="genUploadManagementTable(scrapeList, nameLUT)">

	<%

	cols = list(settings["ulConf"].keys())
	cols.sort()

	# Pixiv column is currently somewhat useless, as it's
	# populated by the pixiv favorites, and not stored
	# in the DB.
	cols.remove("px")


	%>
	<table border="1px" style="width:800px;">
		<tr>
				<th class="uncoloured padded" width="70px">RowId</th>
				<th class="uncoloured padded" width="70px">GalId</th>
				% for col in cols:
					<th class="uncoloured padded" width="200px">${settings["ulConf"][col]}</th>
				% endfor
				<th class="uncoloured padded" width="30px">Del</th>
		</tr>

		% for rowId, rowData in scrapeList.items():
			<%

			print(rowId, rowData)
			galId, aIds = rowData
			print(cols)
			print(aIds)



			aIds = dict(zip(cols, aIds))
			%>
			<tr id='rowid_${rowId}'>

				<td>
					${rowId}
				</td>
				<td>
					${galId}
				</td>

				% for srcKey in cols:
					<%
					print(srcKey, aIds[srcKey])

					src, name = getNameFromId(aIds[srcKey])
					keyVal = '' if aIds[srcKey] == None else name
					if src and src != srcKey:
						print("Wat?")

					%>
					<td>
						## 'display: block;' is a hack to force jquery's :visible to properly resove items as visible even though
						## they have not content. Arrrgh.
						<span id="view" style="display: block;"> ${keyVal} </span>
						<span id="edit" style="display: none;">
							${getDropbox(srcKey, aIds[srcKey])}

						</span>
					</td>
				% endfor

				<td>
					&nbsp;<a href="#" id='buttonid_${rowId}' onclick="ToggleEdit('${rowId}');return false;">Edit</a>&nbsp;
				</td>
			</tr>
		% endfor

	</table>
</%def>


<%


def getNameDict():

	cur = sqlCon.cursor()
	cols = list(settings["ulConf"].keys())
	cols.sort()
	cols = [key+'id' for key in cols if key != 'px']
	cols = ", ".join(cols)

	ret = cur.execute('SELECT id, galleryId, {cols} FROM {table};'.format(table=settings["dbConf"]["uploadGalleries"], cols=cols))
	rets = ret.fetchall()

	ids = []
	for keyset in rets:
		for key in keyset[2:]:
			if key != None:
				ids.append(key)

	items = {}
	for row in rets:
		site = row[0]
		item = (row[1], row[2:])
		if not site in items:
			items[site] = item
		else:
			raise ValueError("Duplicate primary keys? Watttttttttttttttttt")

	# print("Items", items)

	opts = ["id={id}".format(id=val) for val in ids]
	opts = " OR ".join(opts)

	ret = cur.execute('SELECT id, artistName FROM {table} WHERE {condition};'.format(table=settings["dbConf"]["namesDb"], condition=opts))
	rets = ret.fetchall()
	nameLUT = dict(rets)

	return items, nameLUT


def processGetArgs(args):
	print("Args", args)

	for key, value in args.items():
		print("	", key, value)

%>

<%



if request.params:
	api.handleApiCall(request)





scrapeList, nameLUT = getNameDict()


%>

<body>

<div>

	${sideBar.getSideBar(sqlCon)}
	<div class="maindiv" style="width:1020">

		<div class="subdiv mtMainId">
			<div class="contentdiv">
				<h3>Site Fetched Names</h3>

				<div>

					${genUploadManagementTable(scrapeList, nameLUT)}

				</div>
				<button onclick="newRow()">Add Row</button>
			</div>
		</div>

		## % for site in sites:
		## 	<div class="subdiv ${site}Id">
		## 		<div class="contentdiv">
		## 			${genUploadManagementTable(scrapeList, nameLUT))}
		## 		</div>
		## 	</div>
		## % endfor

	</div>
<div>


<%
stopTime = time.time()
timeDelta = stopTime - startTime
%>

<p>This page rendered in ${timeDelta} seconds.</p>

</body>
</html>