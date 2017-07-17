## -*- coding: utf-8 -*-
<!DOCTYPE html>


<html>
	<head>
		<meta charset="utf-8">
		<title>OMGWTFLOLBBQ</title>
	</head>

	<body>
		<H1>${error_str}</H1>

		<h3>YOU BROKE ALL THE THINGS<h3>
		<p>
			<%
				try:
					debugStr = tracebackStr
				except:
					debugStr = "No traceback? Error?"

			%>
			<pre>
${debugStr}
			</pre>
		</p>

	</body>
</html>