## -*- coding: utf-8 -*-

<%!
# Module level!


import datetime
from babel.dates import format_timedelta
import time
import psycopg2

from settings import settings

def compactDateStr(dateStr):
	dateStr = dateStr.replace("months", "mo")
	dateStr = dateStr.replace("month", "mo")
	dateStr = dateStr.replace("weeks", "w")
	dateStr = dateStr.replace("week", "w")
	dateStr = dateStr.replace("days", "d")
	dateStr = dateStr.replace("day", "d")
	dateStr = dateStr.replace("hours", "hr")
	dateStr = dateStr.replace("hour", "hr")
	dateStr = dateStr.replace("minutes", "m")
	dateStr = dateStr.replace("minute", "m")
	dateStr = dateStr.replace("seconds", "s")
	dateStr = dateStr.replace("second", "s")
	return dateStr


%>


<%def name="getSideBar(sqlConnection)">




	<%
	cur = sqlConnection.cursor()

	try:

		cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionname=\'nextRun\';')
		cur.fetchall()
	except psycopg2.InternalError:
		cur.execute("ROLLBACK;")

	contentSources = {}
	for key in settings.keys():
		if not isinstance(settings[key], dict):
			print("Ignoring: ", key)
			continue

		if 'user-url' in settings[key]:
			print('key', key)
			contentSources[key] = settings[key]

	keys = list(contentSources.keys())
	keys.sort()

	# Counting stuff


	cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionname=\'nextRun\';')
	nextRuns = cur.fetchall()
	nextRuns = dict(nextRuns)

	cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionname=\'isRunning\';')
	runState = cur.fetchall()
	runState = dict(runState)

	cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionname=\'prevRun\';')
	lastRun = cur.fetchall()
	lastRun = dict(lastRun)

	cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionname=\'prevRunTime\';')
	runTime = cur.fetchall()
	runTime = dict(runTime)

	for key in keys:
		if key in nextRuns:
			nextRuns[key] = compactDateStr(format_timedelta(float(nextRuns[key])-time.time(), locale='en_US'))
		else:
			nextRuns[key] = "N.A."

		if key in runState:
			runState[key] = "Yes" if runState[key] == "1" else "No"
		else:
			runState[key] = "N.A."

		if key in lastRun:
			# print("Last run = ", lastRun[key])
			lastRun[key] = compactDateStr(format_timedelta(float(lastRun[key])-time.time(), locale='en_US'))
		else:
			lastRun[key] = "N.A."
		if key in runTime:
			runTime[key] = compactDateStr(format_timedelta(float(runTime[key]), locale='en_US'))
		else:
			runTime[key] = "N.A."


	%>
	<div class="statusdiv">

		<div class="statediv navId">
			<strong>Navigation:</strong><br />
			<ul>
				<li><a href="/">Index</a>
				<hr>
				<li><a href="errLists">Error Lists</a>

				% for key in keys:
					<li><a href="/errLists?db=${key}">${key.upper()} Errors</a>
				% endfor
				<hr>
				% for key in keys:
					<li><a href="/source/bysite/${key}">${key.upper()} Artists</a>
				% endfor
				<hr>
				<li><a href='/fa-manual-login'>Manual FA Login</a>
				<hr>
				<li><a href="/dbNameListEditor">Monitored Names</a>
				<li><a href="/uploadEditor">Upload Settings</a>
			</ul>
		</div>
		<div class="statediv">
			<strong>Status:</strong>
		</div>
		<br>

		% for key in keys:
			<%

			cur.execute('SELECT COUNT(*) FROM errored_pages WHERE siteName=%s;', (key, ))
			errs = cur.fetchone()[0]

			cur.execute('SELECT COUNT(*) FROM retrieved_pages WHERE siteName=%s;', (key, ))
			succeed = cur.fetchone()[0]

			%>


			<div class="statediv ${key}Id">
				<strong>${key.upper()}:</strong><br />
				Have: ${succeed}<br />
				Errs: ${errs}
				<hr>
				NextRun: ${nextRuns[key]}<br />
				Running: ${runState[key]}<br />
				RunTime: ${runTime[key]}<br />
				LastRun: ${lastRun[key]}<br />

			</div>
		% endfor



	</div>


</%def>
