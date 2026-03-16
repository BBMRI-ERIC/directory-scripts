from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json


MODULE_PATH = Path(__file__).resolve().parents[1] / "survey-so2-directory.py"


def load_module():
    spec = spec_from_file_location("survey_so2_directory", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_mapping(tmp_path: Path) -> Path:
    payload = {
        "survey": {
            "file": "survey.xlsx",
            "sheet": "Content",
            "header_row": 4,
        },
        "entity_resolution": [],
        "field_mappings": [],
        "value_maps": {
            "sample_types_to_materials": {
                "Whole Blood": ["WHOLE_BLOOD"],
            }
        },
    }
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_objectives_mapping(tmp_path: Path) -> Path:
    payload = {
        "strategic_objectives": {
            "SO2.1": {"title": "Datafication at source", "description": "x"},
            "SO2.4": {"title": "Expand the Federated Platform", "description": "y"},
            "SO2.5": {"title": "On-demand accessible data generation", "description": "z"},
        },
        "question_mappings": [
            {
                "survey_field": "Are you interested in promoting your biobank resources to new partners?",
                "strategic_objectives": ["SO2.4"],
            },
            {
                "survey_field": "Are you interested in promoting your biobank resources to new research or industry partners?",
                "strategic_objectives": ["SO2.4"],
            },
            {
                "survey_field": "Which types of samples do you manage?",
                "strategic_objectives": ["SO2.1"],
            },
            {
                "survey_field": "Sample types",
                "strategic_objectives": ["SO2.1"],
            },
            {
                "survey_field": "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?",
                "strategic_objectives": ["SO2.5"],
            },
            {
                "survey_field": "You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):",
                "strategic_objectives": ["SO2.5"],
            },
        ],
    }
    path = tmp_path / "objectives-mapping.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_survey(tmp_path: Path) -> Path:
    row = {
        "Name": "Test Person",
        "Role": "Manager",
        "E-Mail address": "contact@example.org",
        "Name of Institution": "Demo Biobank",
        "BiobankID in the Directory (if available)": "bbmri-eric:ID:CZ_demo",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "bbmri-eric:ID:CZ_demo:collection:col1",
        "Country": "Czech Republic",
        "Are you interested in promoting your biobank resources to new partners?": "Yes - academic",
        "Which types of samples do you manage?": "Whole Blood",
        "Sample types": "",
        "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?": "Yes — access to internally generated WSI data collections",
        "You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):": "",
    }
    path = tmp_path / "survey.xlsx"
    with __import__("pandas").ExcelWriter(path) as writer:
        __import__("pandas").DataFrame([row]).to_excel(writer, sheet_name="Content", index=False, startrow=3)
    return path


class DirectoryStub:
    def __init__(self, *args, **kwargs):
        self.schema = kwargs.get("schema", "ERIC")
        self._biobank = {
            "id": "bbmri-eric:ID:CZ_demo",
            "name": "Demo Biobank",
            "country": "CZ",
            "contact": {"id": "bbmri-eric:contactID:CZ_demo_1"},
            "collaboration_non_for_profit": False,
            "collaboration_commercial": False,
        }
        self._collection = {
            "id": "bbmri-eric:ID:CZ_demo:collection:col1",
            "biobank": {"id": "bbmri-eric:ID:CZ_demo"},
            "contact": {"id": "bbmri-eric:contactID:CZ_demo_1"},
            "materials": "",
            "type": "",
            "data_categories": "",
            "description": "",
            "imaging_modality": "",
            "image_dataset_type": "",
        }
        self._contact = {
            "id": "bbmri-eric:contactID:CZ_demo_1",
            "email": "contact@example.org",
            "full_name": "Test Person",
        }

    def getSchema(self):
        return self.schema

    def getBiobanks(self):
        return [self._biobank]

    def getCollections(self):
        return [self._collection]

    def getBiobankById(self, biobank_id):
        return self._biobank if biobank_id == self._biobank["id"] else None

    def getCollectionById(self, collection_id):
        return self._collection if collection_id == self._collection["id"] else None

    def getContacts(self):
        return [self._contact]

    def getGraphBiobankCollectionsFromBiobank(self, biobank_id):
        import networkx as nx
        graph = nx.DiGraph()
        graph.add_node(self._biobank["id"])
        graph.add_node(self._collection["id"])
        graph.add_edge(self._biobank["id"], self._collection["id"])
        return graph

    def getContact(self, contact_id):
        return self._contact


def test_survey_so2_analyze_generates_findings_and_proposed_updates(tmp_path, monkeypatch):
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey(tmp_path)
    output_json = tmp_path / "report.json"

    monkeypatch.setattr(module, "Directory", DirectoryStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        verbose=False,
        debug=False,
        username=None,
        password=None,
        token=None,
        schema="ERIC",
        directory_target=None,
    )

    result = module.run_analyze(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["summary"]["survey_rows"] == 1
    assert "strategic_objectives" in payload
    proposed = [finding for finding in payload["findings"] if finding.get("proposed_update")]
    assert {finding["mapping_id"] for finding in proposed} == {
        "promotion.partnership_interest",
        "sample_types.materials",
        "imaging.wsi_presence",
    }
    assert any(finding["strategic_objectives"] for finding in payload["findings"])


def test_survey_so2_export_update_plan_keeps_biobank_and_collection_updates(tmp_path):
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "findings": [
            {
                "export_update_plan": True,
                "proposed_update": {
                    "update_id": "survey_so2.biobank.collaboration_non_profit",
                    "module": "SO2",
                    "entity_type": "BIOBANK",
                    "entity_id": "bbmri-eric:ID:CZ_demo",
                    "field": "collaboration_non_for_profit",
                    "mode": "set",
                    "confidence": "uncertain",
                    "current_value_at_export": False,
                    "expected_current_value": False,
                    "proposed_value": True,
                    "human_explanation": "x",
                    "rationale": "r",
                    "term_explanations": [],
                    "source_check_ids": ["SO2:PromotionInterest"],
                    "source_warning_messages": [],
                    "source_warning_actions": [],
                    "replace_required": False,
                    "blocking_reason": "",
                    "exclusive_group": "",
                    "staging_area": "CZ",
                    "update_checksum": "x",
                },
            },
            {
                "export_update_plan": True,
                "proposed_update": {
                    "update_id": "survey_so2.collection.materials_from_sample_types",
                    "module": "SO2",
                    "entity_type": "COLLECTION",
                    "entity_id": "bbmri-eric:ID:CZ_demo:collection:col1",
                    "field": "materials",
                    "mode": "append",
                    "confidence": "uncertain",
                    "current_value_at_export": [],
                    "expected_current_value": [],
                    "proposed_value": ["WHOLE_BLOOD"],
                    "human_explanation": "x",
                    "rationale": "r",
                    "term_explanations": [],
                    "source_check_ids": ["SO2:SampleTypes"],
                    "source_warning_messages": [],
                    "source_warning_actions": [],
                    "replace_required": False,
                    "blocking_reason": "",
                    "exclusive_group": "",
                    "staging_area": "CZ",
                    "update_checksum": "x",
                },
            },
        ],
    }
    input_path = tmp_path / "report.json"
    output_path = tmp_path / "updates.json"
    input_path.write_text(json.dumps(report), encoding="utf-8")

    args = Namespace(input_json=str(input_path), output_json=str(output_path), min_confidence="uncertain")
    result = module.run_export_update_plan(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert {update["entity_type"] for update in payload["updates"]} == {"BIOBANK", "COLLECTION"}


def test_survey_so2_render_report_writes_tex_and_pdf(tmp_path, monkeypatch):
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "findings": [],
    }
    input_path = tmp_path / "report.json"
    tex_path = tmp_path / "report.tex"
    pdf_path = tmp_path / "report.pdf"
    input_path.write_text(json.dumps(report), encoding="utf-8")

    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/xelatex")

    def fake_run(cmd, cwd, check, stdout, stderr, text):
        Path(cwd, "report.pdf").write_bytes(b"%PDF-1.4\\n")
        class Result:
            stdout = ""
        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    args = Namespace(input_json=str(input_path), output_tex=str(tex_path), output_pdf=str(pdf_path), verbose=False, debug=False)
    result = module.run_render(args)

    assert result == module.EXIT_OK
    assert tex_path.exists()
    assert pdf_path.exists()


def test_survey_so2_render_tex_escapes_special_characters():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "findings": [
            {
                "status": "manual_review",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:NL_LUMC",
                "explanation": "Survey country NL conflicts with biobank name Demo_1 & needs manual review.",
            }
        ],
    }

    tex = module.render_tex(report)

    assert r"NL\_\allowbreak{}LUMC" in tex
    assert r"Demo\_1 \& needs manual review." in tex
    assert r"NL\\_LUMC" not in tex


