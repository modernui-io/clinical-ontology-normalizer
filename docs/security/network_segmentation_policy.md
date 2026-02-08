# Network Segmentation Policy (CISO-5)

## Overview

This document defines the network segmentation architecture for the Clinical Ontology Normalizer platform. The design implements a 4-tier zone model that enforces HIPAA-compliant network isolation for clinical trial patient recruitment infrastructure.

## Network Zones

### Tier Architecture

| Zone | VLAN | CIDR | Security Level | Purpose |
|------|------|------|----------------|---------|
| DMZ | 100 | 10.0.1.0/24 | 30 | Internet-facing: load balancer, WAF, API gateway |
| APPLICATION | 200 | 10.0.2.0/24 | 60 | Core services: FastAPI, Next.js, workers, NLP pipeline |
| DATA | 300 | 10.0.3.0/24 | 95 | Data stores: PostgreSQL, Redis, Neo4j (PHI/PII) |
| MANAGEMENT | 400 | 10.0.4.0/24 | 80 | Operations: Prometheus, Grafana, ELK, Alertmanager |

### Zone Properties

- **DMZ**: Terminates all external TLS connections. No direct access to DATA zone. Public-facing only.
- **APPLICATION**: Receives traffic from DMZ only. Connects to DATA zone on specific ports. All services require authentication.
- **DATA**: Highest security. No outbound traffic. Only APPLICATION and MANAGEMENT zones may connect inbound. All access authenticated and encrypted.
- **MANAGEMENT**: Monitoring access to all zones. Not reachable from DMZ. Requires authentication for all operations.

## Traffic Policies

### Allowed Flows

| Source | Destination | Protocol | Ports | Auth | Encrypted | Logging |
|--------|------------|----------|-------|------|-----------|---------|
| DMZ | APPLICATION | HTTPS | 443 | No | Yes | DETAILED |
| DMZ | APPLICATION | TCP | 8000 | No | Yes | BASIC |
| APPLICATION | DATA | TCP | 5432 | Yes | Yes | FULL |
| APPLICATION | DATA | TCP | 6379 | Yes | Yes | DETAILED |
| APPLICATION | DATA | TCP | 7687 | Yes | Yes | DETAILED |
| MANAGEMENT | DMZ | TCP/ICMP | 443, 9090, 9100 | Yes | Yes | BASIC |
| MANAGEMENT | APPLICATION | TCP/ICMP | 8000, 9090, 9100, 3000 | Yes | Yes | BASIC |
| MANAGEMENT | DATA | TCP | 5432, 6379, 7687, 9100 | Yes | Yes | DETAILED |
| MANAGEMENT | APPLICATION | TCP | 22 | Yes | Yes | FULL |
| MANAGEMENT | DATA | TCP | 22 | Yes | Yes | FULL |

### Denied Flows (Explicit)

| Source | Destination | Reason |
|--------|------------|--------|
| DMZ | DATA | Critical isolation: no direct internet-to-database path |
| DMZ | MANAGEMENT | Prevent external access to admin tools |
| DATA | DMZ | No outbound from data stores |
| DATA | APPLICATION | No reverse connections from databases |
| DATA | MANAGEMENT | No outbound from data stores |
| APPLICATION | DMZ | No reverse proxy connections |
| APPLICATION | MANAGEMENT | No direct admin access from app tier |

### Default Policy

All unmatched traffic is **DENIED** (default deny / zero-trust).

## Service Topology

### DMZ Services
- `nginx_load_balancer` (port 443, HTTPS) - Reverse proxy and load balancer
- `waf` (port 443, HTTPS) - Web Application Firewall

### APPLICATION Services
- `fastapi_backend` (port 8000, TCP) - Clinical ontology normalizer API [PHI]
- `nextjs_frontend` (port 3000, TCP) - Frontend application
- `celery_worker` (port 5555, TCP) - Background task workers [PHI]
- `nlp_pipeline` (port 8001, TCP) - NLP extraction pipeline [PHI]

### DATA Services
- `postgresql` (port 5432, TCP) - OMOP CDM primary database [PHI]
- `redis` (port 6379, TCP) - Cache and job queue [PHI]
- `neo4j` (port 7687, TCP) - Knowledge graph database [PHI]

### MANAGEMENT Services
- `prometheus` (port 9090, TCP) - Metrics collection
- `grafana` (port 3000, TCP) - Monitoring dashboards
- `elasticsearch` (port 9200, TCP) - Log storage
- `kibana` (port 5601, TCP) - Log visualization
- `alertmanager` (port 9093, TCP) - Alert management

