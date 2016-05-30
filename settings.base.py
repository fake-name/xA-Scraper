
settings = {

	"postgres" :
	{
		"username" : "pg_username",
		"password" : "pg_password",
		"address"  : "pg_ip_addr",
		"database" : "pg_database_name",
	},

	"webCtntPath" : "absolute_path_to_this_repo/Content/",
	"runThreads"  : 8,
	"dldCtntPath" : "absolute_path_downloads_will_go_here",

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
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,
		"dlDirName"       : "DeviantArt",
		"shortName"       : "da",

		'user-url'        : "http://%s.deviantart.com/",
	},
	"fa" :  # Fur Affinity
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*3,   # every 72 hours
		"dlDirName"       : "Fur Affinity",
		"shortName"       : "fa",

		'user-url'        : "http://www.furaffinity.net/user/%s/",
	},
	"hf" :  # Hentai Foundry
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,   # every 36 hours
		"dlDirName"       : "Hentai Foundry",
		"shortName"       : "hf",

		'user-url' : "http://www.hentai-foundry.com/user/%s/profile",
	},
	"px" :  # Pixiv
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,
		"dlDirName"       : "Pixiv",
		"shortName"       : "px",

		'user-url'        : "http://www.pixiv.net/member.php?id=%s"
	},

	"ib" :  # InkBunny
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,
		"dlDirName"       : "InkBunny",
		"shortName"       : "ib",

		'user-url'        : "https://inkbunny.net/%s"
	},

	"wy" :  # Weasyl
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,
		"dlDirName"       : "Weasyl",
		"shortName"       : "wy",

		'user-url'        : "https://www.weasyl.com/~%s"
	},



	"sf" :  # InkBunny
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,
		"dlDirName"       : "SoFurry",
		"shortName"       : "sf",

		'user-url'        : "https://%s.sofurry.com/"
	},

	"tum" :  # Tumblr
	{
		"username"        : "your_username",
		"password"        : "your_password",

		# Fuck you tumblr, really.
		'consumer_key'    : 'tumblr_garbage',
		'consumer_secret' : 'tumblr_garbage',
		'token'           : 'tumblr_garbage',
		'token_secret'    : 'tumblr_garbage',

		"threads"         : 5,
		"runInterval"     : 60*60*24*2,
		"dlDirName"       : "Tumblr",
		"shortName"       : "tum",
		'user-url'        : "http://%s.tumblr.com/"
	},


	"eh" :  # E-Hentai
	{
		"username"        : "your_username",
		"password"        : "your_password",
		"runInterval"     : 60*60*24*2
	},
}



for key in settings.keys():
	if not isinstance(settings[key], dict):
		continue

	if 'user-url' in settings[key]:
		settings['artSites'].append(key)
		settings['ulConf'][key] = settings[key]['dlDirName'].replace(" ", "")