def test_survey_so2_render_tex_includes_biobank_grouped_summary():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 2, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 1},
        "row_resolutions": [
            {
                "survey_row": 6,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col1"],
            },
            {
                "survey_row": 7,
                "institution_name": "Demo Biobank follow-up",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col2"],
            },
        ],
        "findings": [
            {
                "status": "consistent",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Country matches.",
                "proposed_update": None,
            },
            {
                "status": "inconsistent",
                "survey_row": 7,
                "mapping_id": "sample_types.materials",
                "entity_type": "COLLECTION",
                "entity_id": "bbmri-eric:ID:CZ_demo:collection:col2",
                "explanation": "Materials mismatch.",
                "proposed_update": {"update_id": "x"},
            },
        ],
    }

    tex = module.render_tex(report)

    assert "Biobank-Oriented Summary" in tex
    assert "bbmri-eric:ID:CZ\\_demo (2 survey answers)" in tex
    assert "Survey row 6: Demo Biobank" in tex
    assert "Survey row 7: Demo Biobank follow-up" in tex
    assert r"\textcolor{soGreen}{Consistent}" in tex
    assert r"\hyperref[appendix-geo-country]{geo.\allowbreak{}country (appendix)}" in tex
    assert r"\textcolor{soRed}{Inconsistent}" in tex
    assert r"\hyperref[appendix-sample-types-materials]{sample\_\allowbreak{}types.\allowbreak{}materials (appendix)}" in tex
    assert "[proposed update]" in tex


