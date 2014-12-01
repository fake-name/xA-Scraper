
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
			self.conn.execute('''
			CREATE TABLE {tableName} (
			    id            INTEGER PRIMARY KEY,
			    uploadTime    REAL    NOT NULL,
			    uploadedItems INTEGER,
			    galleryId     INTEGER,
			    daid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			    faid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			    hfid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			    pxid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			    ibid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			    wyid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			    UNIQUE ( galleryId )  ON CONFLICT ABORT
			);
			'''.format(tableName=settings["dbConf"]["uploadGalleries"], refName=settings["dbConf"]["namesDb"]))


			# CREATE TABLE {tableName} (
			#     id            INTEGER PRIMARY KEY,
			#     uploadTime    REAL    NOT NULL,
			#     uploadedItems INTEGER,
			#     galleryId     INTEGER,
			#     sourceId      TEXT,
			#     daid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			#     faid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			#     hfid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			#     pxid          INTEGER UNIQUE REFERENCES {refName} ( id ),
			#     UNIQUE ( galleryId )  ON CONFLICT ABORT
			# );

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

	def getByGalleryId(self, gId):
		cur = self.conn.cursor()

		ret = cur.execute("""SELECT mainId, uploadTime, uploadedItems, galleryId FROM %s WHERE galleryId=?;""" % settings["dbConf"]["uploadGalleries"], (gId, ))
		rets = ret.fetchone()
		return rets


	def getGalleryIdById(self, rowId):
		cur = self.conn.cursor()

		ret = cur.execute("""SELECT galleryId FROM %s WHERE id=?;""" % settings["dbConf"]["uploadGalleries"], (rowId, ))
		rets = ret.fetchone()
		if len(rets) > 1:
			raise ValueError("More then one primary key?")
		elif len(rets) == 1:
			return rets[0]
		return None


	def getToProcess(self):
		cur = self.conn.cursor()

		ret = cur.execute("""SELECT id FROM %s WHERE uploadEh=1;""" % settings["dbConf"]["namesDb"])
		rets = ret.fetchall()
		return rets



	def insertGalleryId(self, mainId, galleryId):
		cur = self.conn.cursor()

		# uploadTime of 0 causes it to be updated immediately.
		cur.execute("UPDATE %s SET galleryId=? WHERE id=?"  % (settings["dbConf"]["uploadGalleries"]), (galleryId, mainId))
		self.conn.commit()



	def getUploadState(self, mainId):
		cur = self.conn.cursor()

		ret = cur.execute("SELECT uploadTime, uploadedItems, galleryId FROM %s WHERE id=?;" % (settings["dbConf"]["uploadGalleries"]), (mainId,))
		items = ret.fetchall()

		if len(items) > 1:
			print("Returned ", items)
			raise ValueError("Wat? Gallery appears to exist already? Please delete colliding library.")
		if len(items) == 0:
			raise ValueError("Wat? Gallery not found, and it should exist at this point!")

		return items.pop()

	def getSiteIds(self, mainId):
		cur = self.conn.cursor()

		ret = cur.execute("SELECT daid, faid, hfid, pxid, ibid, wyid FROM %s WHERE id=?;" % (settings["dbConf"]["uploadGalleries"]), (mainId,))
		items = ret.fetchall()

		if len(items) > 1:
			print("Returned ", items)
			raise ValueError("Wat? How did you get duplicate primary keys?")
		if len(items) == 0:
			raise ValueError("Wat? Gallery not found, and it should exist at this point!")

		row = items.pop()
		names = ['daid', 'faid', 'hfid', 'pxid', 'ibid', 'wyid']
		ret = dict(zip(names, row))

		return ret



	def haveUploaded(self, imagePath):
		cur = self.conn.cursor()

		ret = cur.execute("SELECT COUNT(*) FROM %s WHERE imagePath=?;" % (settings["dbConf"]["uploadedImages"]), (imagePath,))
		items = ret.fetchall()
		if len(items) != 1:
			print("Returned ", items)
			raise ValueError("Wat? Gallery appears to exist already? Please delete colliding library.")

		ret = items.pop()[0]
		# print("Ret", ret, bool(ret))
		return bool(ret)

	def addUploaded(self, artistId, imagePath):
		cur = self.conn.cursor()
		cur.execute("INSERT INTO %s (artistId, imagePath) VALUES (?, ?)"  % (settings["dbConf"]["uploadedImages"]), (artistId, imagePath))
		self.conn.commit()


	def getUploaded(self, artistId):
		cur = self.conn.cursor()
		ret = cur.execute("SELECT artistId, imagePath FROM %s WHERE artistId=?;"  % (settings["dbConf"]["uploadedImages"]), (artistId, ))
		items = ret.fetchall()
		self.conn.commit()
		return items



	def setUpdateTimer(self, artistId, updateTime):
		cur = self.conn.cursor()
		cur.execute("UPDATE %s SET uploadTime=? WHERE id=?;"  % (settings["dbConf"]["uploadGalleries"]), (updateTime, artistId))
		self.conn.commit()


	def updateGalleryId(self, mainId, galleryId):
		cur = self.conn.cursor()
		cur.execute("UPDATE %s SET galleryId=? WHERE id=?;"  % (settings["dbConf"]["uploadGalleries"]), (galleryId, mainId))

		self.conn.commit()



	def getNamesForUlRow(self, rowId):
		ret = self.getSiteIds(rowId)
		# drop all keys which we're not uploading (v == None)

		rows = [item for item in ret.values() if item]

		ret = []
		for value in rows:
			ret.append(self.getByRowId(value)[-1])

		return ret









