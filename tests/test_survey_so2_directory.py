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


def write_survey_row(tmp_path: Path, updates: dict[str, object] | None = None, *, filename: str = "survey.xlsx") -> Path:
    row = {
        "Name": "Test Person",
        "Role": "Manager",
        "E-Mail address": "contact@example.org",
        "Name of Institution": "Demo Biobank",
        "BiobankID in the Directory (if available)": "bbmri-eric:ID:CZ_demo",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "bbmri-eric:ID:CZ_demo:collection:col1",
        "Country": "Czech Republic",
        "Are you interested in promoting your biobank resources to new partners?": "",
        "Are you interested in promoting your biobank resources to new research or industry partners?": "",
        "Which types of samples do you manage?": "",
        "Sample types": "",
        "What is the approximate size of your biobank (number of samples aliquots)?": "",
        "Does your biobank provide access to radiology datasets?": "",
        "You can provide more information about available radiology pathology imaging data here (e.g., focus of the collections, more details on modalities):": "",
        "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?": "",
        "You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):": "",
        "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "",
        "Next-gen sequencing technology/vendor": "",
        "Radiology imaging technology/vendor": "",
        "Pathology imaging technology/vendor": "",
        "Proteomics technology/vendor": "",
        "Metabolomics technology/vendor": "",
        "Technologies": "",
    }
    if updates:
        row.update(updates)
    path = tmp_path / filename
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
            "data_use": [],
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

    def getNetworks(self):
        return []

    def getGraphBiobankCollectionsFromBiobank(self, biobank_id):
        import networkx as nx
        graph = nx.DiGraph()
        graph.add_node(self._biobank["id"])
        graph.add_node(self._collection["id"])
        graph.add_edge(self._biobank["id"], self._collection["id"])
        return graph

    def getContact(self, contact_id):
        return self._contact


class SwissResolutionDirectoryStub:
    def __init__(self):
        self._biobanks = [
            {"id": "bbmri-eric:ID:CH_UniversityOfBern", "name": "University of Bern", "country": "CH"},
            {"id": "bbmri-eric:ID:CH_Unige", "name": "Université de Genève", "country": "CH"},
            {"id": "bbmri-eric:ID:CH_HopitauxUniversitairesGeneve", "name": "Hôpitaux Universitaires Genève", "country": "CH"},
        ]
        self._collections = [
            {
                "id": "bbmri-eric:ID:CH_UniversityOfBern:collection:CH_VetSuisseBiobankVETGENBERN",
                "biobank": {"id": "bbmri-eric:ID:CH_UniversityOfBern"},
                "name": "VetSuisse Biobank, VET_GEN_BERN",
                "description": "Domestic animal samples.",
                "type": ["NON_HUMAN", "SAMPLE"],
                "materials": ["DNA", "WHOLE_BLOOD"],
                "contact": {"id": "contact-vet"},
            },
            {
                "id": "bbmri-eric:ID:CH_UniversityOfBern:collection:CH_TissueBiobankBern",
                "biobank": {"id": "bbmri-eric:ID:CH_UniversityOfBern"},
                "name": "Tissue Biobank Bern",
                "description": "Human pathology samples from Inselspital.",
                "type": ["DISEASE_SPECIFIC", "HOSPITAL"],
                "materials": ["TISSUE_FROZEN"],
                "contact": {"id": "contact-human"},
            },
            {
                "id": "bbmri-eric:ID:CH_Unige:collection:CH_FABER",
                "biobank": {"id": "bbmri-eric:ID:CH_Unige"},
                "name": "FABER",
                "description": "University of Geneva biomedical cohort.",
                "type": ["SAMPLE"],
                "materials": ["WHOLE_BLOOD"],
                "contact": {"id": "contact-unige"},
            },
            {
                "id": "bbmri-eric:ID:CH_HopitauxUniversitairesGeneve:collection:CH_AneuX",
                "biobank": {"id": "bbmri-eric:ID:CH_HopitauxUniversitairesGeneve"},
                "name": "AneuX",
                "description": "Hospital cohort in Geneva.",
                "type": ["SAMPLE"],
                "materials": ["SERUM"],
                "contact": {"id": "contact-hug"},
            },
        ]

    def getBiobanks(self):
        return list(self._biobanks)

    def getCollections(self):
        return list(self._collections)

    def getNetworks(self):
        return []

    def getGraphBiobankCollectionsFromBiobank(self, biobank_id):
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_node(biobank_id)
        for collection in self._collections:
            if collection["biobank"]["id"] == biobank_id:
                graph.add_node(collection["id"])
                graph.add_edge(biobank_id, collection["id"])
        return graph


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
        "promotion.partnership_interest.duo",
        "sample_types.materials",
        "imaging.wsi_presence",
    }
    duo_finding = next(finding for finding in proposed if finding["mapping_id"] == "promotion.partnership_interest.duo")
    assert duo_finding["proposed_update"]["field"] == "data_use"
    assert duo_finding["proposed_update"]["proposed_value"] == ["DUO:0000018"]
    assert any(finding["strategic_objectives"] for finding in payload["findings"])


