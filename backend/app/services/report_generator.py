"""Report Generation Service.

Generates formatted clinical reports in various formats including:
- PDF reports
- Clinical document templates
- Structured exports
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, BinaryIO
from io import BytesIO
import threading


# ============================================================================
# Enums and Data Classes
# ============================================================================


class ReportFormat(Enum):
    """Supported report formats."""

    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


class ReportTemplate(Enum):
    """Available report templates."""

    CLINICAL_SUMMARY = "clinical_summary"
    DISCHARGE_SUMMARY = "discharge_summary"
    PROBLEM_LIST = "problem_list"
    MEDICATION_LIST = "medication_list"
    LAB_REPORT = "lab_report"
    NLP_EXTRACTION_REPORT = "nlp_extraction"
    BILLING_ANALYSIS = "billing_analysis"
    QUALITY_METRICS = "quality_metrics"


@dataclass
class ReportSection:
    """A section of a report."""

    title: str
    content: str
    subsections: list["ReportSection"] = field(default_factory=list)
    table_data: list[dict] | None = None
    bullet_points: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportData:
    """Input data for report generation."""

    title: str
    patient_id: str | None = None
    patient_name: str | None = None
    document_date: str | None = None
    author: str | None = None
    institution: str | None = None

    # Content sections
    sections: list[ReportSection] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GeneratedReport:
    """Generated report result."""

    report_id: str
    template: ReportTemplate
    format: ReportFormat
    filename: str
    content: bytes | str
    content_type: str
    size_bytes: int
    generated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# HTML Templates
# ============================================================================


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #1a1a2e;
            background: #f8f9fa;
            padding: 40px;
        }}
        .report-container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 3px solid #4361ee;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #4361ee;
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .header-meta {{
            color: #6c757d;
            font-size: 14px;
        }}
        .header-meta span {{
            margin-right: 20px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #2d3436;
            font-size: 20px;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .section h3 {{
            color: #495057;
            font-size: 16px;
            margin: 15px 0 10px 0;
        }}
        .section p {{
            margin-bottom: 10px;
            text-align: justify;
        }}
        .section ul {{
            margin-left: 20px;
            margin-bottom: 15px;
        }}
        .section li {{
            margin-bottom: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #495057;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .highlight {{
            background: #fff3cd;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .badge-primary {{
            background: #4361ee;
            color: white;
        }}
        .badge-success {{
            background: #2ecc71;
            color: white;
        }}
        .badge-warning {{
            background: #f39c12;
            color: white;
        }}
        .badge-danger {{
            background: #e74c3c;
            color: white;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            color: #6c757d;
            font-size: 12px;
            text-align: center;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .report-container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="header">
            <h1>{title}</h1>
            <div class="header-meta">
                {header_meta}
            </div>
        </div>
        {sections}
        <div class="footer">
            Generated on {generated_at} | Clinical Ontology Normalizer
        </div>
    </div>
</body>
</html>
"""

PDF_CSS = """
@page {
    size: letter;
    margin: 1in;
}
body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
}
h1 { font-size: 18pt; color: #2c3e50; margin-bottom: 10pt; }
h2 { font-size: 14pt; color: #34495e; margin-top: 15pt; margin-bottom: 8pt; }
h3 { font-size: 12pt; color: #7f8c8d; margin-top: 10pt; }
table { width: 100%; border-collapse: collapse; margin: 10pt 0; }
th, td { padding: 6pt; border: 1pt solid #bdc3c7; }
th { background: #ecf0f1; }
ul { margin-left: 15pt; }
"""


# ============================================================================
# Report Generator Service
# ============================================================================


