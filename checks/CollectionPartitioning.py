# vim:ts=8:sw=8:tw=0:noet

import logging as log

from fact_sheet_utils import analyze_collection_fact_sheet
from yapsy.IPlugin import IPlugin

from customwarnings import (
	DataCheckEntityType,
	DataCheckWarning,
	DataCheckWarningLevel,
	make_check_id,
)

CHECK_ID_PREFIX = 'CP'


CHECK_DOCS = {
	'CP:SizeOver': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.size', 'COLLECTION.sub_collection'],
		'severity': 'ERROR',
		'summary': 'The sum of direct subcollection sizes exceeds the parent collection size.',
		'fix': 'Review the parent collection size and the exact child sizes. Subcollections may cover only part of the parent, but their total must never exceed the parent total.',
	},
	'CP:DonorOver': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.number_of_donors', 'COLLECTION.sub_collection'],
		'severity': 'ERROR',
		'summary': 'The sum of direct subcollection donor counts exceeds the parent collection number_of_donors.',
		'fix': 'Review the parent donor count and the exact child donor counts. Subcollections may be incomplete, but their donor total must never exceed the parent total.',
	},
	'CP:SizeUnknown': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.size', 'COLLECTION.sub_collection'],
		'severity': 'WARNING',
		'summary': 'The parent collection size cannot be fully checked because one or more direct subcollections have no exact size.',
		'fix': 'Add missing exact child sizes or confirm that the partitioning can only be checked at the order-of-magnitude level.',
	},
	'CP:DonorUnknown': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.number_of_donors', 'COLLECTION.sub_collection'],
		'severity': 'WARNING',
		'summary': 'The parent collection donor count cannot be fully checked because one or more direct subcollections have no exact number_of_donors.',
		'fix': 'Add missing exact child donor counts or confirm that the donor partitioning cannot be checked exactly.',
	},
	'CP:FactSizeOver': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.facts', 'COLLECTION.sub_collection'],
		'severity': 'ERROR',
		'summary': 'The sum of direct subcollection all-star fact-sheet sample totals exceeds the parent all-star fact-sheet sample total.',
		'fix': 'Review the all-star fact rows on the parent and its direct subcollections. Child fact-sheet totals must never exceed the parent total.',
	},
	'CP:FactDonorOver': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.facts', 'COLLECTION.sub_collection'],
		'severity': 'ERROR',
		'summary': 'The sum of direct subcollection all-star fact-sheet donor totals exceeds the parent all-star fact-sheet donor total.',
		'fix': 'Review the all-star donor totals on the parent and its direct subcollections. Child fact-sheet totals must never exceed the parent total.',
	},
	'CP:FactSizeUnknown': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.facts', 'COLLECTION.sub_collection'],
		'severity': 'WARNING',
		'summary': 'The parent fact-sheet sample total cannot be fully checked because one or more direct subcollections have no valid all-star sample total.',
		'fix': 'Add or fix the missing all-star fact rows on the affected child collections.',
	},
	'CP:FactDonorUnknown': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.facts', 'COLLECTION.sub_collection'],
		'severity': 'WARNING',
		'summary': 'The parent fact-sheet donor total cannot be fully checked because one or more direct subcollections have no valid all-star donor total.',
		'fix': 'Add or fix the missing all-star fact rows on the affected child collections.',
	},
}


def _int_value(entity, key):
	value = entity.get(key)
	return value if isinstance(value, int) else None


def _warning_email(dir, collection_id):
	try:
		return dir.getCollectionContact(collection_id)['email']
	except Exception:
		return ''


def _append_partition_warning(warnings, dir, collection, suffix, level, message, action=''):
	if suffix == 'SizeOver':
		warnings.append(DataCheckWarning(make_check_id(CHECK_ID_PREFIX, 'SizeOver'), '', dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(dir.isCollectionWithdrawn(collection['id'])), message, action, _warning_email(dir, collection['id'])))
	elif suffix == 'DonorOver':
		warnings.append(DataCheckWarning(make_check_id(CHECK_ID_PREFIX, 'DonorOver'), '', dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(dir.isCollectionWithdrawn(collection['id'])), message, action, _warning_email(dir, collection['id'])))
	elif suffix == 'SizeUnknown':
		warnings.append(DataCheckWarning(make_check_id(CHECK_ID_PREFIX, 'SizeUnknown'), '', dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(dir.isCollectionWithdrawn(collection['id'])), message, action, _warning_email(dir, collection['id'])))
	elif suffix == 'DonorUnknown':
		warnings.append(DataCheckWarning(make_check_id(CHECK_ID_PREFIX, 'DonorUnknown'), '', dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(dir.isCollectionWithdrawn(collection['id'])), message, action, _warning_email(dir, collection['id'])))
	elif suffix == 'FactSizeOver':
		warnings.append(DataCheckWarning(make_check_id(CHECK_ID_PREFIX, 'FactSizeOver'), '', dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(dir.isCollectionWithdrawn(collection['id'])), message, action, _warning_email(dir, collection['id'])))
	elif suffix == 'FactDonorOver':
		warnings.append(DataCheckWarning(make_check_id(CHECK_ID_PREFIX, 'FactDonorOver'), '', dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(dir.isCollectionWithdrawn(collection['id'])), message, action, _warning_email(dir, collection['id'])))
	elif suffix == 'FactSizeUnknown':
		warnings.append(DataCheckWarning(make_check_id(CHECK_ID_PREFIX, 'FactSizeUnknown'), '', dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(dir.isCollectionWithdrawn(collection['id'])), message, action, _warning_email(dir, collection['id'])))
	elif suffix == 'FactDonorUnknown':
		warnings.append(DataCheckWarning(make_check_id(CHECK_ID_PREFIX, 'FactDonorUnknown'), '', dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(dir.isCollectionWithdrawn(collection['id'])), message, action, _warning_email(dir, collection['id'])))
	else:
		raise ValueError(f"Unsupported collection partitioning check suffix {suffix!r}.")

