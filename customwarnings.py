# vim:ts=4:sw=4:tw=0:sts=4:et

"""Define data-quality warning identifiers, levels, entities, and records."""

from enum import Enum

# Definition of warnings 

class DataCheckWarningLevel(Enum):
    """Enumerate warning severities used by data-quality check output."""
    ERROR = 1
    WARNING = 2
    INFO = 3

class DataCheckEntityType(Enum):
    """Enumerate Directory entity labels emitted in warnings and reports."""
    BIOBANK = 'Biobank'
    COLLECTION = 'Collection'
    CONTACT = 'Contact'
    NETWORK = 'Network'

class DataCheckWarning:
    """Store one data-quality warning and its optional machine-readable fixes.

    Attributes:
        dataCheckID: Stable visible check identifier.
        recipients: Comma-separated routing-recipient string.
        NN: National-node or staging-area code.
        level: Warning severity enum.
        directoryEntityID: Affected Directory entity identifier.
        directoryEntityType: Affected Directory entity type enum.
        directoryEntityWithdrawn: Stored withdrawal state for report consumers.
        message: Human-readable problem description.
        action: Optional remediation text.
        emailTo: Optional direct email recipient text.
        fix_proposals: Independently owned list of attached update proposals.
    """
    def __init__(self, dataCheckID : str, recipients : str, NN : str, level : DataCheckWarningLevel, directoryEntityID : str, directoryEntityType : DataCheckEntityType, directoryEntityWithdrawn : str, message : str, action : str = '', emailTo : str = '', fix_proposals = None):
        """Initialize a warning record, copying any supplied fix proposals.

        Args:
            dataCheckID: Stable check identifier, normally a prefix and suffix.
            recipients: Comma-separated recipient routing string for the warning.
            NN: National-node or staging-area code associated with the entity.
            level: Severity enum to display and export.
            directoryEntityID: Identifier of the affected Directory entity.
            directoryEntityType: Entity kind whose enum value labels output.
            directoryEntityWithdrawn: Withdrawal state retained for report consumers.
            message: Human-readable description of the detected problem.
            action: Optional suggested remediation text.
            emailTo: Optional direct email recipient text.
            fix_proposals: Optional iterable of update proposals. Its items are copied
                into a new list, so later list mutations by the caller do not affect
                this record.
        """
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
        self.fix_proposals = list(fix_proposals or [])
    
    def dump(self):
        """Print a compact one-line rendering of this warning to standard output.

        Returns:
            None. This has the side effect of writing directly to stdout.
        """
        print(self.directoryEntityType.value + " " + self.directoryEntityID + " " + self.dataCheckID + "/" + self.level.name + ": " + self.message + " " + self.action + " " + self.emailTo)


def make_check_id(plugin, suffix: str) -> str:
    """Build a stable check ID from a plugin prefix and an optional suffix.

    Args:
        plugin: Prefix string, plugin instance, or plugin class. Non-string inputs
            use `CHECK_ID_PREFIX` on the object then its class, falling back to the
            class name.
        suffix: Optional specific rule suffix. A falsey value leaves the prefix bare.

    Returns:
        Prefix alone, or `prefix:suffix` when `suffix` is truthy.
    """
    if isinstance(plugin, str):
        plugin_name = plugin
    else:
        plugin_name = getattr(plugin, "CHECK_ID_PREFIX", None)
        if not plugin_name:
            plugin_name = getattr(plugin.__class__, "CHECK_ID_PREFIX", None)
        if not plugin_name:
            plugin_name = plugin.__class__.__name__
    if not suffix:
        return plugin_name
    return f"{plugin_name}:{suffix}"
