## -*- coding: utf-8 -*-
<!DOCTYPE html>

<html>
	<head>
		<meta charset="utf-8">
		<title>WAT WAT IN THE LOGIN</title>
	</head>
	<body>

		<%
		from pyramid.security import authenticated_userid
		print(authenticated_userid)
		user_id = authenticated_userid(request)
		print(user_id)
		%>
		% if user_id != None:
			Successfully logged in as = ${user_id}<br>
			<br>
			Redirecting to home.
			<meta http-equiv="refresh" content="3;/" />
		% else:
			Login Failed!
			<br>
			Try again!
			<meta http-equiv="refresh" content="3;/login" />

		% endif

	</body>
</html>