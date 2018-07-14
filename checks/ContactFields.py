import re

from yapsy.IPlugin import IPlugin
from validate_email import validate_email

from customwarnings import DataCheckWarningLevel,DataCheckWarning

class CheckContactFields(IPlugin):
	def check(self, dir):
		warnings = []
		for contact in dir.getContacts():
			if(not 'first_name' in contact or re.search('^\s*$', contact['first_name'])):
				warning = DataCheckWarning("", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, "Missing first name for contact " + contact['id'])
				warnings.append(warning)
			if(not 'last_name' in contact or re.search('^\s*$', contact['last_name'])):
				warning = DataCheckWarning("", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, "Missing last name for contact " + contact['id'])
				warnings.append(warning)
			if(not 'email' in contact or re.search('^\s*$', contact['email'])):
				warning = DataCheckWarning("", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, "Missing email for contact " + contact['id'])
				warnings.append(warning)
			elif(not validate_email(contact['email'])):
				warning = DataCheckWarning("", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, "Email for contact " + contact['id'] + " is invalid " + contact['email'])
				warnings.append(warning)
			# This is pretty dramatic test and should be used sparingly
			#if(not validate_email(contact['email'],verify=True)):
				#warning = DataCheckWarning("", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, "Email for contact " + contact['id'] + " is invalid")
				#warnings.append(warning)
			if(not 'phone' in contact or re.search('^\s*$', contact['phone'])):
				warning = DataCheckWarning("", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, "Missing phone for contact " + contact['id'])
				warnings.append(warning)
			elif(not re.search('^\+(?:[0-9]??){6,14}[0-9]$', contact['phone'])):
				warning = DataCheckWarning("", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, "Phone number for contact " + contact['id'] + " does not conform to the E.123 international standard " + contact['phone'])
				warnings.append(warning)
		return warnings
