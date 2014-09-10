
settings = {

	"dbPath"      : "dbPath/db.db",
	"webCtntPath" : "./Content/",
	"runThreads"  : 8,
	"dldCtntPath" : "whereShitWillGo/XaDownloads/",

	"artSites"    : ["da", "fa", "hf", "px"],

	"dbConf":
	{
		"namesDb"         : "siteArtistNames",
		"retrevialTimeDB" : "retreival_times",
		"erroredPagesDb"  : "errored_pages",
		"successPagesDb"  : "retrieved_pages"

	},

	"da" :  # Deviant Art
	{
		"username"        : "username",
		"password"        : "password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,   # every 24 hours
		"dlDirName"       : "DeviantArt",
		"shortName"       : "da"
	},
	"fa" :  # Fur Affinity
	{
		"username"        : "username",
		"password"        : "password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*3,   # every 72 hours
		"dlDirName"       : "Fur Affinity",
		"shortName"       : "fa"
	},
	"hf" :  # Hentai Foundry
	{
		"username"        : "username",
		"password"        : "password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,   # every 36 hours
		"dlDirName"       : "Hentai Foundry",
		"shortName"       : "hf"

	},
	"px" :  # Pixiv
	{
		"username"        : "username",
		"password"        : "password",
		"threads"         : 5,
		"runInterval"     : 60*60*24*2,   # every 24 hours
		"dlDirName"       : "Pixiv",
		"shortName"       : "px"
	},

	"eh" :  # Pixiv
	{
		"username"        : "username",
		"password"        : "password",
		"runInterval"     : 60*60*24*2   # every 24 hours
	},
}

