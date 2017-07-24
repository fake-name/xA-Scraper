

class ScraperException(RuntimeError):
	pass

class RetryException(ScraperException):
	pass

class FetchFailedException(ScraperException):
	pass


class AccountDisabledException(ScraperException):
	pass

