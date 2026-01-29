"""SDTM Dataset Generator.

Generates SDTM datasets in submission-ready formats:
- SAS XPT transport files
- CSV files
- define.xml metadata
"""

import csv
import io
import json
import logging
import struct
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from app.models.sdtm_mapping import (
    SDTMDataType,
    SDTMDomainSpec,
    SDTMMappingSpec,
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of dataset generation."""

    domain: str
    format: str
    file_path: str | None = None
    file_content: bytes | None = None
    record_count: int = 0
    success: bool = True
    errors: list[str] = field(default_factory=list)


@dataclass
class DefineXmlResult:
    """Result of define.xml generation."""

    content: str
    domains: list[str]
    variable_count: int
    success: bool = True
    errors: list[str] = field(default_factory=list)


class SDTMGenerator:
    """Generates SDTM datasets and metadata files."""

    def __init__(self, mapping_spec: SDTMMappingSpec | None = None) -> None:
        self._mapping_spec = mapping_spec
        self._output_dir: Path | None = None

    @property
    def mapping_spec(self) -> SDTMMappingSpec | None:
        return self._mapping_spec

    @mapping_spec.setter
    def mapping_spec(self, spec: SDTMMappingSpec) -> None:
        self._mapping_spec = spec

    def set_output_dir(self, path: str | Path) -> None:
        """Set output directory for generated files."""
        self._output_dir = Path(path)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def generate_csv(
        self,
        domain_spec: SDTMDomainSpec,
        records: list[dict[str, Any]],
        output_path: str | None = None,
    ) -> GenerationResult:
        """Generate CSV file for a domain.

        Args:
            domain_spec: Domain specification
            records: SDTM records to write
            output_path: Optional output path

        Returns:
            Generation result
        """
        try:
            # Get variable names from spec
            var_names = [v.name for v in domain_spec.variables]

            # Write to string buffer
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=var_names, extrasaction="ignore")
            writer.writeheader()

            for record in records:
                writer.writerow(record)

            csv_content = output.getvalue()

            # Write to file if path provided
            file_path = None
            if output_path:
                file_path = output_path
            elif self._output_dir:
                file_path = str(self._output_dir / f"{domain_spec.domain.lower()}.csv")

            if file_path:
                with open(file_path, "w", newline="") as f:
                    f.write(csv_content)

            return GenerationResult(
                domain=domain_spec.domain,
                format="csv",
                file_path=file_path,
                file_content=csv_content.encode("utf-8"),
                record_count=len(records),
                success=True,
            )

        except Exception as e:
            return GenerationResult(
                domain=domain_spec.domain,
                format="csv",
                success=False,
                errors=[str(e)],
            )

    def generate_xpt(
        self,
        domain_spec: SDTMDomainSpec,
        records: list[dict[str, Any]],
        output_path: str | None = None,
    ) -> GenerationResult:
        """Generate SAS XPT transport file for a domain.

        Note: This is a simplified XPT generator. For production use,
        consider using a dedicated library like pyreadstat or sas7bdat.

        Args:
            domain_spec: Domain specification
            records: SDTM records to write
            output_path: Optional output path

        Returns:
            Generation result
        """
        try:
            # Build XPT content
            xpt_content = self._build_xpt_content(domain_spec, records)

            # Write to file if path provided
            file_path = None
            if output_path:
                file_path = output_path
            elif self._output_dir:
                file_path = str(self._output_dir / f"{domain_spec.domain.lower()}.xpt")

            if file_path:
                with open(file_path, "wb") as f:
                    f.write(xpt_content)

            return GenerationResult(
                domain=domain_spec.domain,
                format="xpt",
                file_path=file_path,
                file_content=xpt_content,
                record_count=len(records),
                success=True,
            )

        except Exception as e:
            return GenerationResult(
                domain=domain_spec.domain,
                format="xpt",
                success=False,
                errors=[str(e)],
            )

    def _build_xpt_content(
        self, domain_spec: SDTMDomainSpec, records: list[dict[str, Any]]
    ) -> bytes:
        """Build XPT file content.

        This is a simplified implementation that creates a basic XPT structure.
        For full compliance, use a proper SAS transport library.
        """
        # XPT files have 80-byte fixed records
        RECORD_SIZE = 80

        def pad80(s: str) -> bytes:
            """Pad string to 80 bytes."""
            return s.encode("ascii").ljust(RECORD_SIZE, b" ")

        content = bytearray()

        # Library header
        content.extend(pad80("HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!000000000000000000000000000000"))

        # SAS header record
        sas_label = "SAS     SAS     SASLIB  9.4                     "
        content.extend(pad80(sas_label + "                                "))

        # Modification date
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%d%b%y:%H:%M:%S").upper()
        content.extend(pad80(f"{date_str}        {date_str}        "))

        # Member header
        content.extend(pad80("HEADER RECORD*******MEMBER  HEADER RECORD!!!!!!!000000000000000001600000000140"))

        # Dataset descriptor
        desc_header = "HEADER RECORD*******DSCRPTR HEADER RECORD!!!!!!!000000000000000000000000000000"
        content.extend(pad80(desc_header))

        # Dataset name and label
        dataset_name = domain_spec.domain.upper().ljust(8)
        dataset_label = (domain_spec.label or domain_spec.domain)[:40].ljust(40)
        content.extend(pad80(f"SAS     {dataset_name}{dataset_label}                              "))

        # Variable count info
        var_count = len(domain_spec.variables)
        content.extend(pad80(f"    {var_count:05d}                                                                    "))

        # Namestr header
        content.extend(pad80("HEADER RECORD*******NAMESTR HEADER RECORD!!!!!!!000000000000000000000000000000"))

        # Variable descriptors (simplified)
        for i, var in enumerate(domain_spec.variables):
            var_name = var.name.upper()[:8].ljust(8)
            var_label = (var.label or var.name)[:40].ljust(40)
            var_type = 1 if var.data_type == SDTMDataType.NUM else 2  # 1=num, 2=char
            var_length = var.length or 200

            # Namestr record (simplified)
            content.extend(pad80(f"{var_name}{var_label}"))

        # OBS header
        content.extend(pad80("HEADER RECORD*******OBS     HEADER RECORD!!!!!!!000000000000000000000000000000"))

        # Write data records (simplified - just text representation)
        for record in records:
            row_data = ""
            for var in domain_spec.variables:
                value = record.get(var.name, "")
                if value is None:
                    value = ""
                row_data += str(value)[:8].ljust(8)

            # Pad to multiple of 80
            while len(row_data) % 80 != 0:
                row_data += " "

            for i in range(0, len(row_data), 80):
                content.extend(pad80(row_data[i:i+80]))

        return bytes(content)

    def generate_define_xml(
        self,
        mapping_spec: SDTMMappingSpec | None = None,
        output_path: str | None = None,
    ) -> DefineXmlResult:
        """Generate define.xml metadata file.

        Args:
            mapping_spec: Mapping specification (uses instance spec if not provided)
            output_path: Optional output path

        Returns:
            Define.xml generation result
        """
        spec = mapping_spec or self._mapping_spec
        if not spec:
            return DefineXmlResult(
                content="",
                domains=[],
                variable_count=0,
                success=False,
                errors=["No mapping specification provided"],
            )

        try:
            # Build define.xml structure
            root = ET.Element("ODM")
            root.set("xmlns", "http://www.cdisc.org/ns/odm/v1.3")
            root.set("xmlns:def", "http://www.cdisc.org/ns/def/v2.0")
            root.set("ODMVersion", "1.3.2")
            root.set("FileType", "Snapshot")
            root.set("FileOID", f"DEF.{spec.study_id}")
            root.set("CreationDateTime", datetime.now(timezone.utc).isoformat())

            # Study element
            study = ET.SubElement(root, "Study")
            study.set("OID", f"STD.{spec.study_id}")

            # Global variables
            global_vars = ET.SubElement(study, "GlobalVariables")
            ET.SubElement(global_vars, "StudyName").text = spec.study_name
            ET.SubElement(global_vars, "StudyDescription").text = f"SDTM for {spec.study_name}"
            ET.SubElement(global_vars, "ProtocolName").text = spec.study_id

            # MetaDataVersion
            mdv = ET.SubElement(study, "MetaDataVersion")
            mdv.set("OID", "MDV.1")
            mdv.set("Name", f"SDTMIG {spec.sdtmig_version}")
            mdv.set("def:StandardName", "SDTMIG")
            mdv.set("def:StandardVersion", spec.sdtmig_version)

            # Item Group definitions (one per domain)
            variable_count = 0
            domain_names = []

            for domain_spec in spec.domains:
                domain_names.append(domain_spec.domain)

                item_group = ET.SubElement(mdv, "ItemGroupDef")
                item_group.set("OID", f"IG.{domain_spec.domain}")
                item_group.set("Name", domain_spec.domain)
                item_group.set("Repeating", "Yes" if domain_spec.domain != "DM" else "No")
                item_group.set("Purpose", "Tabulation")
                item_group.set("def:Structure", domain_spec.structure)
                item_group.set("def:Class", domain_spec.domain_class.value.replace("_", " ").title())

                # Description
                desc = ET.SubElement(item_group, "Description")
                ET.SubElement(desc, "TranslatedText").text = domain_spec.label

                # Item references
                for var in domain_spec.variables:
                    variable_count += 1
                    item_ref = ET.SubElement(item_group, "ItemRef")
                    item_ref.set("ItemOID", f"IT.{domain_spec.domain}.{var.name}")
                    item_ref.set("Mandatory", "Yes" if var.core == "Req" else "No")
                    if var.name in domain_spec.key_variables:
                        item_ref.set("KeySequence", str(domain_spec.key_variables.index(var.name) + 1))

            # Item definitions
            for domain_spec in spec.domains:
                for var in domain_spec.variables:
                    item_def = ET.SubElement(mdv, "ItemDef")
                    item_def.set("OID", f"IT.{domain_spec.domain}.{var.name}")
                    item_def.set("Name", var.name)
                    item_def.set("DataType", self._xpt_datatype(var.data_type))
                    if var.length:
                        item_def.set("Length", str(var.length))
                    item_def.set("def:Label", var.label)

                    if var.controlled_term:
                        item_def.set("def:CodeListOID", f"CL.{var.controlled_term}")

                    # Description
                    desc = ET.SubElement(item_def, "Description")
                    ET.SubElement(desc, "TranslatedText").text = var.label

            # Convert to string
            xml_str = ET.tostring(root, encoding="unicode", method="xml")

            # Add XML declaration
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

            # Write to file if path provided
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(xml_content)
            elif self._output_dir:
                with open(self._output_dir / "define.xml", "w", encoding="utf-8") as f:
                    f.write(xml_content)

            return DefineXmlResult(
                content=xml_content,
                domains=domain_names,
                variable_count=variable_count,
                success=True,
            )

        except Exception as e:
            return DefineXmlResult(
                content="",
                domains=[],
                variable_count=0,
                success=False,
                errors=[str(e)],
            )

    def _xpt_datatype(self, data_type: SDTMDataType) -> str:
        """Convert SDTM data type to XPT/define.xml data type."""
        if data_type in (SDTMDataType.NUM, SDTMDataType.INTEGER):
            return "float"
        elif data_type in (SDTMDataType.DATE, SDTMDataType.DATETIME, SDTMDataType.DURATION):
            return "datetime"
        else:
            return "text"

    def generate_package(
        self,
        domain_data: dict[str, list[dict[str, Any]]],
        output_dir: str | Path,
        formats: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a complete SDTM package with all domains and metadata.

        Args:
            domain_data: Dictionary mapping domain codes to record lists
            output_dir: Output directory for files
            formats: List of formats to generate (csv, xpt). Default: both

        Returns:
            Package generation result
        """
        if not self._mapping_spec:
            return {
                "success": False,
                "errors": ["No mapping specification provided"],
            }

        self.set_output_dir(output_dir)
        formats = formats or ["csv", "xpt"]

        results: dict[str, list[GenerationResult]] = {"csv": [], "xpt": []}
        errors: list[str] = []

        for domain_code, records in domain_data.items():
            domain_spec = self._mapping_spec.get_domain(domain_code)
            if not domain_spec:
                errors.append(f"No specification found for domain: {domain_code}")
                continue

            if "csv" in formats:
                csv_result = self.generate_csv(domain_spec, records)
                results["csv"].append(csv_result)
                if not csv_result.success:
                    errors.extend(csv_result.errors)

            if "xpt" in formats:
                xpt_result = self.generate_xpt(domain_spec, records)
                results["xpt"].append(xpt_result)
                if not xpt_result.success:
                    errors.extend(xpt_result.errors)

        # Generate define.xml
        define_result = self.generate_define_xml()
        if not define_result.success:
            errors.extend(define_result.errors)

        return {
            "success": len(errors) == 0,
            "output_dir": str(output_dir),
            "domains": list(domain_data.keys()),
            "formats": formats,
            "csv_files": [r.file_path for r in results.get("csv", []) if r.file_path],
            "xpt_files": [r.file_path for r in results.get("xpt", []) if r.file_path],
            "define_xml": define_result.content if define_result.success else None,
            "errors": errors,
        }


# Singleton instance
_generator_instance: SDTMGenerator | None = None
_generator_lock = threading.Lock()


def get_sdtm_generator() -> SDTMGenerator:
    """Get the SDTM generator singleton."""
    global _generator_instance
    # VP-ThreadSafety-7: Double-checked locking for thread safety
    if _generator_instance is None:
        with _generator_lock:
            if _generator_instance is None:
                _generator_instance = SDTMGenerator()
    return _generator_instance
