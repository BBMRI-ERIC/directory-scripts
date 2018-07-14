from enum import Enum

# Definition of warnings 

class DataCheckWarningLevel(Enum):
	ERROR = 1
	WARNING = 2
	INFO = 3

class DataCheckWarning:

	def __init__(self, recipients, NN, level : DataCheckWarningLevel, message):
		self.recipients = recipients
		self.NN = NN
		self.level = level
		self.message = message
	
	def dump(self):
		print("=="+str(self.level)+"== "+self.message)


