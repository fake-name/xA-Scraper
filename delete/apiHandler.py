


from pyramid.response import Response

from settings import settings
import logging
import json

class ApiInterface(object):

	log = logging.getLogger("Main.API")

	def __init__(self):


	def updateName(self, request):

		if not "id" in request.params or not "aName" in request.params:
			return Response(body="Missing required parameters!")

		print("Parameter update call!")
		print(request.params)

		cur = self.conn.cursor()

		ret = cur.execute('SELECT id, siteName, artistName FROM %s WHERE id=%%s;' % settings["dbConf"]["namesDb"], (request.params["id"], ))

		rets = ret.fetchone()
		if not len(rets):
			return Response(body=json.dumps({"Status": "Error", "Message": "No artist for specified ID!"}))

		rowId, siteName, artistName = rets

		if artistName == request.params["aName"]:
			return Response(body=json.dumps({"Status": "Error", "Message": "No changes made?"}))

		cur.execute("UPDATE %s SET artistName=%%s, WHERE id=%%s" % settings["dbConf"]["namesDb"], (request.params["aName"],
																										request.params["id"]))
		self.conn.commit()

		return Response(body=json.dumps({"Status": "Success", "Message": "Updated settings for artist."}))

	def changeRating(self, request):

		print("Parameter update call!")
		print(request.params)

		return Response(body=json.dumps({"Status": "Error", "Message": "Rating change not implemented!"}))


	# 'NestedMultiDict([('id', '9'), ('aname_da', ''), ('aname_fa', ''), ('aname_hf', ''), ('aname_ib', ''), ('aname_wy', ''), ('change-upload-status', 'true')])'
	def changeUploadStatus(self, request):

		print("Parameter update call!")
		print(request.params)

		# Verify all the keys

		requireKeys = ['id', 'change-upload-status']

		for key in settings['artSites']:

			# Skip pixiv.
			if key == 'px':
				continue

			key = 'aname_{key}'.format(key=key)
			requireKeys.append(key)



		if not all([key in request.params for key in requireKeys]):
			return self.errResponse("Missing required key in request params.")

		setKeys = []
		setParams = []
		for key in settings['artSites']:
			# Skip pixiv.
			if key == 'px':
				continue

			lookupKey = 'aname_{key}'.format(key=key)
			setKey = '{key}id=?'.format(key=key)
			setKeys.append(setKey)
			if request.params[lookupKey]:
				setParams.append(request.params[lookupKey])
			else:
				setParams.append(None)


		params = setParams + [request.params["id"]]

		query = "UPDATE {table} SET {cols} WHERE id=%s;".format(table=settings["dbConf"]["uploadGalleries"], cols=', '.join(setKeys))

		print('query', query)
		print('params', params)

		cur = self.conn.cursor()
		ret = cur.execute(query, params)
		self.conn.commit()

		return Response(body=json.dumps({"Status": "Success", "Message": "Updated artist state!", 'reload': True}))



	def createEmptyRow(self, request):
		cur = self.conn.cursor()
		cur.execute("INSERT INTO {table} (uploadTime) VALUES (0);".format(table=settings["dbConf"]["uploadGalleries"]))
		self.conn.commit()


		return Response(body=json.dumps({"Status": "Success", "Message": "Inserted new artist!", 'reload': True}))

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

		ret = cur.execute("SELECT * FROM %s WHERE siteName=%%s AND artistName=%%s;" % settings["dbConf"]["namesDb"], (site, name))
		have = cur.fetchall()
		if have:
			return Response(body=json.dumps({"Status": "Failed", "Message": "Name is already in database!"}))


		cur.execute("INSERT INTO %s (siteName, artistName) VALUES (%%s, %%s);" % settings["dbConf"]["namesDb"], (site, name))
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

		elif "change-upload-status" in request.params:
			print("Rating change!")
			return self.changeUploadStatus(request)

		elif "change-artist-name" in request.params:
			print("Updating artist's name!")
			return self.updateName(request)

		elif 'target' in request.params:
			print("Adding artist!")
			return self.nameAdd(request)

		elif 'add-new-row' in request.params:
			print("Adding empty upload row!")
			return self.createEmptyRow(request)

		else:
			print("Unknown API call!")
			return self.errResponse("Unknown command: '%s'" % request.params)
