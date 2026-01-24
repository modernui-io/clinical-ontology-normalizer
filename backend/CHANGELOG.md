# API Changelog

All notable changes to the Clinical Ontology Normalizer API are documented here.

This project follows [Semantic Versioning](https://semver.org/).

## [1.3.0] - 2026-01-24

### Added
- Value set CRUD API (`/api/v1/value-sets`) with expand and validate operations
- OHDSI Data Quality Dashboard checks (`/api/v1/data-quality`)
- AI interaction audit log (`/api/v1/ai/audit`) with feedback support
- Mortality risk stratification endpoint (`/api/v1/risk/mortality`)
- Live search-as-you-type endpoint (`/api/v1/search/typeahead`)
- Session management enhancements: current session info, bulk revoke
- Pagination support for terminology operations ($lookup, $validate-code, $translate, $subsumes)
- Terminology operation caching with configurable TTL
- FHIR R4 Terminology Services conformance tests
- Standardized error response handlers (all errors return ErrorResponse format)
- Input validation middleware with field-level error messages
- OpenAPI spec examples for all major request/response models

## [1.2.0] - 2026-01-20

### Added
- Data consistency validation service (`/api/v1/data-quality/consistency`)
- Data completeness reporting (`/api/v1/data-quality/completeness`)
- Knowledge graph FHIR integration
- Graph analytics benchmarking
- KG health monitoring endpoints

## [1.1.0] - 2026-01-14

### Added
- Drug safety checking API with interaction, contraindication, and dosing endpoints
- ICD-10-CM code suggestion engine with CER citations
- CPT code suggestion engine with bundling analysis
- HCC gap analysis with RAF score calculation
- Differential diagnosis decision support
- FHIR R4 Terminology Services ($lookup, $expand, $validate-code, $translate, $subsumes, $closure)
- Clinical calculators (BMI, eGFR, MELD, CHA2DS2-VASc, Wells, CURB-65)
- Quality measures (HEDIS/CQM) calculation engine
- Patient timeline service
- Bulk FHIR export service
- CDS Hooks service
- Federated learning endpoints
- Synthetic data generation

### Changed
- Upgraded error handling with field-level suggestions
- Added rate limiting per endpoint
- Enhanced audit logging with PHI tracking

## [1.0.0] - 2026-01-01

### Added
- Initial API release
- Patient management endpoints
- Clinical document NLP processing
- OMOP vocabulary mapping
- Knowledge graph construction (Neo4j)
- Semantic search with embeddings
- Authentication and RBAC
- HIPAA-compliant audit logging
- Prometheus metrics
- Health check and readiness probes

### Security
- JWT-based authentication with refresh token rotation
- Role-based access control (RBAC)
- Request ID tracking for audit trail
- PII/PHI sanitization in error responses