class ReportGeneratorService:
    """Service for generating clinical reports."""

    def __init__(self):
        """Initialize the report generator."""
        self._report_counter = 0
        self._lock = threading.Lock()

    def _get_report_id(self) -> str:
        """Generate unique report ID."""
        with self._lock:
            self._report_counter += 1
            return f"RPT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self._report_counter:04d}"

    def generate_report(
        self,
        data: ReportData,
        template: ReportTemplate = ReportTemplate.CLINICAL_SUMMARY,
        format: ReportFormat = ReportFormat.HTML,
    ) -> GeneratedReport:
        """
        Generate a report from data.

        Args:
            data: Report data
            template: Report template to use
            format: Output format

        Returns:
            Generated report
        """
        report_id = self._get_report_id()

        if format == ReportFormat.HTML:
            content, content_type = self._generate_html(data, template)
            filename = f"{report_id}.html"
        elif format == ReportFormat.MARKDOWN:
            content, content_type = self._generate_markdown(data, template)
            filename = f"{report_id}.md"
        elif format == ReportFormat.JSON:
            content, content_type = self._generate_json(data, template)
            filename = f"{report_id}.json"
        elif format == ReportFormat.PDF:
            content, content_type = self._generate_pdf(data, template)
            filename = f"{report_id}.pdf"
        else:
            raise ValueError(f"Unsupported format: {format}")

        size = len(content) if isinstance(content, (bytes, str)) else 0

        return GeneratedReport(
            report_id=report_id,
            template=template,
            format=format,
            filename=filename,
            content=content,
            content_type=content_type,
            size_bytes=size,
            generated_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "patient_id": data.patient_id,
                "title": data.title,
                "section_count": len(data.sections),
            },
        )

    def _generate_html(
        self,
        data: ReportData,
        template: ReportTemplate,
    ) -> tuple[str, str]:
        """Generate HTML report."""
        # Build header meta
        meta_parts = []
        if data.patient_id:
            meta_parts.append(f"<span><strong>Patient ID:</strong> {data.patient_id}</span>")
        if data.patient_name:
            meta_parts.append(f"<span><strong>Patient:</strong> {data.patient_name}</span>")
        if data.document_date:
            meta_parts.append(f"<span><strong>Date:</strong> {data.document_date}</span>")
        if data.author:
            meta_parts.append(f"<span><strong>Author:</strong> {data.author}</span>")
        header_meta = " ".join(meta_parts)

        # Build sections
        sections_html = []
        for section in data.sections:
            sections_html.append(self._render_section_html(section))

        html = HTML_TEMPLATE.format(
            title=data.title,
            header_meta=header_meta,
            sections="\n".join(sections_html),
            generated_at=data.generated_at,
        )

        return html, "text/html"

    def _render_section_html(self, section: ReportSection) -> str:
        """Render a section as HTML."""
        html = f'<div class="section">\n<h2>{section.title}</h2>\n'

        if section.content:
            html += f"<p>{section.content}</p>\n"

        if section.bullet_points:
            html += "<ul>\n"
            for point in section.bullet_points:
                html += f"<li>{point}</li>\n"
            html += "</ul>\n"

        if section.table_data:
            html += self._render_table_html(section.table_data)

        for subsection in section.subsections:
            html += f"<h3>{subsection.title}</h3>\n"
            if subsection.content:
                html += f"<p>{subsection.content}</p>\n"
            if subsection.bullet_points:
                html += "<ul>\n"
                for point in subsection.bullet_points:
                    html += f"<li>{point}</li>\n"
                html += "</ul>\n"

        html += "</div>\n"
        return html

    def _render_table_html(self, table_data: list[dict]) -> str:
        """Render table data as HTML."""
        if not table_data:
            return ""

        headers = list(table_data[0].keys())
        html = "<table>\n<thead>\n<tr>\n"
        for h in headers:
            html += f"<th>{h}</th>\n"
        html += "</tr>\n</thead>\n<tbody>\n"

        for row in table_data:
            html += "<tr>\n"
            for h in headers:
                value = row.get(h, "")
                html += f"<td>{value}</td>\n"
            html += "</tr>\n"

        html += "</tbody>\n</table>\n"
        return html

    def _generate_markdown(
        self,
        data: ReportData,
        template: ReportTemplate,
    ) -> tuple[str, str]:
        """Generate Markdown report."""
        lines = [f"# {data.title}\n"]

        # Metadata
        if data.patient_id:
            lines.append(f"**Patient ID:** {data.patient_id}  ")
        if data.patient_name:
            lines.append(f"**Patient:** {data.patient_name}  ")
        if data.document_date:
            lines.append(f"**Date:** {data.document_date}  ")
        if data.author:
            lines.append(f"**Author:** {data.author}  ")
        lines.append("")

        # Sections
        for section in data.sections:
            lines.append(f"## {section.title}\n")

            if section.content:
                lines.append(f"{section.content}\n")

            if section.bullet_points:
                for point in section.bullet_points:
                    lines.append(f"- {point}")
                lines.append("")

            if section.table_data:
                lines.append(self._render_table_markdown(section.table_data))

            for subsection in section.subsections:
                lines.append(f"### {subsection.title}\n")
                if subsection.content:
                    lines.append(f"{subsection.content}\n")
                if subsection.bullet_points:
                    for point in subsection.bullet_points:
                        lines.append(f"- {point}")
                    lines.append("")

        lines.append(f"\n---\n*Generated on {data.generated_at}*")

        return "\n".join(lines), "text/markdown"

    def _render_table_markdown(self, table_data: list[dict]) -> str:
        """Render table data as Markdown."""
        if not table_data:
            return ""

        headers = list(table_data[0].keys())
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]

        for row in table_data:
            values = [str(row.get(h, "")) for h in headers]
            lines.append("| " + " | ".join(values) + " |")

        return "\n".join(lines) + "\n"

    def _generate_json(
        self,
        data: ReportData,
        template: ReportTemplate,
    ) -> tuple[str, str]:
        """Generate JSON report."""
        import json

        report_dict = {
            "title": data.title,
            "patient_id": data.patient_id,
            "patient_name": data.patient_name,
            "document_date": data.document_date,
            "author": data.author,
            "institution": data.institution,
            "generated_at": data.generated_at,
            "template": template.value,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "bullet_points": s.bullet_points,
                    "table_data": s.table_data,
                    "subsections": [
                        {
                            "title": sub.title,
                            "content": sub.content,
                            "bullet_points": sub.bullet_points,
                        }
                        for sub in s.subsections
                    ],
                }
                for s in data.sections
            ],
            "metadata": data.metadata,
        }

        return json.dumps(report_dict, indent=2), "application/json"

    def _generate_pdf(
        self,
        data: ReportData,
        template: ReportTemplate,
    ) -> tuple[bytes, str]:
        """
        Generate PDF report.

        Note: This creates a basic PDF using HTML conversion.
        For production, consider using reportlab or weasyprint.
        """
        # Generate HTML first
        html_content, _ = self._generate_html(data, template)

        # For now, return HTML as bytes with PDF content type
        # In production, you'd use weasyprint or reportlab here
        try:
            from weasyprint import HTML, CSS
            pdf_bytes = HTML(string=html_content).write_pdf(
                stylesheets=[CSS(string=PDF_CSS)]
            )
            return pdf_bytes, "application/pdf"
        except ImportError:
            # Fallback: return HTML bytes if weasyprint not available
            return html_content.encode("utf-8"), "text/html"

    def create_clinical_summary_report(
        self,
        patient_id: str,
        summary_data: dict[str, Any],
        format: ReportFormat = ReportFormat.HTML,
    ) -> GeneratedReport:
        """
        Create a clinical summary report from summary data.

        Args:
            patient_id: Patient identifier
            summary_data: Summary data from ClinicalSummarizerService
            format: Output format

        Returns:
            Generated report
        """
        sections = []

        # One-liner section
        if summary_data.get("one_liner"):
            sections.append(ReportSection(
                title="Summary",
                content=summary_data["one_liner"],
            ))

        # Problem list
        if summary_data.get("problem_list"):
            problems = summary_data["problem_list"]
            sections.append(ReportSection(
                title="Problem List",
                content=f"{len(problems)} active problems identified",
                table_data=[
                    {
                        "Problem": p.get("name", ""),
                        "Status": p.get("status", ""),
                        "ICD-10": p.get("icd10_code", ""),
                    }
                    for p in problems
                ],
            ))

        # Medications
        if summary_data.get("medications"):
            meds = summary_data["medications"]
            sections.append(ReportSection(
                title="Medications",
                content=f"{len(meds)} medications",
                bullet_points=[
                    f"{m.get('name', '')} {m.get('dose', '')} {m.get('frequency', '')}"
                    for m in meds
                ],
            ))

        # Critical findings
        if summary_data.get("critical_findings"):
            sections.append(ReportSection(
                title="Critical Findings",
                bullet_points=summary_data["critical_findings"],
            ))

        data = ReportData(
            title="Clinical Summary Report",
            patient_id=patient_id,
            sections=sections,
        )

        return self.generate_report(data, ReportTemplate.CLINICAL_SUMMARY, format)

    def create_nlp_extraction_report(
        self,
        document_id: str,
        extraction_data: dict[str, Any],
        format: ReportFormat = ReportFormat.HTML,
    ) -> GeneratedReport:
        """
        Create NLP extraction report.

        Args:
            document_id: Document identifier
            extraction_data: NLP extraction results
            format: Output format

        Returns:
            Generated report
        """
        sections = []

        # Summary
        sections.append(ReportSection(
            title="Extraction Summary",
            table_data=[
                {"Metric": "Total Mentions", "Value": extraction_data.get("total_mentions", 0)},
                {"Metric": "Conditions", "Value": extraction_data.get("conditions", 0)},
                {"Metric": "Medications", "Value": extraction_data.get("medications", 0)},
                {"Metric": "Measurements", "Value": extraction_data.get("measurements", 0)},
                {"Metric": "Procedures", "Value": extraction_data.get("procedures", 0)},
                {"Metric": "Avg Confidence", "Value": f"{extraction_data.get('avg_confidence', 0):.2%}"},
            ],
        ))

        # Mentions by section
        if extraction_data.get("mentions"):
            mentions_table = [
                {
                    "Text": m.get("text", "")[:50],
                    "Type": m.get("type", ""),
                    "OMOP Concept": m.get("omop_concept_id", ""),
                    "Confidence": f"{m.get('confidence', 0):.2%}",
                }
                for m in extraction_data["mentions"][:20]
            ]
            sections.append(ReportSection(
                title="Extracted Mentions",
                table_data=mentions_table,
            ))

        data = ReportData(
            title="NLP Extraction Report",
            metadata={"document_id": document_id},
            sections=sections,
        )

        return self.generate_report(data, ReportTemplate.NLP_EXTRACTION_REPORT, format)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "reports_generated": self._report_counter,
            "supported_formats": [f.value for f in ReportFormat],
            "available_templates": [t.value for t in ReportTemplate],
        }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: ReportGeneratorService | None = None
_service_lock = threading.Lock()


def get_report_generator_service() -> ReportGeneratorService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = ReportGeneratorService()

    return _service_instance


def reset_report_generator_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
