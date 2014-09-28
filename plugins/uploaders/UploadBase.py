
from settings import settings

import plugins.PluginBase


class UploadBase(plugins.PluginBase.PluginBase):


	def checkInitPrimaryDb(self):
		super().checkInitPrimaryDb()

		cur = self.conn.cursor()
		ret = cur.execute('''SELECT name FROM sqlite_master WHERE type='table';''')
		rets = ret.fetchall()
		tables = [item for sublist in rets for item in sublist]

		if not rets or not settings["dbConf"]["uploadGalleries"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial suceeded page database....")
			self.conn.execute('''CREATE TABLE %s (id INTEGER PRIMARY KEY,
												mainId INTEGER,
												uploadTime real NOT NULL,
												uploadedItems INTEGER,
												galleryId INTEGER,
												FOREIGN KEY(mainId) REFERENCES %s(id),
												UNIQUE(mainId) ON CONFLICT ABORT,
												UNIQUE(galleryId) ON CONFLICT ABORT)''' % (settings["dbConf"]["uploadGalleries"], settings["dbConf"]["namesDb"]))

			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (uploadTime)'''              % ("%s_time_index"          % settings["dbConf"]["uploadGalleries"], settings["dbConf"]["uploadGalleries"]))
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (mainId)'''                  % ("%s_id_index"            % settings["dbConf"]["uploadGalleries"], settings["dbConf"]["uploadGalleries"]))
			self.conn.commit()
			self.log.info("Uploaded artist database created")


		if not rets or not settings["dbConf"]["uploadedImages"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial suceeded page database....")
			self.conn.execute('''CREATE TABLE %s (id INTEGER PRIMARY KEY,
												artistId INTEGER,
												imagePath TEXT,
												FOREIGN KEY(artistId) REFERENCES %s(id),
												UNIQUE(imagePath) ON CONFLICT ABORT)''' % (settings["dbConf"]["uploadedImages"], settings["dbConf"]["namesDb"]))

			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (artistId)'''   % ("%s_a_id_index"            % settings["dbConf"]["uploadedImages"], settings["dbConf"]["uploadedImages"]))
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (imagePath)''' % ("%s_i_id_index"            % settings["dbConf"]["uploadedImages"], settings["dbConf"]["uploadedImages"]))
			self.conn.commit()
			self.log.info("Uploaded artist database created")



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# DB Convenience stuff
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def getByRowId(self, rowId):
		cur = self.conn.cursor()

		ret = cur.execute("""SELECT siteName, artistName FROM %s WHERE id=?;""" % settings["dbConf"]["namesDb"], (rowId, ))
		rets = ret.fetchone()
		return rets


	def getToProcess(self):
		cur = self.conn.cursor()

		ret = cur.execute("""SELECT id FROM %s WHERE uploadEh=1;""" % settings["dbConf"]["namesDb"])
		rets = ret.fetchall()
		return rets



	def addNewUploadGallery(self, mainId, galleryId):
		cur = self.conn.cursor()

		# uploadTime of 0 causes it to be updated immediately.
		cur.execute("INSERT INTO %s (mainId, uploadTime, uploadedItems, galleryId) VALUES (?, ?, ?, ?)"  % (settings["dbConf"]["uploadGalleries"]), (mainId, 0, 0, galleryId))
		self.conn.commit()



	def getUploadState(self, mainId):
		cur = self.conn.cursor()

		ret = cur.execute("SELECT uploadTime, uploadedItems, galleryId FROM %s WHERE mainId=?;" % (settings["dbConf"]["uploadGalleries"]), (mainId,))
		items = ret.fetchall()
		if len(items) != 1:
			print("Returned ", items)
			raise ValueError("Wat? Gallery appears to exist already? Please delete colliding library.")


		return items.pop()


	def haveUploaded(self, imagePath):
		cur = self.conn.cursor()

		ret = cur.execute("SELECT COUNT(*) FROM %s WHERE imagePath=?;" % (settings["dbConf"]["uploadedImages"]), (imagePath,))
		items = ret.fetchall()
		if len(items) != 1:
			print("Returned ", items)
			raise ValueError("Wat? Gallery appears to exist already? Please delete colliding library.")

		ret = items.pop()[0]
		print("Ret", ret, bool(ret))
		return bool(ret)

	def addUploaded(self, artistId, imagePath):
		cur = self.conn.cursor()
		cur.execute("INSERT INTO %s (artistId, imagePath) VALUES (?, ?)"  % (settings["dbConf"]["uploadedImages"]), (artistId, imagePath))
		self.conn.commit()



	def setUpdateTimer(self, artistId, updateTime):
		cur = self.conn.cursor()
		cur.execute("UPDATE %s SET uploadTime=? WHERE mainId=?;"  % (settings["dbConf"]["uploadGalleries"]), (updateTime, artistId))
		self.conn.commit()









