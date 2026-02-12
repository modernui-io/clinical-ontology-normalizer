# LOC Baseline (2026-02-10)

## Snapshot Metadata
- Captured: 2026-02-10 04:47:29 UTC (2026-02-09 23:47:29 EST)
- Source: tracked files from `git ls-files`
- Files counted: `1772`
- Total tracked LOC: `4,201,735`

## Composition
| Category | LOC | Share |
|---|---:|---:|
| Data-like (`json`/`csv`) | 3,241,852 | 77.15% |
| Source-like (code extensions) | 913,966 | 21.75% |
| Docs (`md`/`txt`) | 41,721 | 0.99% |
| Other | 4,196 | 0.10% |

Key point: repository scale is dominated by fixtures/data, but executable code is still very large.

## Extension Breakdown (Top)
| Ext | Files | LOC |
|---|---:|---:|
| `json` | 36 | 3,241,790 |
| `py` | 1,239 | 767,693 |
| `tsx` | 225 | 127,117 |
| `md` | 111 | 40,826 |
| `ts` | 37 | 9,224 |
| `lock` | 1 | 3,171 |
| `yaml` | 31 | 2,853 |
| `tf` | 21 | 2,827 |
| `yml` | 11 | 2,293 |
| `txt` | 11 | 895 |

## Top-Level Directory Breakdown
| Path | Files | LOC |
|---|---:|---:|
| `backend` | 1,296 | 3,970,628 |
| `frontend` | 285 | 152,339 |
| `docs` | 69 | 32,034 |
| `codebase_kg.json` | 1 | 22,179 |
| `fixtures` | 4 | 7,831 |
| `infrastructure` | 24 | 2,911 |
| `exec-review` | 9 | 2,873 |
| `k8s` | 29 | 2,710 |
| `tasks` | 11 | 2,175 |
| `.github` | 11 | 1,894 |

## Backend Concentration
- `backend/app`: 824 files, 503,103 LOC
- `backend/tests`: 332 files, 231,184 LOC
- `backend/fixtures`: 17 files, 3,193,605 LOC

### `backend/app` breakdown
| Path | Files | LOC | Share of `backend/app` |
|---|---:|---:|---:|
| `backend/app/services` | 343 | 303,578 | 60.34% |
| `backend/app/api` | 256 | 122,436 | 24.34% |
| `backend/app/schemas` | 153 | 51,117 | 10.16% |
| `backend/app/models` | 23 | 6,437 | 1.28% |
| `backend/app/connectors` | 8 | 6,313 | 1.25% |
| `backend/app/etl` | 12 | 5,400 | 1.07% |
| `backend/app/core` | 15 | 3,149 | 0.63% |
| `backend/app/scripts` | 7 | 2,647 | 0.53% |
| `backend/app/main.py` | 1 | 1,176 | 0.23% |
| `backend/app/jobs` | 3 | 522 | 0.10% |

## Frontend Concentration
- `frontend/src`: 241 files, 130,698 LOC

### `frontend/src` notable slices
| Path | Files | LOC |
|---|---:|---:|
| `frontend/src/analytics` | 30 | 21,213 |
| `frontend/src/clinical` | 18 | 9,979 |
| `frontend/src/etl` | 9 | 8,516 |
| `frontend/src/admin` | 8 | 6,556 |
| `frontend/src/billing` | 8 | 6,184 |
| `frontend/src/quality` | 3 | 3,838 |
| `frontend/src/cohorts` | 4 | 3,762 |
| `frontend/src/valuesets` | 4 | 3,501 |
| `frontend/src/patients` | 5 | 3,246 |
| `frontend/src/KnowledgeGraph` | 6 | 3,108 |

## Largest Files (Top 15)
| LOC | Path |
|---:|---|
| 732,411 | `backend/fixtures/snomed_codes.json` |
| 678,261 | `backend/fixtures/snomed_concepts.json` |
| 544,029 | `backend/fixtures/icd10_codes_full.json` |
| 495,171 | `backend/fixtures/omop_vocabulary_comprehensive.json` |
| 292,669 | `backend/fixtures/rxnorm_drugs.json` |
| 139,719 | `backend/fixtures/loinc_measurements.json` |
| 101,579 | `backend/fixtures/icd10_codes.json` |
| 85,758 | `backend/fixtures/cpt_codes_full.json` |
| 74,774 | `backend/fixtures/cpt_codes.json` |
| 36,485 | `backend/fixtures/clinical_guidelines.json` |
| 22,179 | `codebase_kg.json` |
| 15,051 | `frontend/package-lock.json` |
| 12,713 | `backend/app/services/calculator_definitions.py` |
| 5,745 | `backend/fixtures/drug_interactions_expanded.json` |
| 4,186 | `frontend/src/lib/api.ts` |

## API Inventory Snapshot
- Endpoints: `3,113`
- Methods: GET `1,680`, POST `935`, PUT `271`, DELETE `224`, PATCH `3`
- Maturity tiers: Pilot `2,745`, Production `283`, Scaffold `85`
- Auth flag: required `73`, not required `3,040`
- API files containing endpoints: `232`

## Raw Snapshot Artifacts
- `docs/swarm/data/loc_tracked_2026-02-10.tsv`
- `docs/swarm/data/loc_by_ext_2026-02-10.tsv`
- `docs/swarm/data/loc_by_topdir_2026-02-10.tsv`
- `docs/swarm/data/loc_backend_app_subdir_2026-02-10.tsv`
- `docs/swarm/data/loc_frontend_src_subdir_2026-02-10.tsv`
- `docs/swarm/data/largest_files_top40_2026-02-10.tsv`
- `docs/swarm/data/loc_major_scopes_2026-02-10.tsv`
- `docs/swarm/data/endpoint_inventory_2026-02-10.json`