def test_survey_so2_analyze_radiology_presence_and_explicit_size_bucket(tmp_path, monkeypatch):
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "What is the approximate size of your biobank (number of samples aliquots)?": "1000 - 10,000 aliquots",
            "Does your biobank provide access to radiology datasets?": "Yes — access to internally generated radiology data collections (e.g., directly connected to a PACS system)",
        },
        filename="radiology-size.xlsx",
    )
    output_json = tmp_path / "radiology-size-report.json"

    class DirectoryExplicitSizeStub(DirectoryStub):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._collection["size"] = 1500

    monkeypatch.setattr(module, "Directory", DirectoryExplicitSizeStub)

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
    size_finding = next(finding for finding in payload["findings"] if finding["mapping_id"] == "biobank_size.samples")
    assert size_finding["status"] == "consistent"
    assert size_finding["directory_value"]["explicit_total"] == 1500
    assert size_finding["directory_value"]["bucket"] == "1000 - 10,000 aliquots"
    radiology_finding = next(finding for finding in payload["findings"] if finding["mapping_id"] == "imaging.radiology_presence")
    assert radiology_finding["status"] == "missing_in_directory"
    assert radiology_finding["proposed_update"]["field"] == "type"
    assert radiology_finding["proposed_update"]["proposed_value"] == ["IMAGE"]




