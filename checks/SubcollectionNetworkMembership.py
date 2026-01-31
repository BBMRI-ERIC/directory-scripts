# vim:ts=8:sw=8:tw=0:noet
"""Plugin to check that subcollections belong to the same network as their parent collections"""

import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id
from directory import Directory


class SubcollectionNetworkMembership(IPlugin):
    """Check whether subcollections belong to the same network as their parent collections"""

    def check(self, directory: Directory, _):
        """Do the actual checking"""
        warnings = []
        log.info("Running subcollection network membership checks (SubcollectionNetworkMembership)")
        for collection in directory.getCollections():
            if "parent_collection" in collection:
                # Is a subcollection
                parent_id = collection["parent_collection"]["id"]
                parent = directory.getCollectionById(parent_id)
                if "network" in parent:
                    # Parent collection is member of one or more networks
                    for network in parent["network"]:
                        if "network" not in collection or network not in collection["network"]:
                            warnings.append(
                                DataCheckWarning(
                                    make_check_id(self, "SubcollectionPartNetworkNetwork"),
                                    "",
                                    directory.getCollectionNN(collection["id"]),
                                    DataCheckWarningLevel.WARNING,
                                    collection["id"],
                                    DataCheckEntityType.COLLECTION,
                                    str(collection["withdrawn"]),
                                    f"Subcollection is not part of network {network['id']},"
                                    f" even though parent collection {parent_id} is.",
                                )
                            )
        return warnings