def test_survey_so2_render_tex_includes_objective_summary():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 1},
        "strategic_objectives": {
            "SO2.4": {"title": "Expand the Federated Platform", "description": "Platform onboarding and discovery."},
        },
        "row_resolutions": [
            {
                "survey_row": 6,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": [],
            }
        ],
        "findings": [
            {
                "status": "inconsistent",
                "survey_row": 6,
                "mapping_id": "promotion.partnership_interest",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Promotion interest differs.",
                "strategic_objectives": ["SO2.4"],
                "proposed_update": {"update_id": "x"},
            }
        ],
    }

    tex = module.render_tex(report)

    assert "Strategic-Objective Summary" in tex
    assert "SO2.4 - Expand the Federated Platform" in tex
    assert "Per biobank" in tex
    assert "bbmri-eric:ID:CZ\\_demo" in tex
    assert "promotion.partnership\\_interest" in tex


def test_survey_so2_render_tex_keeps_empty_objectives_in_toc():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "strategic_objectives": {
            "SO2.2": {"title": "Traceability and quality management", "description": "Traceability objective."},
            "SO2.6": {"title": "Capacities to host result data", "description": "Return-data hosting objective."},
        },
        "row_resolutions": [],
        "findings": [],
    }

    tex = module.render_tex(report)

    assert r"\subsection{SO2.2 - Traceability and quality management}" in tex
    assert r"\subsection{SO2.6 - Capacities to host result data}" in tex
    assert "No findings were mapped to this strategic objective in the current report." in tex


