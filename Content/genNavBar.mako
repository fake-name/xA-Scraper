## -*- coding: utf-8 -*-

<%!
# Module level!


import datetime
from babel.dates import format_timedelta
import time

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

	# Counting stuff


	cur = sqlConnection.cursor()


	cur.execute('SELECT COUNT(*) FROM errored_pages WHERE siteName="fa";')
	faErrs = cur.fetchone()[0]

	cur.execute('SELECT COUNT(*) FROM retrieved_pages WHERE siteName="fa";')
	faSucceed = cur.fetchone()[0]

	# ----------------------------

	cur.execute('SELECT COUNT(*) FROM errored_pages WHERE siteName="da";')
	daErrs = cur.fetchone()[0]

	cur.execute('SELECT COUNT(*) FROM retrieved_pages WHERE siteName="da";')
	daSucceed = cur.fetchone()[0]

	# ----------------------------

	cur.execute('SELECT COUNT(*) FROM errored_pages WHERE siteName="hf";')
	hfErrs = cur.fetchone()[0]

	cur.execute('SELECT COUNT(*) FROM retrieved_pages WHERE siteName="hf";')
	hfSucceed = cur.fetchone()[0]

	# ----------------------------

	cur.execute('SELECT COUNT(*) FROM errored_pages WHERE siteName="px";')
	pxErrs = cur.fetchone()[0]

	cur.execute('SELECT COUNT(*) FROM retrieved_pages WHERE siteName="px";')
	pxSucceed = cur.fetchone()[0]

	cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionName="nextRun";')
	nextRuns = cur.fetchall()
	nextRuns = dict(nextRuns)

	cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionName="isRunning";')
	runState = cur.fetchall()
	runState = dict(runState)

	cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionName="prevRun";')
	lastRun = cur.fetchall()
	lastRun = dict(lastRun)

	cur.execute('SELECT siteName,statusText FROM statusDb WHERE sectionName="prevRunTime";')
	runTime = cur.fetchall()
	runTime = dict(runTime)

	for key in ["da", "fa", "hf", "px"]:
		nextRuns[key] = compactDateStr(format_timedelta(float(nextRuns[key])-time.time(), locale='en_US'))
		runState[key] = "Yes" if runState[key] == "1" else "No"
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

		<div class="statediv">
			<strong>Status:</strong>
		</div>
		<br>
		<div class="statediv daId">
			<strong>DA:</strong><br />
			Have: ${daSucceed}<br />
			Errs: ${daErrs}
			<hr>
			NextRun: ${nextRuns["da"]}<br />
			Running: ${runState["da"]}<br />
			RunTime: ${runTime["da"]}<br />
			LastRun: ${lastRun["da"]}<br />


		</div>
		<div class="statediv faId">
			<strong>FA:</strong><br />
			Have: ${faSucceed}<br />
			Errs: ${faErrs}
			<hr>
			NextRun: ${nextRuns["fa"]}<br />
			Running: ${runState["fa"]}<br />
			RunTime: ${runTime["fa"]}<br />
			LastRun: ${lastRun["fa"]}<br />
		</div>
		<div class="statediv hfId">
			<strong>HF:</strong><br />
			Have: ${hfSucceed}<br />
			Errs: ${hfErrs}
			<hr>
			NextRun: ${nextRuns["hf"]}<br />
			Running: ${runState["hf"]}<br />
			RunTime: ${runTime["hf"]}<br />
			LastRun: ${lastRun["hf"]}<br />

		</div>
		<div class="statediv pxId">
			<strong>PX:</strong><br />
			Have: ${pxSucceed}<br />
			Errs: ${pxErrs}
			<hr>
			NextRun: ${nextRuns["px"]}<br />
			Running: ${runState["px"]}<br />
			RunTime: ${runTime["px"]}<br />
			LastRun: ${lastRun["px"]}<br />
		</div>
		<br>
		<div class="statediv navId">
			<strong>Navigation:</strong><br />
			<ul>
				<li><a href="/">Index</a>
				<hr>
				<li><a href="errLists">Error Lists</a>
				<li><a href="errLists?db=da">DA Errors</a>
				<li><a href="errLists?db=fa">FA Errors</a>
				<li><a href="errLists?db=hf">HF Errors</a>
				<li><a href="errLists?db=px">PX Errors</a>
				<hr>
				<li><a href="/source/bysite/da">DA Artists</a>
				<li><a href="/source/bysite/fa">FA Artists</a>
				<li><a href="/source/bysite/hf">HF Artists</a>
				<li><a href="/source/bysite/px">PX Artists</a>
				<hr>
				<li><a href="/dbNameListEditor">Monitored Names</a>
<!-- 				<hr>
				<li><a href="dbFix">DB Tweaker</a> -->
			</ul>
		</div>
	</div>

</%def>
