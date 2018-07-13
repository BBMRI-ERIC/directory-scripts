import re

from yapsy.IPlugin import IPlugin
from validate_email import validate_email

from customwarnings import WarningLevel,Warning

class CheckContactFields(IPlugin):
	def check(self, dir):
		warnings = []
		for contact in dir.getContacts():
			if(not 'first_name' in contact or re.search('^\s*$', contact['first_name'])):
				warning = Warning("", dir.getContactNN(contact['id']), WarningLevel.WARNING, "Missing first name for contact " + contact['id'])
				warnings.append(warning)
			if(not 'last_name' in contact or re.search('^\s*$', contact['last_name'])):
				warning = Warning("", dir.getContactNN(contact['id']), WarningLevel.WARNING, "Missing last name for contact " + contact['id'])
				warnings.append(warning)
			if(not 'email' in contact or re.search('^\s*$', contact['email'])):
				warning = Warning("", dir.getContactNN(contact['id']), WarningLevel.ERROR, "Missing email for contact " + contact['id'])
				warnings.append(warning)
			elif(not validate_email(contact['email'])):
				warning = Warning("", dir.getContactNN(contact['id']), WarningLevel.WARNING, "Email for contact " + contact['id'] + " is invalid " + contact['email'])
				warnings.append(warning)
			# This is pretty dramatic test and should be used sparingly
			#if(not validate_email(contact['email'],verify=True)):
				#warning = Warning("", dir.getContactNN(contact['id']), WarningLevel.WARNING, "Email for contact " + contact['id'] + " is invalid")
				#warnings.append(warning)
		return warnings