def test_survey_so2_render_tex_uses_appendix_and_detailed_inconsistent_values():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 2, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "strategic_objectives": {},
        "row_resolutions": [
            {
                "survey_row": 6,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": [],
            },
            {
                "survey_row": 7,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": [],
            },
        ],
        "findings": [
            {
                "status": "consistent",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Country matches.",
                "why_relevant": "Country validates the mapping.",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": ["Country"],
                "strategic_objectives": [],
                "survey_value": "CZ",
                "directory_value": "CZ",
                "proposed_update": None,
            },
            {
                "status": "inconsistent",
                "survey_row": 7,
                "mapping_id": "sample_types.materials",
                "entity_type": "COLLECTION",
                "entity_id": "bbmri-eric:ID:CZ_demo:collection:col1",
                "explanation": "Materials differ.",
                "why_relevant": "Sample types should align with materials.",
                "relation_type": "controlled_vocabulary_mapping",
                "reliability": "medium",
                "survey_fields": ["Which types of samples do you manage?"],
                "strategic_objectives": ["SO2.1"],
                "survey_value": {"expected_materials": ["WHOLE_BLOOD"]},
                "directory_value": {"observed_materials": []},
                "proposed_update": None,
            },
        ],
    }

    tex = module.render_tex(report)

    assert r"\section{Finding-Type Reference}" in tex
    assert tex.count(r"geo.country\label{appendix-geo-country}") == 1
    assert tex.count(r"sample\_types.materials\label{appendix-sample-types-materials}") == 1
    assert r"\hyperref[appendix-geo-country]{geo.\allowbreak{}country (appendix)}" in tex
    assert r"\hyperref[appendix-sample-types-materials]{sample\_\allowbreak{}types.\allowbreak{}materials (appendix)}" in tex
    assert "Consistent." in tex
    assert r"Survey=WHOLE\_BLOOD; Directory=<empty>." in tex


def test_survey_so2_render_tex_breaks_entity_identifiers():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "inconsistent",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "COLLECTION",
                "entity_id": "bbmri-eric:ID:NL_LUMC:collection:CRC.Cohort-1",
                "explanation": "Country differs.",
                "why_relevant": "x",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": ["Country"],
                "strategic_objectives": [],
                "survey_value": "NL",
                "directory_value": "DE",
                "proposed_update": None,
            }
        ],
    }

    tex = module.render_tex(report)

    assert r"COLLECTION bbmri-\allowbreak{}eric:\allowbreak{}ID:\allowbreak{}NL\_\allowbreak{}LUMC:\allowbreak{}collection:\allowbreak{}CRC.\allowbreak{}Cohort-\allowbreak{}1" in tex


def test_survey_so2_render_tex_uses_status_colors():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "inconsistent",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Country differs.",
                "why_relevant": "x",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": ["Country"],
                "strategic_objectives": [],
                "survey_value": "CZ",
                "directory_value": "DE",
                "proposed_update": None,
            }
        ],
    }

    tex = module.render_tex(report)

    assert r"\usepackage[table]{xcolor}" in tex
    assert r"\definecolor{soRed}{HTML}{9E2A2B}" in tex
    assert r"\textcolor{soRed}{Inconsistent}" in tex


def test_survey_so2_render_tex_includes_toc_and_clearpage_after_title():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 0, "resolved_rows": 0, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [],
    }

    tex = module.render_tex(report)

    assert r"\maketitle" in tex
    assert r"\tableofcontents" in tex
    assert r"\clearpage" in tex
    assert tex.index(r"\maketitle") < tex.index(r"\tableofcontents") < tex.index(r"\clearpage") < tex.index(r"\section{Summary}")
