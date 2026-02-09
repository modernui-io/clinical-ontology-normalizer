"""CDISC ODM XML Parser.

Parses CDISC Operational Data Model (ODM) v1.3 XML documents used by
Medidata Rave for study definitions, eligibility criteria, and clinical
data exchange.

Reference: https://www.cdisc.org/standards/data-exchange/odm
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)

# CDISC ODM v1.3 XML namespace
ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
MDSOL_NS = "http://www.mdsol.com/ns/odm/metadata"

# Namespace map for XPath queries
NS = {"odm": ODM_NS, "mdsol": MDSOL_NS}


def _find_text(element: ET.Element, path: str, default: str = "") -> str:
    """Find text content at an XPath, returning default if not found."""
    el = element.find(path, NS)
    if el is not None and el.text:
        return el.text.strip()
    return default


def _get_attr(element: ET.Element, attr: str, default: str = "") -> str:
    """Get element attribute with a default."""
    return element.get(attr, default)


def parse_study_definition(odm_xml: str) -> dict[str, Any]:
    """Parse an ODM XML document and extract the study definition.

    Extracts study-level metadata including name, description, protocol,
    forms (CRF definitions), and item definitions.

    Args:
        odm_xml: Raw ODM XML string from Rave Web Services.

    Returns:
        Dictionary with study metadata:
            - oid: Study OID
            - name: Study name
            - description: Study description
            - protocol_name: Protocol name
            - forms: List of form definitions
            - items: List of item (field) definitions
            - item_groups: List of item group definitions
    """
    root = ET.fromstring(odm_xml)

    study_el = root.find(".//odm:Study", NS)
    if study_el is None:
        # Try without namespace for simple XML
        study_el = root.find(".//Study")

    if study_el is None:
        logger.warning("No Study element found in ODM XML")
        return {"oid": "", "name": "Unknown", "forms": [], "items": [], "item_groups": []}

    study_oid = _get_attr(study_el, "OID")

    # Global variables (study-level metadata)
    gv = study_el.find("odm:GlobalVariables", NS)
    if gv is None:
        gv = study_el.find("GlobalVariables")

    study_name = ""
    study_desc = ""
    protocol_name = ""

    if gv is not None:
        study_name = _find_text(gv, "odm:StudyName", "") or _find_text(gv, "StudyName", "")
        study_desc = _find_text(gv, "odm:StudyDescription", "") or _find_text(gv, "StudyDescription", "")
        protocol_name = _find_text(gv, "odm:ProtocolName", "") or _find_text(gv, "ProtocolName", "")

    # Parse MetaDataVersion for forms, item groups, items
    md = study_el.find(".//odm:MetaDataVersion", NS)
    if md is None:
        md = study_el.find(".//MetaDataVersion")

    forms: list[dict[str, Any]] = []
    item_groups: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    if md is not None:
        # Forms
        for form_el in md.findall("odm:FormDef", NS) or md.findall("FormDef"):
            form = {
                "oid": _get_attr(form_el, "OID"),
                "name": _get_attr(form_el, "Name"),
                "repeating": _get_attr(form_el, "Repeating", "No"),
                "item_group_refs": [],
            }
            for igr in form_el.findall("odm:ItemGroupRef", NS) or form_el.findall("ItemGroupRef"):
                form["item_group_refs"].append(_get_attr(igr, "ItemGroupOID"))
            forms.append(form)

        # Item Groups
        for ig_el in md.findall("odm:ItemGroupDef", NS) or md.findall("ItemGroupDef"):
            ig = {
                "oid": _get_attr(ig_el, "OID"),
                "name": _get_attr(ig_el, "Name"),
                "repeating": _get_attr(ig_el, "Repeating", "No"),
                "item_refs": [],
            }
            for ir in ig_el.findall("odm:ItemRef", NS) or ig_el.findall("ItemRef"):
                ig["item_refs"].append({
                    "item_oid": _get_attr(ir, "ItemOID"),
                    "mandatory": _get_attr(ir, "Mandatory", "No"),
                })
            item_groups.append(ig)

        # Items
        for item_el in md.findall("odm:ItemDef", NS) or md.findall("ItemDef"):
            item = {
                "oid": _get_attr(item_el, "OID"),
                "name": _get_attr(item_el, "Name"),
                "data_type": _get_attr(item_el, "DataType"),
                "length": _get_attr(item_el, "Length"),
                "description": "",
                "question": "",
                "code_list_oid": None,
            }

            # Description
            desc = item_el.find("odm:Description/odm:TranslatedText", NS)
            if desc is not None and desc.text:
                item["description"] = desc.text.strip()

            # Question text
            q = item_el.find("odm:Question/odm:TranslatedText", NS)
            if q is not None and q.text:
                item["question"] = q.text.strip()

            # CodeList reference
            clr = item_el.find("odm:CodeListRef", NS)
            if clr is not None:
                item["code_list_oid"] = _get_attr(clr, "CodeListOID")

            items.append(item)

    return {
        "oid": study_oid,
        "name": study_name,
        "description": study_desc,
        "protocol_name": protocol_name,
        "forms": forms,
        "items": items,
        "item_groups": item_groups,
    }


def extract_eligibility_criteria(odm_xml: str) -> list[dict[str, Any]]:
    """Extract eligibility criteria from an ODM study definition.

    Looks for forms/item groups with eligibility-related names (common
    Rave convention: forms named "IE" or containing "ELIG", "INCL", "EXCL").

    Args:
        odm_xml: Raw ODM XML string.

    Returns:
        List of criteria dicts with:
            - oid: Item OID
            - criterion_type: "inclusion" or "exclusion"
            - description: Criterion text
            - code_system: Optional code system
            - code: Optional coded value
            - data_type: Expected data type
    """
    study_def = parse_study_definition(odm_xml)
    criteria: list[dict[str, Any]] = []

    # Build lookup maps
    item_map = {item["oid"]: item for item in study_def["items"]}
    ig_map = {ig["oid"]: ig for ig in study_def["item_groups"]}

    # Identify eligibility-related item groups
    eligibility_keywords = {"ie", "elig", "incl", "excl", "inclusion", "exclusion", "criteria"}

    eligibility_item_oids: set[str] = set()
    eligibility_ig_types: dict[str, str] = {}  # item_oid -> "inclusion" or "exclusion"

    for ig in study_def["item_groups"]:
        ig_name_lower = ig["name"].lower()
        ig_oid_lower = ig["oid"].lower()

        is_eligibility = any(kw in ig_name_lower or kw in ig_oid_lower for kw in eligibility_keywords)
        if not is_eligibility:
            continue

        # Determine type from naming convention
        is_exclusion = "excl" in ig_name_lower or "excl" in ig_oid_lower
        criterion_type = "exclusion" if is_exclusion else "inclusion"

        for item_ref in ig["item_refs"]:
            oid = item_ref["item_oid"]
            eligibility_item_oids.add(oid)
            eligibility_ig_types[oid] = criterion_type

    # Also check forms for eligibility naming
    for form in study_def["forms"]:
        form_name_lower = form["name"].lower()
        form_oid_lower = form["oid"].lower()

        is_eligibility = any(kw in form_name_lower or kw in form_oid_lower for kw in eligibility_keywords)
        if not is_eligibility:
            continue

        for ig_oid in form["item_group_refs"]:
            ig = ig_map.get(ig_oid)
            if ig is None:
                continue
            is_exclusion = "excl" in ig["name"].lower() or "excl" in ig_oid.lower()
            criterion_type = "exclusion" if is_exclusion else "inclusion"
            for item_ref in ig["item_refs"]:
                oid = item_ref["item_oid"]
                eligibility_item_oids.add(oid)
                if oid not in eligibility_ig_types:
                    eligibility_ig_types[oid] = criterion_type

    # Build criteria from identified items
    for oid in sorted(eligibility_item_oids):
        item = item_map.get(oid)
        if item is None:
            continue

        description = item["question"] or item["description"] or item["name"]
        criterion_type = eligibility_ig_types.get(oid, "inclusion")

        # Also check item-level naming for exclusion hints
        name_lower = item["name"].lower()
        if "excl" in name_lower and criterion_type == "inclusion":
            criterion_type = "exclusion"

        criteria.append({
            "oid": oid,
            "criterion_type": criterion_type,
            "description": description,
            "code_system": None,
            "code": None,
            "data_type": item["data_type"],
        })

    logger.info(
        "Extracted %d eligibility criteria from ODM (%d inclusion, %d exclusion)",
        len(criteria),
        sum(1 for c in criteria if c["criterion_type"] == "inclusion"),
        sum(1 for c in criteria if c["criterion_type"] == "exclusion"),
    )

    return criteria


def build_clinical_data_odm(
    patient_data: dict[str, Any],
    study_oid: str,
    *,
    environment: str = "Prod",
    site_oid: str = "SITE01",
    form_oid: str = "SCREENING",
    item_group_oid: str = "SCREENING_LOG",
) -> str:
    """Build CDISC ODM XML for pushing screening data back to Rave.

    Creates a ClinicalData ODM document that can be submitted to Rave
    via the Rave Web Services POST endpoint.

    Args:
        patient_data: Dictionary with screening data fields.
            Expected keys: subject_key, items (list of {oid, value}).
        study_oid: Target study OID.
        environment: Study environment (Prod, UAT, etc.).
        site_oid: Site OID for subject assignment.
        form_oid: Target form OID for screening data.
        item_group_oid: Target item group OID.

    Returns:
        ODM XML string ready for Rave submission.
    """
    subject_key = patient_data.get("subject_key", "SUBJ001")
    items = patient_data.get("items", [])
    transaction_type = patient_data.get("transaction_type", "Insert")

    # Build XML manually for precise control over namespace and structure
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<ODM xmlns="{ODM_NS}"',
        f'     xmlns:mdsol="{MDSOL_NS}"',
        '     FileType="Transactional"',
        f'     FileOID="SCREENING_{study_oid}"',
        '     CreationDateTime="2024-01-01T00:00:00">',
        f'  <ClinicalData StudyOID="{_xml_escape(study_oid)}"',
        f'                MetaDataVersionOID="1">',
        f'    <SubjectData SubjectKey="{_xml_escape(subject_key)}"',
        f'                 TransactionType="{transaction_type}">',
        f'      <SiteRef LocationOID="{_xml_escape(site_oid)}"/>',
        f'      <StudyEventData StudyEventOID="SCREENING">',
        f'        <FormData FormOID="{_xml_escape(form_oid)}">',
        f'          <ItemGroupData ItemGroupOID="{_xml_escape(item_group_oid)}"',
        f'                        TransactionType="{transaction_type}">',
    ]

    for item in items:
        item_oid = _xml_escape(item.get("oid", ""))
        value = _xml_escape(str(item.get("value", "")))
        lines.append(f'            <ItemData ItemOID="{item_oid}" Value="{value}"/>')

    lines.extend([
        "          </ItemGroupData>",
        "        </FormData>",
        "      </StudyEventData>",
        "    </SubjectData>",
        "  </ClinicalData>",
        "</ODM>",
    ])

    return "\n".join(lines)


def _xml_escape(value: str) -> str:
    """Escape XML special characters in attribute values."""
    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