def test_survey_so2_analyze_outputs_technology_upset_artifacts(tmp_path, monkeypatch):
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": (
                "Next-gen sequencing (if yes, specify technology/vendor); "
                "Proteomics (if yes, specify technology/vendor); "
                "Other (please specify):"
            ),
            "Radiology imaging technology/vendor": "Siemens SOMATOM",
            "Technologies": "Mass cytometry",
        },
        filename="technology-upset.xlsx",
    )
    output_json = tmp_path / "technology-upset-report.json"
    upset_prefix = tmp_path / "so2-modalities"

    monkeypatch.setattr(module, "Directory", DirectoryStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        output_tech_upset_prefix=str(upset_prefix),
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
    technology_payload = payload["technology_modalities"]
    assert technology_payload["summary"]["modality_counts"]["sequencing"] == 1
    assert technology_payload["summary"]["modality_counts"]["genotyping_panels"] == 0
    assert technology_payload["summary"]["modality_counts"]["radiology"] == 1
    assert technology_payload["summary"]["modality_counts"]["proteomics"] == 1
    assert technology_payload["summary"]["modality_counts"]["other_technology"] == 1
    row = technology_payload["rows"][0]
    assert row["sequencing"] == 1
    assert row["genotyping_panels"] == 0
    assert row["radiology"] == 1
    assert row["proteomics"] == 1
    assert row["other_technology"] == 1
    assert row["metabolomics"] == 0

    csv_path = tmp_path / "so2-modalities-technology-upset.csv"
    r_path = tmp_path / "so2-modalities-technology-upset.R"
    assert csv_path.exists()
    assert r_path.exists()
    df = __import__("pandas").read_csv(csv_path)
    assert {"country", "sequencing", "radiology", "proteomics", "other_technology", "has_any_modality"}.issubset(df.columns)
    assert df.loc[0, "country"] == "CZ"
    assert int(df.loc[0, "sequencing"]) == 1
    assert int(df.loc[0, "radiology"]) == 1
    assert int(df.loc[0, "proteomics"]) == 1
    assert int(df.loc[0, "other_technology"]) == 1
    script_text = r_path.read_text(encoding="utf-8")
    assert "ComplexUpset::upset" in script_text
    assert "Observed Intersection Deviation From Independence" in script_text
    assert "so2-modalities-technology-upset.pdf" in script_text
    assert "so2-modalities-technology-upset-deviation.png" in script_text
    assert "SO2 Survey Respondent-by-Modality Matrix" in script_text
    assert "so2-modalities-technology-matrix.pdf" in script_text
    assert "so2-modalities-technology-matrix.png" in script_text
    assert "tidyr::pivot_longer" in script_text
    assert 'paste0(" (", plot_data$country, ")"' in script_text
    assert 'plot.background = ggplot2::element_rect(fill = "white", colour = NA)' in script_text
    assert 'dplyr::arrange(.data$country, dplyr::desc(.data$modality_count), .data$institution_name, .data$survey_row)' in script_text
    assert 'respondent_label = factor(.data$respondent_label, levels = rev(respondent_levels))' in script_text
    assert "Rows are grouped by country, then sorted by the number of advertised modalities, highest first." in script_text


def test_technology_genotyping_panels_is_split_from_other_positive_detail(tmp_path, monkeypatch):
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "Other (please specify):",
            "Technologies": "GWAS array",
        },
        filename="technology-genotyping-panels.xlsx",
    )
    output_json = tmp_path / "technology-genotyping-panels-report.json"

    monkeypatch.setattr(module, "Directory", DirectoryStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        output_tech_upset_prefix=None,
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
    technology_payload = payload["technology_modalities"]
    assert technology_payload["summary"]["modality_counts"]["genotyping_panels"] == 1
    assert technology_payload["summary"]["field_only_counts"]["genotyping_panels"] == 1
    assert technology_payload["summary"]["modality_counts"]["other_technology"] == 0
    row = technology_payload["rows"][0]
    assert row["genotyping_panels"] == 1
    assert row["genotyping_panels_field_present"] == 1
    assert row["other_technology"] == 0
    assert row["other_technology_field_present"] == 0
    assert row["has_any_modality"] == 1


def test_technology_other_checkbox_requires_positive_detail(tmp_path, monkeypatch):
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "Other (please specify):",
            "Technologies": "The answer is \"No\"",
        },
        filename="technology-other-negative.xlsx",
    )
    output_json = tmp_path / "technology-other-negative-report.json"

    monkeypatch.setattr(module, "Directory", DirectoryStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        output_tech_upset_prefix=None,
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
    technology_payload = payload["technology_modalities"]
    assert technology_payload["summary"]["modality_counts"]["other_technology"] == 0
    assert technology_payload["summary"]["field_only_counts"]["other_technology"] == 0
    row = technology_payload["rows"][0]
    assert row["other_technology_selected"] == 1
    assert row["other_technology_detail_present"] == 1
    assert row["other_technology_field_present"] == 0
    assert row["other_technology"] == 0
    assert row["has_any_modality"] == 0


def test_survey_so2_analyze_sample_size_uses_oom_fallback_as_manual_review(tmp_path, monkeypatch):
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "What is the approximate size of your biobank (number of samples aliquots)?": "1000 - 10,000 aliquots",
        },
        filename="size-oom.xlsx",
    )
    output_json = tmp_path / "size-oom-report.json"

    class DirectoryOomSizeStub(DirectoryStub):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._collection["order_of_magnitude"] = 3

    monkeypatch.setattr(module, "Directory", DirectoryOomSizeStub)

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
    size_finding = next(finding for finding in payload["findings"] if finding["mapping_id"] == "biobank_size.samples")
    assert size_finding["status"] == "manual_review"
    assert size_finding["directory_value"]["explicit_total"] is None
    assert size_finding["directory_value"]["estimated_total"] == 1000
    assert size_finding["directory_value"]["bucket"] == "500 - 1000 aliquots"
    assert size_finding["directory_value"]["estimate_used"] is True


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
                "status": "missing_in_directory",
                "survey_row": 5,
                "mapping_id": "imaging.wsi_presence",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Missing in directory.",
                "why_relevant": "z",
                "relation_type": "derived_presence",
                "reliability": "medium",
                "survey_fields": [],
                "survey_value": "yes",
                "directory_value": "no",
                "proposed_update": None,
            },
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

    assert r"BIOBANK \texorpdfstring{\nolinkurl{bbmri-eric:ID:NL_LUMC}}{bbmri-eric:ID:NL_LUMC}" in tex
    assert r"Demo\_\allowbreak{}1 \& needs manual review." in tex
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
                "collection_scope_display": "all collections",
            },
            {
                "survey_row": 7,
                "institution_name": "Demo Biobank follow-up",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col2"],
                "collection_scope_display": "All except bbmri-eric:ID:CZ_demo:collection:col1",
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
    assert r"\nolinkurl{bbmri-eric:ID:CZ_demo}" in tex
    assert "(2 survey answers)" in tex
    assert "Survey row 6: Demo Biobank" in tex
    assert "Survey row 7: Demo Biobank follow-up" in tex
    assert "Mapped collections: all collections" in tex
    assert r"Mapped collections: All except \texorpdfstring{\nolinkurl{bbmri-eric:ID:CZ_demo:collection:col1}}{bbmri-eric:ID:CZ_demo:collection:col1}" in tex
    assert r"\textcolor{soGreen}{Consistent}" in tex
    assert r"\hyperref[appendix-geo-country]{" in tex
    assert r"\nolinkurl{geo.country}" in tex
    assert r"\textcolor{soRed}{Inconsistent}" in tex
    assert r"\hyperref[appendix-sample-types-materials]{" in tex
    assert r"\nolinkurl{sample_types.materials}" in tex
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
    assert r"\nolinkurl{bbmri-eric:ID:CZ_demo}" in tex
    assert r"\nolinkurl{promotion.partnership_interest}" in tex


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
    assert tex.count(r"sample\_\allowbreak{}types.materials\label{appendix-sample-types-materials}") == 1
    assert r"\hyperref[appendix-geo-country]{" in tex
    assert r"\nolinkurl{geo.country}" in tex
    assert r"\hyperref[appendix-sample-types-materials]{" in tex
    assert r"\nolinkurl{sample_types.materials}" in tex
    assert "Consistent." in tex
    assert r"Missing in Directory=WHOLE\_\allowbreak{}BLOOD; Extra in Directory=<empty>." in tex


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

    assert r"COLLECTION \texorpdfstring{\nolinkurl{bbmri-eric:ID:NL_LUMC:collection:CRC.Cohort-1}}{bbmri-eric:ID:NL_LUMC:collection:CRC.Cohort-1}" in tex


def test_escape_latex_breakable_entity_hyphenates_camel_case_segments():
    module = load_module()

    rendered = module.escape_latex_breakable_entity("bbmri-eric:ID:CH_FondazioneEpatocentroTicino")

    assert r"\nolinkurl{bbmri-eric:ID:CH_Fondazione-Epatocentro-Ticino}" in rendered


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


def test_resolve_row_normalizes_collection_scope_and_avoids_geneva_bern_mixup():
    module = load_module()
    directory = SwissResolutionDirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    network_index = {}
    contacts_by_email = {}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)
    collection_contact_domain_counts = {
        "unige.ch": {"bbmri-eric:ID:CH_Unige": 1, "bbmri-eric:ID:CH_HopitauxUniversitairesGeneve": 1},
        "unibe.ch": {"bbmri-eric:ID:CH_UniversityOfBern": 2},
    }

    veterinary_row = {
        "Name of Institution": "Insitute of Genetics, Vetsuisse Faculty, University of Bern",
        "BiobankID in the Directory (if available)": "bbmri-eric:ID:CH_UniversityOfBern",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "CH_UniversityOfBern:collection:CH_VetSuisseBiobankVETGENBERN",
        "Country": "Switzerland",
        "E-Mail address": "michaela.droegemueller@unibe.ch",
        "Research field": "genetic traits and diseases in animals",
        "What field of research does your biobank or biomolecular resource support? (Select all that apply)": "Other (please specify):",
    }
    veterinary_resolution = module.resolve_row(
        __import__("pandas").Series(veterinary_row),
        17,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        collection_contact_domain_counts,
    )
    assert veterinary_resolution["matched_biobank_ids"] == ["bbmri-eric:ID:CH_UniversityOfBern"]
    assert veterinary_resolution["matched_collection_ids"] == [
        "bbmri-eric:ID:CH_UniversityOfBern:collection:CH_VetSuisseBiobankVETGENBERN"
    ]

    geneva_row = {
        "Name of Institution": "University of Geneva",
        "BiobankID in the Directory (if available)": "",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "",
        "Country": "Switzerland",
        "E-Mail address": "valerie.dutoit@unige.ch",
    }
    geneva_resolution = module.resolve_row(
        __import__("pandas").Series(geneva_row),
        57,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        collection_contact_domain_counts,
    )
    assert "bbmri-eric:ID:CH_UniversityOfBern" not in geneva_resolution["matched_biobank_ids"]


