# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
#import DNS
import os

# this is ugly and only for assertive programming
import __main__ 

from yapsy.IPlugin import IPlugin
from validate_email import validate_email
from diskcache import Cache

from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

class ContactFields(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running contact fields checks (ContactFields)")
		ValidateEmails = True
		assert 'emails' in __main__.remoteCheckList
		if 'emails' in args.disableChecksRemote:
			ValidateEmails = False
		else:
			ValidateEmails = True

		cache_dir = 'data-check-cache/emails'
		if not os.path.exists(cache_dir):
			os.makedirs(cache_dir)
		cache = Cache(cache_dir)
		if 'emails' in args.purgeCaches:
			cache.clear()
			
		for contact in dir.getContacts():
			if(not 'first_name' in contact or re.search('^\s*$', contact['first_name'])):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Missing first name for contact ('first_name' attribute is empty)"))
			if(not 'last_name' in contact or re.search('^\s*$', contact['last_name'])):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Missing last name for contact ('last_name' attribute is empty)"))
			if(not 'email' in contact or re.search('^\s*$', contact['email'])):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Missing email for contact ('email' attribute is empty)"))
			elif(not validate_email(contact['email'])):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Email for contact is invalid - offending  'email' attribute value: " + contact['email']))
			else:
				# This is pretty dramatic test and should be used sparingly
				if ValidateEmails:
					contact_email = contact['email']
					log_message = "Validating email " + contact_email
					# XXX: does not work in most cases
					#if(not validate_email(contact['email'],verify=True)):
					try:
						if(contact_email in cache):
							cache_result = cache[contact_email]
							if(cache_result['valid']):
								log_message += " -> OK"
							else:
								log_message += " -> failed"
								warnings.append(cache_result['warning'])
						else:
							if(not validate_email(contact_email,check_mx=True)):
								log_message += " -> failed"
								warning = DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Email for contact seems to be unreachable because of missing DNS MX record")
								warnings.append(warning)
								cache[contact_email] = { 'valid' : False, 'warning' : warning }
							else:
								log_message += " -> OK"
								cache[contact_email] = { 'valid' : True, 'warning' : None }
						log.info(log_message)
					except (DNS.Base.TimeoutError, DNS.Base.ServerError, DNS.Base.SocketError) as e:
						log_message += " -> failed with exception (" + str(e) + ")"
						log.error(log_message)

			if(not 'phone' in contact or re.search('^\s*$', contact['phone'])):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Missing phone for contact ('phone' attribute is empty'"))
			elif(not re.search('^\+(?:[0-9]??){6,14}[0-9]$', contact['phone'])):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Phone number for contact does not conform to the E.123 international standard (means starts with + sign, no spaces) - offending phone number in 'phone' attribute: " + contact['phone']))
		return warnings
