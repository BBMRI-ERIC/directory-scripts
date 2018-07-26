import re
import logging as log

from yapsy.IPlugin import IPlugin
from validate_email import validate_email

from customwarnings import DataCheckWarningLevel,DataCheckWarning

class ContactFields(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running contact fields checks (ContactFields)")
		ValidateEmails = True
		if 'emails' in args.disableChecksRemote:
			ValidateEmails = False
		else:
			ValidateEmails = True
		for contact in dir.getContacts():
			if(not 'first_name' in contact or re.search('^\s*$', contact['first_name'])):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], "Missing first name for contact")
				warnings.append(warning)
			if(not 'last_name' in contact or re.search('^\s*$', contact['last_name'])):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], "Missing last name for contact")
				warnings.append(warning)
			if(not 'email' in contact or re.search('^\s*$', contact['email'])):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, contact['id'], "Missing email for contact")
				warnings.append(warning)
			elif(not validate_email(contact['email'])):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], "Email for contact is invalid " + contact['email'])
				warnings.append(warning)
			else:
				# This is pretty dramatic test and should be used sparingly
				if ValidateEmails:
					print("Validating email " + contact['email'], end=' ')
					# XXX: does not work in most cases
					#if(not validate_email(contact['email'],verify=True)):
					if(not validate_email(contact['email'],check_mx=True)):
						print(" -> failed")
						warning = DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], "Email for contact seems to be unreachable because of missing DNS MX record")
						warnings.append(warning)
					else:
						print(" -> OK")
			if(not 'phone' in contact or re.search('^\s*$', contact['phone'])):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], "Missing phone for contact")
				warnings.append(warning)
			elif(not re.search('^\+(?:[0-9]??){6,14}[0-9]$', contact['phone'])):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, contact['id'], "Phone number for contact does not conform to the E.123 international standard " + contact['phone'])
				warnings.append(warning)
		return warnings