## HIPAA Compliance

### Compliance Checks

The system performs 12 automated compliance checks mapped to HIPAA regulations:

| Check ID | Name | HIPAA Reference | Severity |
|----------|------|-----------------|----------|
| HIPAA-NET-001 | DMZ-to-DATA isolation | 45 CFR 164.312(e)(1) | Critical |
| HIPAA-NET-002 | DATA zone outbound restriction | 45 CFR 164.312(a)(1) | Critical |
| HIPAA-NET-003 | Encryption in transit | 45 CFR 164.312(e)(2)(ii) | Critical |
| HIPAA-NET-004 | Authentication on PHI access | 45 CFR 164.312(d) | Critical |
| HIPAA-NET-005 | Audit logging enabled | 45 CFR 164.312(b) | High |
| HIPAA-NET-006 | Network monitoring active | 45 CFR 164.308(a)(1)(ii)(D) | High |
| HIPAA-NET-007 | Minimum necessary access | 45 CFR 164.502(b) | High |
| HIPAA-NET-008 | DATA zone authentication | 45 CFR 164.312(d) | Critical |
| HIPAA-NET-009 | Management zone isolation | 45 CFR 164.312(a)(1) | High |
| HIPAA-NET-010 | Default deny policy | 45 CFR 164.312(e)(1) | Critical |
| HIPAA-NET-011 | PHI data classification | 45 CFR 164.312(a)(2)(iv) | High |
| HIPAA-NET-012 | Zone VLAN separation | 45 CFR 164.312(e)(1) | Medium |

### Scoring

- PASS = 100 points
- WARN = 50 points
- FAIL = 0 points
- Overall score = average across all checks
- HIPAA compliant = no FAIL results

## API Endpoints

All endpoints are under `/api/v1/security/network/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/zones` | List all network zones |
| GET | `/zones/{zone}` | Get zone detail with policies |
| GET | `/policies` | List all traffic policies |
| POST | `/validate-traffic` | Zero-trust traffic validation |
| GET | `/firewall-rules` | Generate iptables/nftables rules |
| GET | `/topology` | Service-to-zone topology map |
| GET | `/audit` | Run HIPAA compliance audit |

### Traffic Validation Example

```json
POST /api/v1/security/network/validate-traffic
{
    "source_zone": "APPLICATION",
    "destination_zone": "DATA",
    "protocol": "TCP",
    "port": 5432
}
```

Response:
```json
{
    "allowed": true,
    "matching_policy": "POL-003",
    "reason": "Traffic allowed by policy: APP to PostgreSQL (POL-003)",
    "authentication_required": true,
    "encryption_required": true,
    "logging_level": "FULL"
}
```

## Firewall Rule Generation

The system can generate firewall rules in two formats:

- **iptables**: Traditional Linux firewall rules
- **nftables**: Modern Linux firewall framework

Rules are generated from zone policies with a default DENY rule at the end.

### Example iptables Output

```
iptables -A FORWARD -s 10.0.1.0/24 -d 10.0.2.0/24 -p tcp --dport 443 -j ACCEPT -m comment --comment "DMZ to APP HTTPS"
iptables -A FORWARD -s 10.0.2.0/24 -d 10.0.3.0/24 -p tcp --dport 5432 -j ACCEPT -m comment --comment "APP to PostgreSQL"
iptables -A FORWARD -s 10.0.1.0/24 -d 10.0.3.0/24 -j DROP -m comment --comment "DENY DMZ to DATA"
iptables -A FORWARD -j DROP -m comment --comment "Default deny"
```

## Implementation Details

### Files

| File | Purpose |
|------|---------|
| `backend/app/schemas/network_segmentation.py` | Pydantic request/response models |
| `backend/app/services/network_segmentation_service.py` | Business logic and policy engine |
| `backend/app/api/network_segmentation.py` | FastAPI endpoints |
| `backend/tests/test_network_segmentation.py` | 69 tests covering all features |

### Key Design Decisions

1. **Zero-trust model**: All traffic is denied unless explicitly allowed by a policy rule.
2. **No DMZ-to-DATA path**: The most critical security rule prevents any direct path from internet-facing services to databases containing PHI.
3. **DATA zone is a dead end**: No outbound traffic from the data zone prevents data exfiltration.
4. **MANAGEMENT is isolated from DMZ**: Admin tools cannot be reached from the internet.
5. **Full audit logging on PHI paths**: All traffic policies touching PHI zones have DETAILED or FULL logging.
6. **Encryption everywhere**: All inter-zone traffic requires TLS/encryption.
