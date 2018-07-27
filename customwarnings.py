from enum import Enum

# Definition of warnings 

class DataCheckWarningLevel(Enum):
	ERROR = 1
	WARNING = 2
	INFO = 3

class DataCheckEntityType(Enum):
	BIOBANK = 'Biobank'
	COLLECTION = 'Collection'
	CONTACT = 'Contact'
	NETWORK = 'Network'

class DataCheckWarning:

	def __init__(self, dataCheckID : str, recipients : str, NN : str, level : DataCheckWarningLevel, directoryEntityID : str, directoryEntityType : DataCheckEntityType, message : str):
		self.dataCheckID = dataCheckID
		self.recipients = recipients
		self.NN = NN
		self.level = level
		self.directoryEntityID = directoryEntityID
		self.directoryEntityType = directoryEntityType
		self.message = message
	
	def dump(self):
		print(self.directoryEntityType.value + " " + self.directoryEntityID + " " + self.dataCheckID + "/" + self.level.name + ": " + self.message)


