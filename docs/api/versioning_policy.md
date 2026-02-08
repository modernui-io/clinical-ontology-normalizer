# API Versioning and Deprecation Policy (CTO-8)

## Overview

This document defines the API versioning strategy, deprecation timeline, and
migration guidelines for the Clinical Ontology Normalizer platform. All public
API consumers must follow these guidelines when integrating with or migrating
between API versions.

## Versioning Strategy

### URI-Based Versioning

All API endpoints use URI-based versioning with the pattern:

```
/api/v{major}/{resource}
```

Examples:
- `/api/v1/patients`
- `/api/v1/documents`
- `/api/v2/patients/search`

### Version Format

- **Major versions** (`v1`, `v2`, `v3`) denote breaking changes
- Non-breaking additions are allowed within a major version
- Each major version is a complete, self-contained API surface

### Why URI-Based

- Explicit and visible in every request
- Easy to route and load-balance at the infrastructure level
- Clear in logs, documentation, and debugging
- No hidden version negotiation

## Version Lifecycle

Every API version follows a four-stage lifecycle:

```
CURRENT --> DEPRECATED --> SUNSET --> RETIRED
```

| Stage      | Description                                      | Duration          |
|------------|--------------------------------------------------|-------------------|
| CURRENT    | Fully supported, receives new features and fixes | Indefinite        |
| DEPRECATED | Supported but no new features; sunset notice active | >= 6 months    |
| SUNSET     | Read-only mode; write operations return 405      | >= 3 months       |
| RETIRED    | Fully removed; all requests return 410 Gone      | Permanent         |

### Transition Rules

1. Only **CURRENT** versions can be deprecated
2. Only **DEPRECATED** versions can be sunset
3. Only **SUNSET** versions can be retired
4. Transitions are one-way and irreversible

## Deprecation Timeline

### Minimum Notice Periods

| Transition              | Minimum Notice |
|-------------------------|---------------|
| Deprecation to Sunset   | 6 months      |
| Sunset to Retirement    | 3 months      |
| Total (Deprecation to Retirement) | 9 months |

### Notification Channels

Deprecation notices are communicated through:

1. **Response Headers** (RFC 8594):
   - `Deprecation: true` on deprecated endpoints
   - `Sunset: <HTTP-date>` with the sunset date
   - `Link: <replacement-url>; rel="successor-version"`

2. **Changelog**: Version changelog entries in the API management endpoints

3. **Developer Portal**: Published migration guides

## Breaking vs Non-Breaking Changes

### Breaking Changes (Require New Major Version)

- Removing an endpoint
- Removing or renaming a response field
- Adding a required request field
- Changing a field type (e.g., `string` to `integer`)
- Changing response status codes for success/error cases
- Changing authentication or authorization requirements
- Changing the HTTP method of an endpoint

### Non-Breaking Changes (Allowed Within Current Version)

- Adding new optional request fields
- Adding new response fields
- Adding new endpoints
- Adding new query parameters
- Adding new enum values (when clients handle unknown values)
- Relaxing validation constraints
- Adding new error codes

## Client Migration Guide Template

When migrating between API versions, follow this process:

### Step 1: Inventory

Audit all API calls your application makes to the current version.
Use the migration guide endpoint:

```
GET /api/v1/api-management/migration-guide/{from_version}/{to_version}
```

### Step 2: Review Breaking Changes

Check for breaking changes between versions:

```
POST /api/v1/api-management/check-breaking-changes
{
    "from_version": "v1",
    "to_version": "v2"
}
```

### Step 3: Update Endpoints

For each breaking change:
- Update the endpoint path (e.g., `/api/v1/...` to `/api/v2/...`)
- Update request schemas to match new requirements
- Update response handling for changed schemas

### Step 4: Test

Run integration tests against the new API version.
Verify all endpoints return expected responses.

### Step 5: Switch Traffic

Update your API base URL from `/api/v1/` to `/api/v2/`.
Monitor for errors during the transition.

### Rollback Plan

If issues arise, revert to the previous API version by:
1. Restoring the old base URL
2. Reverting any request/response handler changes
3. Verifying functionality against the previous version

## API Management Endpoints

The following endpoints are available for managing API versions:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/api-management/versions` | List all API versions |
| GET | `/api/v1/api-management/versions/{version}` | Version detail |
| GET | `/api/v1/api-management/versions/{version}/endpoints` | Endpoints in version |
| GET | `/api/v1/api-management/deprecated` | All deprecated endpoints |
| GET | `/api/v1/api-management/migration-guide/{from}/{to}` | Migration guide |
| GET | `/api/v1/api-management/client-usage` | Client version usage |
| POST | `/api/v1/api-management/check-breaking-changes` | Breaking change check |
| GET | `/api/v1/api-management/deprecation-policy` | Current policy |

## Client Usage Tracking

The platform tracks which API versions each client is using. Clients still
on deprecated versions will be identified and can be contacted to migrate.

Check current client distribution:

```
GET /api/v1/api-management/client-usage
```

## Policy Version

- **Policy Version**: 1.0
- **Effective Date**: January 15, 2024
- **Last Updated**: February 2026
