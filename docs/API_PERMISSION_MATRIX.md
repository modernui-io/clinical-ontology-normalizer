# API Permission Matrix (CISO-9)

This document defines the mapping between API endpoint groups, required
permissions, and allowed roles. It serves as the authoritative reference for
the RBAC enforcement layer introduced in CISO-9 Phase 1.

## Roles

| Role          | Description                                        |
|---------------|----------------------------------------------------|
| ADMIN         | Full system access - all permissions                |
| PROVIDER      | Clinicians - read/write patients, trials, documents |
| COORDINATOR   | Study coordinators - read patients/trials, screen   |
| ANALYST       | Data analysts - read-only plus analytics & export   |
| VIEWER        | Read-only access to patients and trials             |
| SYSTEM        | Internal service calls - all permissions            |

## Permission Definitions

| Permission             | Description                                      |
|------------------------|--------------------------------------------------|
| READ_PATIENTS          | View patient records and demographics            |
| WRITE_PATIENTS         | Create/update patient records                    |
| READ_TRIALS            | View clinical trial details and enrollment       |
| WRITE_TRIALS           | Create/update/delete clinical trials             |
| SCREEN_PATIENTS        | Execute patient screening against trial criteria |
| READ_DOCUMENTS         | View clinical documents                          |
| WRITE_DOCUMENTS        | Upload/modify clinical documents                 |
| READ_AUDIT             | View audit logs and access history               |
| ADMIN                  | Administrative actions (system configuration)    |
| READ_ANALYTICS         | View dashboards and aggregate analytics          |
| MANAGE_USERS           | Create/modify/deactivate user accounts           |
| READ_CLINICAL_FACTS    | View extracted clinical facts                    |
| WRITE_CLINICAL_FACTS   | Create/modify clinical facts                     |
| EXPORT_DATA            | Export data (OMOP, FHIR, CSV)                    |
| READ_LINEAGE           | View data lineage and provenance records         |

## Role-Permission Matrix

| Permission             | ADMIN | PROVIDER | COORDINATOR | ANALYST | VIEWER | SYSTEM |
|------------------------|:-----:|:--------:|:-----------:|:-------:|:------:|:------:|
| READ_PATIENTS          |  Y    |    Y     |      Y      |    Y    |   Y    |   Y    |
| WRITE_PATIENTS         |  Y    |    Y     |             |         |        |   Y    |
| READ_TRIALS            |  Y    |    Y     |      Y      |    Y    |   Y    |   Y    |
| WRITE_TRIALS           |  Y    |    Y     |             |         |        |   Y    |
| SCREEN_PATIENTS        |  Y    |    Y     |      Y      |         |        |   Y    |
| READ_DOCUMENTS         |  Y    |    Y     |      Y      |         |        |   Y    |
| WRITE_DOCUMENTS        |  Y    |    Y     |             |         |        |   Y    |
| READ_AUDIT             |  Y    |          |             |         |        |   Y    |
| ADMIN                  |  Y    |          |             |         |        |   Y    |
| READ_ANALYTICS         |  Y    |          |             |    Y    |        |   Y    |
| MANAGE_USERS           |  Y    |          |             |         |        |   Y    |
| READ_CLINICAL_FACTS    |  Y    |    Y     |             |    Y    |        |   Y    |
| WRITE_CLINICAL_FACTS   |  Y    |    Y     |             |         |        |   Y    |
| EXPORT_DATA            |  Y    |          |             |    Y    |        |   Y    |
| READ_LINEAGE           |  Y    |    Y     |      Y      |    Y    |        |   Y    |

## Endpoint Permission Requirements

### Patient Management

| Endpoint                             | Method | Permission(s)              | Enforced? | Notes |
|--------------------------------------|--------|----------------------------|-----------|-------|
| `/api/v1/patients`                   | GET    | READ_PATIENTS              | Phase 1   | List all patients |
| `/api/v1/patients/{id}/graph`        | GET    | READ_PATIENTS              | Phase 1   | Patient KG |
| `/api/v1/patients/{id}/graph/build`  | POST   | WRITE_PATIENTS             | Phase 1   | Rebuild KG |
| `/api/v1/patients/{id}/facts`        | GET    | READ_CLINICAL_FACTS        | Phase 1   | Patient facts |

### Trial Management

| Endpoint                             | Method | Permission(s)              | Enforced? | Notes |
|--------------------------------------|--------|----------------------------|-----------|-------|
| `/api/v1/trials`                     | GET    | READ_TRIALS                | Phase 1   | List trials |
| `/api/v1/trials`                     | POST   | WRITE_TRIALS               | Phase 1   | Create trial |
| `/api/v1/trials/{id}`               | GET    | READ_TRIALS                | Phase 1   | Trial details |
| `/api/v1/trials/{id}`               | PUT    | WRITE_TRIALS               | Phase 1   | Update trial |
| `/api/v1/trials/{id}`               | DELETE | WRITE_TRIALS               | Phase 1   | Delete trial |
| `/api/v1/trials/stats`              | GET    | READ_TRIALS                | Phase 1   | Service stats |

