from enum import Enum

# Definition of warnings 

class DataCheckWarningLevel(Enum):
	ERROR = 1
	WARNING = 2
	INFO = 3

class DataCheckWarning:

	def __init__(self, dataCheckID : str, recipients : str, NN : str, level : DataCheckWarningLevel, directoryEntityID : str, message : str):
		self.dataCheckID = dataCheckID
		self.recipients = recipients
		self.NN = NN
		self.level = level
		self.directoryEntityID = directoryEntityID
		self.message = message
	
	def dump(self):
		print(self.directoryEntityID + " " + self.dataCheckID + "/" + self.level.name + ": " + self.message)