def test_normalize_biobank_id_accepts_bare_directory_id():
    module = load_module()

    assert module.normalize_biobank_id("NL_AUMCBB") == "bbmri-eric:ID:NL_AUMCBB"
    assert module.normalize_biobank_id("bbmri-eric:ID:NL_AUMCBB") == "bbmri-eric:ID:NL_AUMCBB"


def test_resolve_row_matches_bare_biobank_id_and_falls_back_from_invalid_explicit_id():
    module = load_module()
    directory = DirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    network_index = {}
    contacts_by_email = {directory.getContacts()[0]["email"]: directory.getContacts()}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)

    row = {
        "Name of Institution": "Demo Biobank",
        "BiobankID in the Directory (if available)": "CZ_demo",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "",
        "Country": "Czech Republic",
        "E-Mail address": "contact@example.org",
    }
    resolved = module.resolve_row(
        __import__("pandas").Series(row),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_biobank_id"
    assert resolved["matched_biobank_ids"] == ["bbmri-eric:ID:CZ_demo"]

    row["BiobankID in the Directory (if available)"] = "CZ_missing"
    resolved = module.resolve_row(
        __import__("pandas").Series(row),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_contact_email"
    assert resolved["matched_biobank_ids"] == ["bbmri-eric:ID:CZ_demo"]
    assert "Survey biobank ID CZ_missing does not exist in schema ERIC." in resolved["resolution_explanation"]


def test_alias_and_acronym_matching_supports_chuv_and_small_typos():
    module = load_module()

    assert module.normalize_text(float("nan")) == ""
    assert module.normalize_text("Hôpitaux Universitaires Genève") == "hopitaux university geneve"

    aliases = module.institution_aliases("Centre Hospitalier Universitaire Vaudois")
    assert "chuv" in aliases

    biobank = {
        "id": "bbmri-eric:ID:CH_CHUV",
        "name": "Centre Hospitalier Universitaire Vaudois",
        "country": "CH",
    }
    biobanks_by_alias = {}
    for alias in module.institution_aliases(biobank["name"]).union(module.biobank_id_aliases(biobank["id"])):
        biobanks_by_alias.setdefault(alias, []).append(biobank)

    alias_candidates = module.match_biobank_alias_candidates({"chuv"}, biobanks_by_alias, country="CH")
    assert [candidate["id"] for candidate in alias_candidates] == ["bbmri-eric:ID:CH_CHUV"]

    score = max(
        __import__("difflib").SequenceMatcher(None, survey_key, candidate_key).ratio()
        for survey_key in module.institution_aliases("Leids Universtair Medical Center")
        for candidate_key in module.institution_aliases("Leiden University Medical Center Biobank")
    )
    assert score >= 0.82


def test_resolve_row_matches_chuv_alias_even_with_invalid_explicit_biobank_id():
    module = load_module()

    class ChuvDirectoryStub:
        def getSchema(self):
            return "ERIC"

        def getBiobanks(self):
            return [
                {
                    "id": "bbmri-eric:ID:CH_CHUV",
                    "name": "Centre Hospitalier Universitaire Vaudois",
                    "country": "CH",
                }
            ]

        def getCollections(self):
            return [
                {
                    "id": "bbmri-eric:ID:CH_CHUV:collection:demo",
                    "biobank": {"id": "bbmri-eric:ID:CH_CHUV"},
                    "name": "Demo collection",
                    "description": "",
                    "type": ["SAMPLE"],
                    "materials": ["SERUM"],
                }
            ]

        def getGraphBiobankCollectionsFromBiobank(self, biobank_id):
            import networkx as nx

            graph = nx.DiGraph()
            graph.add_node(biobank_id)
            graph.add_node("bbmri-eric:ID:CH_CHUV:collection:demo")
            graph.add_edge(biobank_id, "bbmri-eric:ID:CH_CHUV:collection:demo")
            return graph

    directory = ChuvDirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    network_index = {}
    contacts_by_email = {}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)

    row = {
        "Name of Institution": "CHUV",
        "BiobankID in the Directory (if available)": "BB_038",
        "Country": "Switzerland",
        "E-Mail address": "nathalie.vionnet@chuv.ch",
    }
    resolved = module.resolve_row(
        __import__("pandas").Series(row),
        25,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_institution_name_certain"
    assert resolved["matched_biobank_ids"] == ["bbmri-eric:ID:CH_CHUV"]
    assert "Resolved by institution alias/acronym match" in resolved["resolution_explanation"]


def test_resolve_row_uses_exact_contact_email_before_name_matching():
    module = load_module()

    class ContactDirectoryStub(DirectoryStub):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._biobank["name"] = "Different Official Name"
            self._contact["email"] = "owner@example.org"

    directory = ContactDirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    contact_index = {contact["id"]: contact for contact in directory.getContacts()}
    network_index = {}
    contacts_by_email = {"owner@example.org": directory.getContacts()}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)
    row = {
        "Name of Institution": "Completely Different Survey Name",
        "BiobankID in the Directory (if available)": "",
        "Country": "Czech Republic",
        "E-Mail address": "owner@example.org",
    }
    resolved = module.resolve_row(
        __import__("pandas").Series(row),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_contact_email"
    assert resolved["matched_biobank_ids"] == ["bbmri-eric:ID:CZ_demo"]
    assert resolved["matched_contact_ids"] == ["bbmri-eric:contactID:CZ_demo_1"]


def test_resolve_row_marks_dangling_contact_biobank_references_for_manual_review():
    module = load_module()

    class DanglingContactDirectoryStub:
        def getSchema(self):
            return "ERIC"

        def getBiobanks(self):
            return []

        def getCollections(self):
            return []

        def getContacts(self):
            return [
                {
                    "id": "bbmri-eric:contactID:ES_demo",
                    "email": "demo@example.org",
                    "biobanks": [{"id": "bbmri-eric:ID:ES_MISSING"}],
                }
            ]

        def getNetworks(self):
            return []

    directory = DanglingContactDirectoryStub()
    biobank_index = {}
    collection_index = {}
    contact_index = {contact["id"]: contact for contact in directory.getContacts()}
    network_index = {}
    contacts_by_email = {"demo@example.org": directory.getContacts()}
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    resolved = module.resolve_row(
        __import__("pandas").Series(
            {
                "Name of Institution": "Demo",
                "BiobankID in the Directory (if available)": "",
                "Country": "Spain",
                "E-Mail address": "demo@example.org",
            }
        ),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        {},
        {},
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "manual_review"
    assert "bbmri-eric:ID:ES_MISSING" in resolved["resolution_explanation"]
    assert resolved["matched_contact_ids"] == ["bbmri-eric:contactID:ES_demo"]


def test_resolve_row_supports_explicit_network_id():
    module = load_module()
    directory = DirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    contact_index = {contact["id"]: contact for contact in directory.getContacts()}
    network_index = {"bbmri-eric:networkID:DE_DKTK": {"id": "bbmri-eric:networkID:DE_DKTK", "name": "DKTK"}}
    contacts_by_email = {directory.getContacts()[0]["email"]: directory.getContacts()}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)
    resolved = module.resolve_row(
        __import__("pandas").Series(
            {
                "Name of Institution": "German Cancer Consortium",
                "BiobankID in the Directory (if available)": "bbmri-eric:networkID:DE_DKTK",
                "Country": "Germany",
                "E-Mail address": "",
            }
        ),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_network_id"
    assert resolved["matched_network_ids"] == ["bbmri-eric:networkID:DE_DKTK"]


def test_survey_so2_render_tex_adds_directory_fields_missing_country_prefix_and_breakable_emails():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 1, "missing_rows": 1, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [
            {
                "survey_row": 6,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID bbmri-eric:ID:CZ_demo:collection:col1.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col1"],
            }
        ],
        "findings": [
            {
                "status": "missing_from_directory",
                "survey_row": 7,
                "mapping_id": "row_resolution",
                "entity_type": "BIOBANK",
                "entity_id": "NL_AUMCBB",
                "explanation": "No exact-ID or institution-name-based match was found in the Directory.",
                "why_relevant": "Mapping must be resolved first.",
                "relation_type": "entity_resolution",
                "reliability": "low",
                "survey_fields": ["Country", "E-Mail address"],
                "survey_value": {"country": "NL", "institution_name": "AUMC", "email": "contact.person@example.org"},
                "directory_value": {"matched_biobank_ids": []},
                "proposed_update": None,
            },
            {
                "status": "missing_in_directory",
                "survey_row": 6,
                "mapping_id": "imaging.wsi_presence",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Survey-reported WSI availability is not reflected by generic imaging metadata or text.",
                "why_relevant": "Imaging comparison.",
                "relation_type": "derived_presence",
                "reliability": "medium",
                "survey_fields": ["Radiology / WSI"],
                "survey_value": {"answer": "Yes"},
                "directory_value": {"has_image_support": False, "has_wsi_hint": False},
                "proposed_update": None,
            },
            {
                "status": "manual_review",
                "survey_row": 6,
                "mapping_id": "contact.email",
                "entity_type": "CONTACT",
                "entity_id": "bbmri-eric:contactID:CZ_demo_1",
                "explanation": "Respondent email differs from Directory contact email.",
                "why_relevant": "Contact comparison.",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": ["E-Mail address"],
                "survey_value": "contact.person@example.org",
                "directory_value": "data.owner@example.org",
                "proposed_update": None,
            },
            {
                "status": "inconsistent",
                "survey_row": 6,
                "mapping_id": "sample_types.materials",
                "entity_type": "COLLECTION",
                "entity_id": "bbmri-eric:ID:CZ_demo:collection:col1",
                "explanation": "Inconsistent material types between survey and Directory collection.",
                "why_relevant": "Material comparison.",
                "relation_type": "controlled_vocabulary_mapping",
                "reliability": "medium",
                "survey_fields": ["Which types of samples do you manage?"],
                "survey_value": {"expected_materials": ["DNA", "SERUM"]},
                "directory_value": {"observed_materials": ["DNA", "SALIVA"]},
                "proposed_update": None,
            },
        ],
    }

    tex = module.render_tex(report)

    assert r"\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}" in tex
    assert r"\begin{longtable}{L{1.5cm}L{3.2cm}L{3.2cm}L{6.5cm}}" in tex
    assert r"(NL) BIOBANK \texorpdfstring{\nolinkurl{NL_AUMCBB}}{NL_AUMCBB}" in tex
    assert r"\nolinkurl{contact.person@example.org}" in tex
    assert r"Missing in Directory=SERUM; Extra in Directory=SALIVA." in tex
    assert "These findings are linked to a concrete Directory entity" in tex
    assert "These findings have a plausible survey-to-Directory relation" in tex
    assert "These findings cover survey respondents or identifiers that could not be mapped confidently" in tex
    assert "These findings indicate a concrete mismatch between the survey answer and the mapped Directory metadata" in tex
    assert r"\subsection{\textcolor{soRed}{Survey Data Missing from the Directory}}" in tex
    assert r"\subsection{\textcolor{soOrange}{Data Requiring Manual Review}}" in tex
    assert r"\subsection{\textcolor{soOrange}{Entities Not Mapped to the Directory}}" in tex
    assert r"\textbf{Directory field(s):} COLLECTION.materials\\" in tex
    assert r"\textbf{Comparison method:} Map structured survey sample-type answers" in tex


def test_findings_by_status_orders_missing_in_directory_manual_review_and_missing_from_directory():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 0, "missing_rows": 1, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "missing_from_directory",
                "survey_row": 7,
                "mapping_id": "row_resolution",
                "entity_type": "BIOBANK",
                "entity_id": "NL_AUMCBB",
                "explanation": "Missing.",
                "why_relevant": "x",
                "relation_type": "entity_resolution",
                "reliability": "low",
                "survey_fields": [],
                "survey_value": {"country": "NL"},
                "directory_value": {"matched_biobank_ids": []},
                "proposed_update": None,
            },
            {
                "status": "missing_in_directory",
                "survey_row": 5,
                "mapping_id": "imaging.wsi_presence",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Missing in directory.",
                "why_relevant": "z",
                "relation_type": "derived_presence",
                "reliability": "medium",
                "survey_fields": [],
                "survey_value": "yes",
                "directory_value": "no",
                "proposed_update": None,
            },
            {
                "status": "manual_review",
                "survey_row": 6,
                "mapping_id": "contact.email",
                "entity_type": "CONTACT",
                "entity_id": "bbmri-eric:contactID:CZ_demo_1",
                "explanation": "Manual review.",
                "why_relevant": "y",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": [],
                "survey_value": "a",
                "directory_value": "b",
                "proposed_update": None,
            },
        ],
    }
    tex = module.render_tex(report)
    assert tex.index(r"\subsection{\textcolor{soRed}{Survey Data Missing from the Directory}}") < tex.index(
        r"\subsection{\textcolor{soOrange}{Data Requiring Manual Review}}"
    )
    assert tex.index(r"\subsection{\textcolor{soOrange}{Data Requiring Manual Review}}") < tex.index(
        r"\subsection{\textcolor{soOrange}{Entities Not Mapped to the Directory}}"
    )