### Screening

| Endpoint                             | Method | Permission(s)              | Enforced? | Notes |
|--------------------------------------|--------|----------------------------|-----------|-------|
| `/api/v1/trials/{id}/screen`         | POST   | SCREEN_PATIENTS            | Phase 1   | Screen patients |
| `/api/v1/trials/{id}/check/{pid}`    | GET    | SCREEN_PATIENTS            | Phase 1   | Check eligibility |
| `/api/v1/trials/{id}/matches/{pid}/explanation` | GET | SCREEN_PATIENTS   | Phase 1   | Match explanation |

### Enrollment

| Endpoint                             | Method | Permission(s)              | Enforced? | Notes |
|--------------------------------------|--------|----------------------------|-----------|-------|
| `/api/v1/trials/{id}/enroll`         | POST   | WRITE_TRIALS               | Phase 1   | Enroll patient |
| `/api/v1/trials/{id}/enrollments/{pid}` | PUT | WRITE_TRIALS               | Phase 1   | Update enrollment |
| `/api/v1/trials/{id}/enrollments`    | GET    | READ_TRIALS                | Phase 1   | List enrollments |

### False Negative Monitoring

| Endpoint                             | Method | Permission(s)              | Enforced? | Notes |
|--------------------------------------|--------|----------------------------|-----------|-------|
| `/api/v1/trials/{id}/patients/{pid}/flag-fn` | POST | SCREEN_PATIENTS     | Phase 1   | Flag FN |
| `/api/v1/trials/{id}/fn-report`      | GET    | READ_ANALYTICS             | Phase 1   | FN report |

### Dashboard

| Endpoint                             | Method | Permission(s)              | Enforced? | Notes |
|--------------------------------------|--------|----------------------------|-----------|-------|
| `/api/v1/trials/{id}/dashboard`      | GET    | READ_ANALYTICS             | Phase 1   | Trial dashboard |

### Data Lineage

| Endpoint                             | Method | Permission(s)              | Enforced? | Notes |
|--------------------------------------|--------|----------------------------|-----------|-------|
| `/api/v1/lineage/facts/{fact_id}`    | GET    | READ_LINEAGE               | Phase 1   | Fact lineage |
| `/api/v1/lineage/patients/{pid}`     | GET    | READ_LINEAGE               | Phase 1   | Patient lineage |
| `/api/v1/lineage/patients/{pid}/summary` | GET | READ_LINEAGE              | Phase 1   | Lineage summary |

### Endpoints Not Yet Protected (Future Phases)

The following endpoint groups do not have RBAC enforcement in Phase 1.
They are protected only by API-key or JWT authentication (if enabled).

| Group               | Approx Endpoints | Target Phase | Notes |
|----------------------|:-----------------:|:------------:|-------|
| Documents            | ~20               | Phase 2      | Ingest, NLP, CRUD |
| Billing / Coding     | ~40               | Phase 2      | HCC, CPT, claims |
| FHIR Import/Export   | ~15               | Phase 2      | R4 bundles |
| Knowledge Graph      | ~30               | Phase 3      | Graph query, RAG |
| Admin / Users        | ~10               | Phase 2      | User CRUD, role mgmt |
| Audit                | ~8                | Phase 2      | Log queries |
| Vocabulary           | ~12               | Phase 3      | OMOP lookup |
| Analytics            | ~15               | Phase 3      | Dashboards, reports |
| Export               | ~10               | Phase 3      | Bulk OMOP, CSV |
| All remaining        | ~550+             | Phase 4      | Long tail |

## Design Rationale

1. **Least privilege**: VIEWER has minimal read access; COORDINATOR adds
   screening; ANALYST adds analytics and export; PROVIDER adds write access
   to clinical data; ADMIN gets everything.

2. **Demo-mode bypass**: When `auth_enabled=False` and no API keys are
   configured, the PermissionChecker is a no-op. This keeps the demo and
   local development experience unchanged.

3. **Graceful degradation**: If the auth middleware does not populate a user
   role on the request, the checker allows the request through (with a debug
   log). This supports API-key-only auth setups where role information is
   not available.

4. **Audit trail**: Every permission denial is logged at WARNING level with
   the role, path, method, and missing permissions for post-incident review.

5. **SYSTEM role**: Reserved for internal service-to-service calls (e.g.,
   background jobs, webhook handlers). It has all permissions.
