# vim:ts=4:sw=4:tw=0:sts=4:et

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

    def __init__(self, dataCheckID : str, recipients : str, NN : str, level : DataCheckWarningLevel, directoryEntityID : str, directoryEntityType : DataCheckEntityType, directoryEntityWithdrawn : str, message : str, action : str = '', emailTo : str = ''):
        self.dataCheckID = dataCheckID
        self.recipients = recipients
        self.NN = NN
        self.level = level
        self.directoryEntityID = directoryEntityID
        self.directoryEntityType = directoryEntityType
        self.directoryEntityWithdrawn = directoryEntityWithdrawn
        self.message = message
        self.action = action
        self.emailTo = emailTo
    
    def dump(self):
        print(self.directoryEntityType.value + " " + self.directoryEntityID + " " + self.dataCheckID + "/" + self.level.name + ": " + self.message + " " + self.action + " " + self.emailTo)



