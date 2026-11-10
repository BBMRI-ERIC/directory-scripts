"""Report explicitly deprecated dataset and service terms with reviewed advice."""

from yapsy.IPlugin import IPlugin

from customwarnings import DataCheckEntityType, DataCheckWarning, DataCheckWarningLevel, make_check_id
from vocabulary_guidance import find_guidance
from vocabulary_status import advice_matches, deprecation_state, prepare_vocabulary_context, reference_column_issue


CHECK_DOCS = {
    "VOC:DeprecatedValue": {
        "entity": "COLLECTION, SERVICE",
        "dynamic_metadata": ["entity"],
        "fields": ["COLLECTION.data_categories", "SERVICE.serviceTypes"],
        "severity": "ERROR",
        "summary": "A collection dataset type or service type is explicitly deprecated in the available reference vocabulary. Retired values absent from that vocabulary are not classified as deprecated merely because an old snapshot contains them.",
        "fix": "Review the affected value and the Manual migration guidance. Select replacement terms only when supported by existing information; ask the data manager where additional information is needed. The API may still accept deprecated values. This check does not propose automatic updates.",
    }
}


class VocabularyStatus(IPlugin):
    """Check collection and service vocabulary status without changing records."""

    CHECK_ID_PREFIX = "VOC"

    def check(self, dir, args):
        """Return ERROR findings only for explicit current deprecation declarations.

        Args:
            dir: Loaded Directory view; selectors enforce configured withdrawal scope.
            args: Runner options for optional reference refresh, offline mode and guidance.

        Returns:
            Warning objects with no fix proposals, one per entity/field/deprecated term.
            Unsupported paths are skipped with shared nonfatal coverage diagnostics.
        """
        context = prepare_vocabulary_context(dir, args)
        snapshot = context.get("snapshot")
        if not snapshot:
            return []
        guidance = context.get("guidance")
        warnings = []
        for table, field, vocabulary, entity_type, selector, node_lookup in (
            ("Collections", "data_categories", "DataCategories", DataCheckEntityType.COLLECTION, dir.getCollections, dir.getCollectionNN),
            ("Services", "serviceTypes", "ServiceTypes", DataCheckEntityType.SERVICE, dir.getServices, dir.getServiceNN),
        ):
            issue = reference_column_issue(snapshot.get("schema_metadata", {}), table, field, vocabulary)
            if issue:
                context["diagnostics"].append("Vocabulary coverage reduced: " + issue + ".")
                continue
            rows = snapshot.get("ontologies", {}).get(vocabulary)
            if rows is None:
                context["diagnostics"].append(f"Vocabulary coverage reduced: {vocabulary} reference is unavailable.")
                continue
            reference = {row["name"]: row for row in rows}
            unknown = set()
            ambiguous = {row["name"] for row in rows if deprecation_state(row.get("definition")) == "unverified"}
            if ambiguous:
                context["diagnostics"].append(f"Review {vocabulary} deprecation wording for: {', '.join(sorted(ambiguous))}. No deprecation errors are inferred from ambiguous wording.")
            for entity in selector():
                raw = entity.get(field) or []
                if not isinstance(raw, list):
                    context["diagnostics"].append(f"Vocabulary coverage reduced: {entity['id']} has an unsupported {field} representation.")
                    continue
                names = {value.get("name") if isinstance(value, dict) else value for value in raw}
                for name in sorted(value for value in names if isinstance(value, str)):
                    term = reference.get(name)
                    if term is None:
                        unknown.add(name)
                        continue
                    if deprecation_state(term.get("definition")) != "deprecated":
                        continue
                    action = "Review the original information and choose supported replacement terms; do not infer more specific data or services from this value alone."
                    if guidance:
                        entries = [entry for entry in find_guidance(guidance, vocabulary, name)
                                   if advice_matches(entry, rows, guidance)]
                        if entries:
                            entry = entries[0]
                            action = " ".join(item["text"] for item in entry["actions"])
                            for option in entry["replacement_options"]:
                                conditions = " ".join(option["conditions"])
                                action += " Candidate: " + "; ".join(option["terms"]) + "."
                                if conditions:
                                    action += " Only if: " + conditions
                            if entry["information_needed"]:
                                action += " Clarify: " + " ".join(entry["information_needed"])
                            for section_id in entry["manual_section_ids"]:
                                section = guidance["manual_sections"][section_id]
                                action += f" Manual: {section['title']}"
                                if section["publication"] == "unpublished":
                                    action += " (updated section not yet published)."
                                else:
                                    action += " (https://zenodo.org/doi/10.5281/zenodo.2583446)."
                    if entity_type == DataCheckEntityType.SERVICE:
                        withdrawn = dir.isBiobankWithdrawn(dir.getServiceBiobankId(entity["id"]))
                    else:
                        withdrawn = dir.isCollectionWithdrawn(entity["id"])
                    warnings.append(DataCheckWarning(
                        make_check_id(self, "DeprecatedValue"), "", node_lookup(entity["id"]),
                        DataCheckWarningLevel.ERROR, entity["id"], entity_type, withdrawn,
                        f"{table}.{field} uses the deprecated value {name}. The API may still accept it, but it needs migration.",
                        action,
                    ))
            if unknown:
                context["diagnostics"].append(f"{vocabulary}: values absent from the available reference ({', '.join(sorted(unknown))}); check snapshot/reference versions before treating them as current data errors.")
        return warnings
