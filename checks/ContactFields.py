import re
from yapsy.IPlugin import IPlugin
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
		return warnings
