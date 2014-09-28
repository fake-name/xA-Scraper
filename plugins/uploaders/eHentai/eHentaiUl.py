
import os
import os.path
import traceback
import re
import bs4
import urllib.request
import urllib.parse
import time
import webFunctions as wg
from settings import settings

import plugins.uploaders.UploadBase

class UploadEh(plugins.uploaders.UploadBase.UploadBase):

	settingsDictKey = "eh"
	pluginName = "Eh.Ul"

	ovwMode = "Check Files"

	numThreads = 1



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie management sillyness
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def checkCookie(self):
		idCookie   =	re.search(r"<Cookie ipb_member_id=[%0-9]*? for \.e-hentai\.org/>", "%s" % self.wg.cj, re.IGNORECASE)
		passCookie =	re.search(r"<Cookie ipb_pass_hash=[%0-9a-f]*? for \.e-hentai\.org/>", "%s" % self.wg.cj, re.IGNORECASE)


		if idCookie and passCookie:
			return True, "Have e-hentai Cookies:\n	%s\n	%s" % (idCookie.group(0), passCookie.group(0))
		# print idCookie, authSecureCookie
		return False, "Do not have e-hentai login Cookies"


	def getCookie(self):

		prepage = self.wg.getpage('http://e-hentai.org/bounce_login.php')
		# print prepage
		soup = bs4.BeautifulSoup(prepage)
		form = soup.find("form", action="https://forums.e-hentai.org/index.php?act=Login&CODE=01")
		items = form.find_all("input")
		logDict = {}
		for item in items:
			if "name" in item.attrs and "value" in item.attrs:
				print("Attrs = ", item.attrs)
				print("'%s', '%s'" % (item["name"], item["value"]))
				logDict[item["name"]] = item["value"]

		# print(logDict)
		if not "UserName" in logDict and "PassWord" in logDict:
			raise ValueError("Login form structure changed! Don't know how to log in correctly!	")

		# Note: Case sensitive!
		logDict["UserName"] = settings["eh"]["username"]
		logDict["PassWord"] = settings["eh"]["password"]


		pagetext = self.wg.getpage('https://forums.e-hentai.org/index.php?act=Login&CODE=01', postData = logDict)

		if re.search("You are now logged in as", pagetext):
			return "Logged In"
		else:
			return "Login Failed"

	def checkExAccess(self):
		dummy_exPg, handle = self.wg.getpage("http://exhentai.org/", returnMultiple=True)
		return "text" in handle.headers.get("Content-Type")




	def getToProcess(self):
		cur = self.conn.cursor()

		ret = cur.execute("""SELECT id FROM %s WHERE uploadEh=1;""" % settings["dbConf"]["namesDb"])
		rets = ret.fetchall()
		return rets





	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Actual uploading bits
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def uploadFromRowId(self, rowId, siteName, aName):

		print("Should process %s, %s, %s" % (rowId, siteName, aName))

	def getExtantGalleries(self):
		ret = []

		pagetext = self.wg.getpage('http://ul.exhentai.org/manage.php')

		soup = bs4.BeautifulSoup(pagetext)
		items1 = soup.find_all("tr", class_="gtr1")
		items2 = soup.find_all("tr", class_="gtr0")

		items = items1+items2

		for item in items:
			itemTd = item.find("td", class_="gtc1")
			aName = itemTd.get_text().split("-")[0]
			aName = aName.rstrip().lstrip().lower()

			itemUrl = itemTd.a["href"]
			urlQuery = urllib.parse.urlparse(itemUrl)[4]
			itemGid = urllib.parse.parse_qs(urlQuery)["gid"].pop()

			ret.append((aName, itemGid))

		return ret

	def createGallery(self, aName, uniques, totalItems):
		# pagetext = self.wg.getpage('http://ul.exhentai.org/manage.php?act=new')
		# soup = bs4.BeautifulSoup(pagetext)

		# form = soup.find("form", action="http://ul.exhentai.org/manage.php?act=new")
		# items = form.find_all("input")
		# formDict = {}
		# for item in items:
		# 	if "name" in item.attrs and "value" in item.attrs:
		# 		formDict[item["name"]] = item["value"]

		# formDict["tos"]

		formDict = {}

		title       = "%s - Collected Works" % aName.title()
		description = """Assorted art from varied sources for artist: %s.

		Auto-Gallery System 0.0001a (really, really alpha release)
		This is an automatically maintained gallery. Please direct any issues/complaints/complements to fake0name@tfwno.gf.

		By SHA-1 duplicate checking, this gallery should contain %s new items, %s duplicates, and is therefore
		a super-set of any previously uploaded galleries. These values only reflect the initial upload state, though, and will miss items
		that have been recompressed/resaved.

		If there is an artist on DeviantArt, HentaiFoundry, FurAffinity or Pixiv you would
		like a mirror of, feel free to ask. I currently have automated systems in place to
		periodically update my local mirror of all four of these sites, and adding
		additional targets to scrape is a trivial matter.

		Updates are limited to at-max once every two weeks, as the rules require. If you see updates more often then that, plese
		report the issue, and I'll see about fixing it as soon as possible.
		""" % (aName.title(), uniques, totalItems-uniques)

		formDict["gname"]         = title
		formDict["gname_jpn"]     = ""
		formDict["gfldr"]         = 2
		formDict["gfldrnew"]      = ""
		formDict["comment"]       = description
		formDict["publiccat"]     = 10
		formDict["tos"]           = "on"
		formDict["creategallery"] = "Create+and+Continue"

		# print(formDict)

		pagetext = self.wg.getpage('http://ul.exhentai.org/manage.php?act=new', postData = formDict)

		soup = bs4.BeautifulSoup(pagetext)
		forward = soup.find('p', id='continue')
		forward.a['href']

		itemUrl = forward.a['href']
		urlQuery = urllib.parse.urlparse(itemUrl)[4]
		newGid = urllib.parse.parse_qs(urlQuery)["gid"].pop()
		newGid = int(newGid)

		print("Created gallery for ", aName)
		return newGid

	def uploadFile(self, gid, filePath):

		gurl = 'http://ul.e-hentai.org/manage.php?act=add&gid=%s' % gid

		with open(filePath, "rb") as fp:
			fcont = fp.read()
		fName = os.path.split(filePath)[-1]
		form = wg.MultiPartForm()
		form.add_field("MAX_FILE_SIZE", '52428800')
		form.add_field("ulact", 'ulmore')
		form.add_file("file01", fName, fcont)

		self.wg.getpage(gurl, binaryForm=form)


	def updateGallery(self, rowId, images):
		lastUl, ulQuantity, galleryId = self.getUploadState(rowId)

		if lastUl > time.time() - 60*60*24*14:
			self.log.info("Item updated within the last two weeks. Skipping")

		for image in images:
			if self.haveUploaded(image):
				continue

			self.uploadFile(galleryId, image)
			self.addUploaded(rowId, image)

		self.setUpdateTimer(rowId, time.time())



		# print("rowId", rowId, "images", images)

	def checkGallery(self, haveItems, rowId):

		images = self.getImagesForId(rowId)


		siteName, aName = self.getByRowId(rowId)
		if not aName in [name for name, gId in haveItems]:

			numUnique = self.checkIfShouldUpload(images)
			if numUnique > 3:
				newGid = self.createGallery(aName, numUnique, len(images))
				self.addNewUploadGallery(rowId, newGid)
				self.updateGallery(rowId, images)
			else:
				self.log.warn("Do not have sufficent unique items to warrant upload for artist %s!" % aName)

		else:
			print("Have gallery for", aName, "Updating")
			self.updateGallery(rowId, images)



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Deduplication stuff
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkIfHashExists(self, hashS):
		pagetext = self.wg.getpage('http://exhentai.org/?f_shash=%s' % hashS)
		if "No hits found" in pagetext:
			return False
		return True

	def checkIfShouldUpload(self, fileList):
		uniques = 0
		nonuniq = 0
		toScan = len(fileList)
		for fileN in fileList:

			fHash = self.getHashOfFile(fileN)
			if not self.checkIfHashExists(fHash):
				uniques += 1
				self.log.info("Unique item '%s', '%s', '%s'", uniques, nonuniq, fileN)
			else:
				nonuniq += 1
				self.log.info("Non-unique item '%s', '%s', '%s'", uniques, nonuniq, fileN)

			toScan -= 1
			self.log.info("Remaining to check - %s", toScan)
			time.sleep(2)


		return uniques

	def processTodo(self, listIn):

		existingGalleries = self.getExtantGalleries()
		for itemName, itemGid in existingGalleries:
			self.log.info("Have gallery %s, %s", itemName, itemGid)
		for rowId, in listIn:

			self.checkGallery(existingGalleries, rowId)
			# if not alreadyUpdated:
			# else:
			# 	self.log.info("Skipping uploading %s", rowId)




	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Task management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def go(self, toDoList=None, ctrlNamespace=None):
		if ctrlNamespace == None:
			raise ValueError("You need to specify a namespace!")
		self.manager = ctrlNamespace

		try:
			self.wg.cj.clear("exhentai.org")
		except KeyError:
			print("Wat")


		self.statusMgr.updateRunningStatus(self.settingsDictKey, True)
		startTime = time.time()
		self.statusMgr.updateLastRunStartTime(self.settingsDictKey, startTime)
		self.checkInitPrimaryDb()

		haveCookie, dummy_message = self.checkCookie()
		if not haveCookie:
			self.log.info("Do not have login cookie. Retreiving one now.")
			cookieStatus = self.getCookie()
			self.log.info("Login attempt status = %s.", cookieStatus)

		haveCookie, dummy_message = self.checkCookie()
		if not haveCookie:
			self.log.critical("Failed to download cookie! Exiting!")
			return False


		haveEx = self.checkExAccess()
		if not haveEx:

			self.wg.cj.clear("exhentai.org")
			self.wg.cj.clear("e-hentai.org")
			raise ValueError("Logged in, but cannot access ex?")


		if not toDoList:
			toDoList = self.getToProcess()

		self.processTodo(toDoList)


		self.statusMgr.updateRunningStatus(self.settingsDictKey, False)
		runTime = time.time()-startTime
		self.statusMgr.updateLastRunDuration(self.settingsDictKey, runTime)


	@classmethod
	def run(cls, managedNamespace):
		instance = cls()
		instance.go(ctrlNamespace=managedNamespace)

