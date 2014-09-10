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
		user_id = authenticated_userid(request)
		%>
		<form action="${request.route_url('do_login',action='in')}" method="post">
			<table>
				<tr>
					<td><label>Username</label></td>
					<td><input type="text" name="username"></td>
				</tr>
				<tr>
					<td><label>Password</label></td>
					<td><input type="password" name="password"></td>
				</tr>
			</table>
			<input type="submit" value="Sign in">
		</form>
	</body>
</html>