def test_findings_by_status_adds_intro_for_ambiguous_section():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 0, "missing_rows": 0, "ambiguous_rows": 1, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "ambiguous",
                "survey_row": 1,
                "mapping_id": "row_resolution",
                "entity_type": "BIOBANK",
                "entity_id": "Demo",
                "explanation": "Ambiguous.",
                "why_relevant": "x",
                "relation_type": "entity_resolution",
                "reliability": "low",
                "survey_fields": [],
                "survey_value": {"institution_name": "Demo"},
                "directory_value": {"matched_biobank_ids": ["A", "B"]},
                "proposed_update": None,
            },
        ],
    }
    tex = module.render_tex(report)
    assert "These findings indicate that the available survey and Directory evidence supports more than one plausible interpretation or mapping." in tex


def test_findings_by_status_keeps_stable_sections_when_one_status_has_no_findings():
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 0, "missing_rows": 1, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "manual_review",
                "survey_row": 6,
                "mapping_id": "contact.email",
                "entity_type": "CONTACT",
                "entity_id": "bbmri-eric:contactID:CZ_demo_1",
                "explanation": "Manual review.",
                "why_relevant": "y",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": [],
                "survey_value": "a",
                "directory_value": "b",
                "proposed_update": None,
            },
            {
                "status": "missing_from_directory",
                "survey_row": 7,
                "mapping_id": "row_resolution",
                "entity_type": "BIOBANK",
                "entity_id": "NL_AUMCBB",
                "explanation": "Missing.",
                "why_relevant": "x",
                "relation_type": "entity_resolution",
                "reliability": "low",
                "survey_fields": [],
                "survey_value": {"country": "NL"},
                "directory_value": {"matched_biobank_ids": []},
                "proposed_update": None,
            },
        ],
    }
    tex = module.render_tex(report)
    assert r"\subsection{\textcolor{soRed}{Survey Data Missing from the Directory}}" in tex
    assert "No findings with this status in the current report." in tex
    assert tex.index(r"\subsection{\textcolor{soRed}{Survey Data Missing from the Directory}}") < tex.index(
        r"\subsection{\textcolor{soOrange}{Data Requiring Manual Review}}"
    )


