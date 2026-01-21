
USE_POSTGRESQL = False
import os.path
import os


# Convenience functions to make intervals clearer.
def days(num):
	return 60*60*24*num
def hours(num):
	return 60*60*num
def minutes(num):
	return 60*num

settings = {

	# Web logins go here.
	# format is 'username' : 'password',
	'web-logins' :
	{
		"herp" : "wattttttt"
	},

	'server-conf' :
	{
		'listen-address'      : "0.0.0.0",
		'listen-port'         : 6543,
		'thread-pool-size'    : 20,
	},

	"dldCtntPath" : "absolute_path_downloads_will_go_here",

	"captcha" : {

		"anti-captcha" : {
			'api_key' : "your-key-goes-here"
		},

	},


	# You only need to set these if USE_POSTGRESQL is set to true.
	"postgres" :
	{
		"username" : "pg_username",
		"password" : "pg_password",
		"address"  : "pg_ip_addr",
		"database" : "pg_database_name",


		# 'import_db'      : 'ttrss',
		# 'import_db_user' : 'ttrss_readable_user',
		# 'import_db_pass' : 'ttrss_user_pw',
	},

	"sqlite" :
	{
		"sqlite_db_path" : os.path.abspath(os.path.join("./", "sqlite_db.db"))
	},

	"rpc-server" :
	{
		"address"         : 'ip',
		"port"            : 'other-port',
	},

	"captcha" :
	{
		"2Captcha-API-key" : '<key goes here>',
	},


	# These are built by the little script at the bottom of the file.
	"artSites"    : [],
	"ulConf"      : {},

	"dbConf":
	{
		"namesDb"         : "siteartistnames",
		"retrevialTimeDB" : "retreival_times",
		"erroredPagesDb"  : "errored_pages",
		"successPagesDb"  : "retrieved_pages",


		"uploadedImages"  : "upload_images",
		"uploadGalleries" : "upload_galleries"

	},

	"da" :  # Deviant Art
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : days(2),
		"dlDirName"       : "DeviantArt",

		'user-url'        : "http://%s.deviantart.com/",
	},
	"fa" :  # Fur Affinity
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : days(3),
		"dlDirName"       : "Fur Affinity",

		'user-url'        : "http://www.furaffinity.net/user/%s/",
	},
	"hf" :  # Hentai Foundry
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : days(2),   # every 36 hours
		"dlDirName"       : "Hentai Foundry",

		'user-url' : "http://www.hentai-foundry.com/user/%s/profile",
	},
	"px" :  # Pixiv
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : days(2),
		"dlDirName"       : "Pixiv",

		'user-url'        : "http://www.pixiv.net/member.php?id=%s"
	},

	"ib" :  # InkBunny
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : days(2),
		"dlDirName"       : "InkBunny",

		'user-url'        : "https://inkbunny.net/%s"
	},

	"wy" :  # Weasyl
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : days(2),
		"dlDirName"       : "Weasyl",

		'user-url'        : "https://www.weasyl.com/~%s"
	},

	"as" :  # Artstation
	{
		# No password here.
		"username"        : None,
		"password"        : None,
		"runInterval"     : days(2),
		"dlDirName"       : "ArtStation",

		'user-url'        : "https://www.artstation.com/artist/%s"
	},


	"sf" :  # SoFurry
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : days(2),
		"dlDirName"       : "SoFurry",

		'user-url'        : "https://%s.sofurry.com/"
	},

	"tum" :  # Tumblr
	{
		"username"        : "your_username",

		# Fuck you tumblr, really.
		'consumer_key'    : 'tumblr_garbage',
		'consumer_secret' : 'tumblr_garbage',
		'token'           : 'tumblr_garbage',
		'token_secret'    : 'tumblr_garbage',

		"runInterval"     : days(2),
		"dlDirName"       : "Tumblr",
		'user-url'        : "http://%s.tumblr.com/"
	},


	"eh" :  # E-Hentai
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : days(2)
	},


	"yp" :  # yiff Party
	{
		"dlDirName"       : "YiffParty",
		"runInterval"     : days(2),

		'user-url'        : "%s-None"
	},

	"pat" :  # Patreon
	{
		"username"        : "<username>",
		"password"        : "<password>",

		"dlDirName"       : "Patreon",
		"runInterval"     : 60*60*18,   # every 24 hours
		"blacklisted_artists" : ["<some user name>", "<some other user>"], #the display name, japaneese names may need to be escaped, better use the ID instead
		"blacklisted_artists_ids" : ["<some id>"], # ids in case the user changes screen name
		'user-url'        : "%s-None"
	},
	"ng" : # Newgrounds
	{
		"runInterval"     : 60*60*48,   # every 24 hours
		'user-url'        : "https://%s.newgrounds.com/art",

		"username"        : "<username>",
		"password"        : "<password>",
		"dlDirName"       : "NewGrounds",
	},

	"ay" : # Aryion
	{
		"runInterval"     : 60*60*48,   # every 24 hours
		'user-url'        : "https://aryion.com/g4/user/%s",

		"username"        : "<username>",
		"password"        : "<password>",
		"dlDirName"       : "Aryion",
	},

}


if USE_POSTGRESQL:

	SQLALCHEMY_DATABASE_URI = 'postgresql://{user}:{passwd}@{host}:5432/{database}'.format(
		user     = settings['postgres']['username'],
		passwd   = settings['postgres']['password'],
		host     = settings['postgres']['address'],
		database = settings['postgres']['database']
		)
else:
	SQLALCHEMY_DATABASE_URI = 'sqlite:///{db_path}'.format(db_path = settings['sqlite']['sqlite_db_path'])
	print("Sqlite database path: '%s'" % SQLALCHEMY_DATABASE_URI)

	db_dir, db_f = os.path.split(settings['sqlite']['sqlite_db_path'])
	assert os.path.exists(db_dir), "Sqlite database dir ('%s') doesn't exist!" % (db_dir, )
	assert os.path.isdir(db_dir),  "Sqlite directory ('%s') isn't a directory!" % (db_dir, )
	if os.path.exists(settings['sqlite']['sqlite_db_path']):
		assert not os.path.isdir(settings['sqlite']['sqlite_db_path']), "Sqlite database path ('%s') is currently occupied by a folder. Cannot create database!" % (
			settings['sqlite']['sqlite_db_path'], )

for key in settings.keys():
	if not isinstance(settings[key], dict):
		continue

	if 'user-url' in settings[key]:
		settings['artSites'].append(key)
		settings['ulConf'][key] = settings[key]['dlDirName'].replace(" ", "")


