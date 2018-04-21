

class ScraperException(RuntimeError):
	pass

class RetryException(ScraperException):
	pass

class FetchFailedException(ScraperException):
	pass


class ContentRemovedException(ScraperException):
	pass
class CannotAccessException(ScraperException):
	pass
class AccountDisabledException(ScraperException):
	pass