def test_summarize_collection_scope_uses_all_collections_and_all_except():
    module = load_module()

    assert module.summarize_collection_scope(["c1", "c2"], ["c1", "c2"]) == "all collections"
    assert module.summarize_collection_scope(["c1", "c3"], ["c1", "c2", "c3"]) == "c1, c3"
    assert module.summarize_collection_scope(["c1", "c3", "c4", "c5"], ["c1", "c2", "c3", "c4", "c5", "c6"]) == "All except c2, c6"
    assert module.summarize_collection_scope(["c1"], ["c1", "c2", "c3", "c4", "c5", "c6"]) == "c1"



def test_survey_so2_render_tex_includes_so21_technology_matrix():
    module = load_module()
    technology_rows = [
        {
            "survey_row": 7,
            "institution_name": "Gamma Biobank",
            "matched_biobank_ids": "bbmri-eric:ID:CZ_gamma",
            "matched_collection_ids": "",
            "resolution_status": "resolved_by_biobank_id",
            "sequencing": 1,
            "genotyping_panels": 0,
            "radiology": 1,
            "pathology": 1,
            "proteomics": 0,
            "metabolomics": 0,
            "other_technology": 0,
            "has_any_modality": 1,
        },
        {
            "survey_row": 8,
            "institution_name": "Alpha Biobank",
            "matched_biobank_ids": "bbmri-eric:ID:CZ_alpha",
            "matched_collection_ids": "",
            "resolution_status": "resolved_by_biobank_id",
            "sequencing": 1,
            "genotyping_panels": 0,
            "radiology": 0,
            "pathology": 0,
            "proteomics": 0,
            "metabolomics": 0,
            "other_technology": 0,
            "has_any_modality": 1,
        },
    ]
    report = {
        "report_metadata": {"generated_at": "2026-03-19T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 2, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "findings": [],
        "row_resolutions": [],
        "strategic_objectives": {"SO2.1": {"title": "Datafication at source", "description": "x"}},
        "technology_modalities": module.build_technology_modalities_payload(technology_rows),
    }
    tex = module.render_tex(report)
    assert "Technology Modality Matrix" in tex
    assert "Gamma Biobank" in tex
    assert "Alpha Biobank" in tex
    assert tex.index("Gamma Biobank") < tex.index("Alpha Biobank")
    assert "NGS & G/P & Rad & Path & Prot & Met & Other & N" in tex


def test_technology_modalities_combine_question_sources_and_render_inconsistencies(tmp_path):
    module = load_module()
    survey_row = __import__("pandas").Series(
        {
            "Name of Institution": "Demo Biobank",
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "I don’t know",
            "Does your biobank provide access to radiology datasets?": "Yes — access to internally generated radiology data collections (e.g., directly connected to a PACS system)",
            "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?": "Yes — access to internally generated WSI data collections",
        }
    )
    row_resolution = {
        "survey_row": 1,
        "resolution_status": "missing_from_directory",
        "matched_biobank_ids": [],
        "matched_collection_ids": [],
    }
    technology_row = module.build_technology_modality_row(survey_row, row_resolution)
    payload = module.build_technology_modalities_payload([technology_row])

    assert technology_row["radiology"] == 1
    assert technology_row["pathology"] == 1
    assert technology_row["radiology_field_present"] == 0
    assert technology_row["pathology_field_present"] == 0
    assert technology_row["radiology_question_present"] == 1
    assert technology_row["pathology_question_present"] == 1
    assert technology_row["radiology_inconsistent"] == 1
    assert technology_row["pathology_inconsistent"] == 1
    assert payload["summary"]["modality_counts"]["radiology"] == 1
    assert payload["summary"]["modality_counts"]["pathology"] == 1
    assert payload["summary"]["field_only_counts"]["radiology"] == 0
    assert payload["summary"]["field_only_counts"]["pathology"] == 0
    assert payload["summary"]["question_yes_counts"]["radiology"] == 1
    assert payload["summary"]["question_yes_counts"]["pathology"] == 1
    assert payload["summary"]["inconsistency_counts"]["radiology"] == 1
    assert payload["summary"]["inconsistency_counts"]["pathology"] == 1

    report = {
        "report_metadata": {"generated_at": "2026-03-18T00:00:00+00:00"},
        "summary": {
            "survey_rows": 1,
            "resolved_rows": 0,
            "missing_rows": 1,
            "ambiguous_rows": 0,
            "proposed_update_findings": 0,
        },
        "findings": [],
        "row_resolutions": [row_resolution],
        "strategic_objectives": {},
        "technology_modalities": payload,
    }
    tex = module.render_tex(report)
    assert "Technology Modalities" in tex
    assert "Field/question mismatches: Radiology=1, Pathology/WSI=1" in tex
    assert "Technology Source Inconsistencies" in tex

def test_survey_so2_render_report_can_write_only_technology_upset_artifacts(tmp_path):
    module = load_module()
    survey_row = __import__("pandas").Series(
        {
            "Name of Institution": "Demo Biobank",
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "Next-gen sequencing (if yes, specify technology/vendor)",
            "Next-gen sequencing technology/vendor": "Illumina",
        }
    )
    row_resolution = {
        "survey_row": 1,
        "resolution_status": "resolved_by_biobank_id",
        "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
        "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col1"],
    }
    technology_rows = [module.build_technology_modality_row(survey_row, row_resolution)]
    report = {
        "report_metadata": {"generated_at": "2026-03-18T00:00:00+00:00"},
        "summary": {},
        "findings": [],
        "row_resolutions": [],
        "strategic_objectives": {},
        "technology_modalities": module.build_technology_modalities_payload(technology_rows),
    }
    input_json = tmp_path / "report.json"
    input_json.write_text(json.dumps(report), encoding="utf-8")
    upset_prefix = tmp_path / "render-only"

    args = Namespace(
        input_json=str(input_json),
        output_tex=None,
        output_pdf=None,
        output_tech_upset_prefix=str(upset_prefix),
        verbose=False,
        debug=False,
    )

    result = module.run_render(args)

    assert result == module.EXIT_OK
    assert (tmp_path / "render-only-technology-upset.csv").exists()
    assert (tmp_path / "render-only-technology-upset.R").exists()
