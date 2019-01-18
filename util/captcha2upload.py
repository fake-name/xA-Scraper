'''
Originally from: https://github.com/Mirio/captcha2upload
Some changes by Fake-Name: https://github.com/fake-name

Copyright (c) 2015, Alessandro Sbarbati
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.

'''
import logging
import io
from os.path import exists
from requests import post, get
from time import sleep
from settings import settings

class CaptchaSolverMixin:
	def __init__(self):
		if (settings['captcha']['2Captcha-API-key'] and
			settings['captcha']['2Captcha-API-key'] != '<key goes here>' and
			len(settings['captcha']['2Captcha-API-key']) == 32):
			self.captcha_solver = CaptchaUpload(key=settings['captcha']['2Captcha-API-key'], log=logging.getLogger("Main.CaptchaSolver"))
		else:
			self.log.warning("No 2Captcha API key found (or key not valid). Cannot do automated captcha solving!")
			self.captcha_solver = None

class CaptchaUpload:
	def __init__(self, key, log=None, waittime=None):
		self.settings = {"url_request": "http://2captcha.com/in.php",
						 "url_response": "http://2captcha.com/res.php",
						 "key": key}
		self.log = log

		if waittime:
			self.waittime = waittime
		else:
			self.waittime = 30

	def getbalance(self):
		"""
		This request need for get balance
		:return: <YOURBALANCE> OK | 1 ERROR!
		"""
		fullurl = "%s?action=getbalance&key=%s" % (
			self.settings['url_response'], self.settings['key'])
		request = get(fullurl)
		if "." in request.text:
			self.log.info("[2CaptchaUpload] Balance: %s" % request.text)
			return request.text
		elif request.text == "ERROR_KEY_DOES_NOT_EXIST":
			self.log.error("[2CaptchaUpload] You used the wrong key in the query")
			return 1
		elif request.text == "ERROR_WRONG_ID_FORMAT":
			self.log.error("[2CaptchaUpload] Wrong format ID CAPTCHA. ID must contain only numbers")
			return 1

	def getresult(self, captcha_id):
		"""
		This function return the captcha solved
		:param id: id captcha returned by upload
		:return: <captchaword> OK | 1 ERROR!
		"""
		self.log.info("[2CaptchaUpload] Wait %s second.." % self.waittime)
		sleep(self.waittime)
		fullurl = "%s?key=%s&action=get&id=%s" % (self.settings['url_response'],
												  self.settings['key'], captcha_id)
		self.log.info("[2CaptchaUpload] Get Captcha solved with id %s", captcha_id)
		request = get(fullurl)
		if request.text.split('|')[0] == "OK":
			return request.text.split('|')[1]
		elif request.text == "CAPCHA_NOT_READY":
			self.log.error("[2CaptchaUpload] CAPTCHA is being solved, "
							  "repeat the request several seconds later, wait "
							  "another %s seconds" % self.waittime)
			return self.getresult(id)
		elif request.text == "ERROR_KEY_DOES_NOT_EXIST":
			self.log.error("[2CaptchaUpload] You used the wrong key in  the query")
			return 1
		elif request.text == "ERROR_WRONG_ID_FORMAT":
			self.log.error("[2CaptchaUpload] Wrong format ID CAPTCHA. ID must contain only numbers")
			return 1
		elif request.text == "ERROR_CAPTCHA_UNSOLVABLE":
			self.log.error("[2CaptchaUpload] Captcha could not solve three different employee. Funds for this captcha not")
			return 1

	def solve(self, pathfile=None, filedata=None, filename=None):
		"""
		This function upload read, upload and is the wrapper for solve
			the captcha
		:param pathfile: path of image
		:return: <captchaword> OK | 1 ERROR!
		"""

		if pathfile and exists(pathfile):
			files = {'file': open(pathfile, 'rb')}
		elif filedata:
			assert filename
			files = {'file' : (filename, io.BytesIO(filedata))}
		else:
			raise ValueError("You must pass either a valid file path, or a bytes array containing the captcha image!")

		print("files:", files)
		payload = {'key': self.settings['key'], 'method': 'post'}

		self.log.info("[2CaptchaUpload] Uploading to 2Captcha.com..")

		request = post(self.settings['url_request'], files=files, data=payload)

		if request.ok:
			if request.text.split('|')[0] == "OK":
				self.log.info("[2CaptchaUpload] Upload Ok")
				return self.getresult(request.text.split('|')[1])
			elif request.text == "ERROR_WRONG_USER_KEY":
				self.log.error("[2CaptchaUpload] Wrong 'key' parameter"
								   " format, it should contain 32 symbols")
				return 1
			elif request.text == "ERROR_KEY_DOES_NOT_EXIST":
				self.log.error("[2CaptchaUpload] The 'key' doesn't exist")
				return 1
			elif request.text == "ERROR_ZERO_BALANCE":
				self.log.error("[2CaptchaUpload] You don't have money "
								   "on your account")
				return 1
			elif request.text == "ERROR_NO_SLOT_AVAILABLE":
				self.log.error("[2CaptchaUpload] The current bid is "
								   "higher than the maximum bid set for "
								   "your account.")
				return 1
			elif request.text == "ERROR_ZERO_CAPTCHA_FILESIZE":
				self.log.error("[2CaptchaUpload] CAPTCHA size is less than 100 bites")
				return 1
			elif request.text == "ERROR_TOO_BIG_CAPTCHA_FILESIZE":
				self.log.error("[2CaptchaUpload] CAPTCHA size is more than 100 Kbites")
				return 1
			elif request.text == "ERROR_WRONG_FILE_EXTENSION":
				self.log.error("[2CaptchaUpload] The CAPTCHA has a "
								   "wrong extension. Possible extensions "
								   "are: jpg,jpeg,gif,png")
				return 1
			elif request.text == "ERROR_IMAGE_TYPE_NOT_SUPPORTED":
				self.log.error("[2CaptchaUpload] The server cannot "
								   "recognize the CAPTCHA file type.")
				return 1
			elif request.text == "ERROR_IP_NOT_ALLOWED":
				self.log.error("[2CaptchaUpload] The request has sent "
								   "from the IP that is not on the list of"
								   " your IPs. Check the list of your IPs "
								   "in the system.")
				return 1
			elif request.text == "IP_BANNED":
				self.log.error("[2CaptchaUpload] The IP address you're"
								   " trying to access our server with is "
								   "banned due to many frequent attempts "
								   "to access the server using wrong "
								   "authorization keys. To lift the ban, "
								   "please, contact our support team via "
								   "email: support@2captcha.com")
				return 1
