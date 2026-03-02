# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin

from customwarnings import DataCheckEntityType, DataCheckWarning, DataCheckWarningLevel
from text_consistency import build_text_consistency_findings

CHECK_DOCS = {
	'TXT:AgeRange': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.age_high', 'COLLECTION.age_low', 'COLLECTION.description', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests an age group that does not match the structured age range.',
		'fix': 'Align the age_low/age_high metadata with the narrative description, or reword the narrative if the collection is broader than the text suggests.',
	},
	'TXT:StudyType': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.name', 'COLLECTION.type'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests a study-design concept that is missing from the structured collection type.',
		'fix': 'Review the collection name/description and add the relevant structured type such as PROSPECTIVE_COLLECTION, LONGITUDINAL, or CASE_CONTROL when appropriate.',
	},
	'TXT:FFPEMaterial': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.materials', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text mentions FFPE/paraffin material but the structured materials do not include TISSUE_PARAFFIN_EMBEDDED.',
		'fix': 'Add the structured material if paraffin-embedded tissue is really stored, or clarify in the text when the mention only refers to slides, sections, images, or derived DNA/RNA from FFPE material.',
	},
	'TXT:CovidDiag': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.diagnosis_available', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests COVID-19 disease or post-/long-COVID focus, but the structured diagnosis metadata does not reflect that context.',
		'fix': 'Add the relevant structured diagnoses if the collection really targets COVID-19 or post-/long-COVID content (for example U07.* or U09.9), or reword the narrative to avoid misleading search results.',
	},
}


class TextConsistency(IPlugin):
	def check(self, dir, args):
		log.info('Running deterministic text consistency checks (TextConsistency)')
		warnings = []
		for collection in dir.getCollections():
			for finding in build_text_consistency_findings(collection):
				warnings.append(self._build_warning(dir, collection, finding))
		return warnings

	def _build_warning(self, dir, collection, finding):
		check_id = finding['check_id']
		if check_id == 'TXT:AgeRange':
			return DataCheckWarning(
				'TXT:AgeRange',
				'',
				dir.getCollectionNN(collection['id']),
				DataCheckWarningLevel.WARNING,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(dir.isCollectionWithdrawn(collection['id'])),
				finding['message'],
				finding['action'],
			)
		if check_id == 'TXT:StudyType':
			return DataCheckWarning(
				'TXT:StudyType',
				'',
				dir.getCollectionNN(collection['id']),
				DataCheckWarningLevel.WARNING,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(dir.isCollectionWithdrawn(collection['id'])),
				finding['message'],
				finding['action'],
			)
		if check_id == 'TXT:FFPEMaterial':
			return DataCheckWarning(
				'TXT:FFPEMaterial',
				'',
				dir.getCollectionNN(collection['id']),
				DataCheckWarningLevel.WARNING,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(dir.isCollectionWithdrawn(collection['id'])),
				finding['message'],
				finding['action'],
			)
		if check_id == 'TXT:CovidDiag':
			return DataCheckWarning(
				'TXT:CovidDiag',
				'',
				dir.getCollectionNN(collection['id']),
				DataCheckWarningLevel.WARNING,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(dir.isCollectionWithdrawn(collection['id'])),
				finding['message'],
				finding['action'],
			)
		raise ValueError(f'Unsupported TextConsistency check_id {check_id!r}.')
