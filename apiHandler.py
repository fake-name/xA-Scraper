


from pyramid.response import Response

from settings import settings
import logging
import json

class ApiInterface(object):

	log = logging.getLogger("Main.API")

	def __init__(self, sqlInterface):
		self.conn = sqlInterface


	def updateName(self, request):

		if not "id" in request.params or not "aName" in request.params:
			return Response(body="Missing required parameters!")

		print("Parameter update call!")
		print(request.params)

		cur = self.conn.cursor()

		ret = cur.execute('SELECT id, siteName, artistName FROM %s WHERE id=?;' % settings["dbConf"]["namesDb"], (request.params["id"], ))

		rets = ret.fetchone()
		if not len(rets):
			return Response(body=json.dumps({"Status": "Error", "Message": "No artist for specified ID!"}))

		rowId, siteName, artistName = rets

		if artistName == request.params["aName"]:
			return Response(body=json.dumps({"Status": "Error", "Message": "No changes made?"}))

		cur.execute("UPDATE %s SET artistName=?, WHERE id=?" % settings["dbConf"]["namesDb"], (request.params["aName"],
																										request.params["id"]))
		self.conn.commit()

		return Response(body=json.dumps({"Status": "Success", "Message": "Updated settings for artist."}))

	def changeRating(self, request):

		print("Parameter update call!")
		print(request.params)

		# if not "new-rating" in request.params:
		# 	return Response(body=json.dumps({"Status": "Failed", "Message": "No new rating specified in rating-change call!"}))

		# mangaName = request.params["change-rating"]
		# newRating = request.params["new-rating"]

		# try:
		# 	newRating = int(newRating)
		# except ValueError:
		# 	return Response(body=json.dumps({"Status": "Failed", "Message": "New rating was not a integer!"}))

		# if not mangaName in nt.dirNameProxy:
		# 	return Response(body=json.dumps({"Status": "Failed", "Message": "Specified Manga Name not in dir-dict."}))

		# print("Calling ratingChange")
		# nt.dirNameProxy.changeRating(mangaName, newRating)
		# print("ratingChange Complete")

		return Response(body=json.dumps({"Status": "Success", "Message": "Directory Renamed"}))

	def nameAdd(self, request):

		requiredKeys = ['target', 'add', 'site', 'artistName']
		for item in requiredKeys:
			if not item in request.params:
				return Response(body=json.dumps({"Status": "Failed", "Message": "Missing required parameters."}))

		site = request.params['site']
		if not site in settings["artSites"]:
			return Response(body=json.dumps({"Status": "Failed", "Message": "Invalid source site."}))

		add = request.params['add']
		if not add == "True":
			return Response(body=json.dumps({"Status": "Failed", "Message": "Add is false?"}))

		name = request.params['artistName']
		if not name:
			return Response(body=json.dumps({"Status": "Failed", "Message": "Name is empty."}))


		cur = self.conn.cursor()

		ret = cur.execute("SELECT * FROM %s WHERE siteName=? AND artistName=?;" % settings["dbConf"]["namesDb"], (site, name))
		have = ret.fetchall()
		if have:
			return Response(body=json.dumps({"Status": "Failed", "Message": "Name is already in database!"}))


		cur.execute("INSERT INTO %s (siteName, artistName) VALUES (?, ?);" % settings["dbConf"]["namesDb"], (site, name))
		self.conn.commit()


	def errResponse(self, errorMessage=None):
		ret = {}
		ret['Status'] = 'Failed'
		if not errorMessage:
			ret['Message'] = 'Error in API Call!'
		else:
			ret['Message']  = 'Error in API Call! \n'
			ret['Message'] += 'Error message: \n'
			ret['Message'] += errorMessage


		return Response(body=json.dumps(ret))


	def handleApiCall(self, request):

		print("API Call!", request.params)

		if "change-rating" in request.params:
			print("Rating change!")
			return self.changeRating(request)

		elif "change-artist-name" in request.params:
			print("Updating artist's name!")
			return self.updateName(request)
		elif 'target' in request.params:
			print("Adding artist!")
			return self.nameAdd(request)

		else:
			print("Unknown API call!")
			return self.errResponse("Unknown command: '%s'" % request.params)