class CollectionPartitioning(IPlugin):
	CHECK_ID_PREFIX = 'CP'

	def check(self, dir, args):
		warnings = []
		log.info('Running collection partitioning checks (CollectionPartitioning)')
		for parent in dir.getCollections():
			children = dir.getDirectSubcollections(parent['id'])
			if not children:
				continue

			self._check_metric_partition(
				dir,
				parent,
				children,
				metric='size',
				over_suffix='SizeOver',
				missing_suffix='SizeUnknown',
				warnings=warnings,
			)
			self._check_metric_partition(
				dir,
				parent,
				children,
				metric='number_of_donors',
				over_suffix='DonorOver',
				missing_suffix='DonorUnknown',
				warnings=warnings,
			)
			self._check_fact_partition(
				dir,
				parent,
				children,
				metric='number_of_samples',
				over_suffix='FactSizeOver',
				missing_suffix='FactSizeUnknown',
				warnings=warnings,
			)
			self._check_fact_partition(
				dir,
				parent,
				children,
				metric='number_of_donors',
				over_suffix='FactDonorOver',
				missing_suffix='FactDonorUnknown',
				warnings=warnings,
			)
		return warnings

	def _check_metric_partition(self, dir, parent, children, metric, over_suffix, missing_suffix, warnings):
		parent_value = _int_value(parent, metric)
		if parent_value is None:
			return

		known_values = []
		missing_children = []
		for child in children:
			child_value = _int_value(child, metric)
			if child_value is None:
				missing_children.append(child['id'])
			else:
				known_values.append((child['id'], child_value))

		known_sum = sum(value for _, value in known_values)
		if known_sum > parent_value:
			_append_partition_warning(
				warnings,
				dir,
				parent,
				over_suffix,
				DataCheckWarningLevel.ERROR,
				f"Direct subcollections exceed parent {metric}: parent={parent_value}, child_sum={known_sum}, children={[child_id for child_id, _ in known_values]}",
				f"Check the parent {metric} value and the exact values of its direct subcollections. Child totals must not exceed the parent total.",
			)
		elif missing_children:
			_append_partition_warning(
				warnings,
				dir,
				parent,
				missing_suffix,
				DataCheckWarningLevel.WARNING,
				f"Cannot fully verify parent {metric} because direct subcollections are missing exact values: {missing_children}",
				f"Add exact {metric} values to the listed direct subcollections to verify that their total stays within the parent total.",
			)

	def _check_fact_partition(self, dir, parent, children, metric, over_suffix, missing_suffix, warnings):
		parent_fact_sheet = analyze_collection_fact_sheet(parent, dir.getCollectionFacts(parent['id']))
		parent_value = parent_fact_sheet.get(f'all_star_{metric}')
		if not isinstance(parent_value, int):
			return

		known_values = []
		missing_children = []
		for child in children:
			child_fact_sheet = analyze_collection_fact_sheet(child, dir.getCollectionFacts(child['id']))
			child_value = child_fact_sheet.get(f'all_star_{metric}')
			if not isinstance(child_value, int):
				missing_children.append(child['id'])
			else:
				known_values.append((child['id'], child_value))

		known_sum = sum(value for _, value in known_values)
		if known_sum > parent_value:
			_append_partition_warning(
				warnings,
				dir,
				parent,
				over_suffix,
				DataCheckWarningLevel.ERROR,
				f"Direct subcollection fact-sheet totals exceed parent all-star {metric}: parent={parent_value}, child_sum={known_sum}, children={[child_id for child_id, _ in known_values]}",
				"Check the parent and child all-star fact rows. Direct child fact-sheet totals must not exceed the parent total.",
			)
		elif missing_children:
			_append_partition_warning(
				warnings,
				dir,
				parent,
				missing_suffix,
				DataCheckWarningLevel.WARNING,
				f"Cannot fully verify parent fact-sheet {metric} because direct subcollections lack a valid all-star total: {missing_children}",
				"Add or correct the missing all-star fact rows on the listed direct subcollections.",
			)
