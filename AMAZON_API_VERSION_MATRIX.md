# Amazon Advertising API Version Matrix (Campaign & Reporting)

| Ad Product | Campaign Creation / Management | Reporting / Data Retrieval | Notes |
|------------|--------------------------------|-----------------------------|-------|
| Sponsored Products (SP) | v3 (POST/PUT/GET under `/sp/v3/` where available) | v3 (migrated from v2 as of Mar 30 2023) | v2 deprecated Mar 30 2023; persistent 403 on legacy `/sp/campaigns` often indicates permission loss, not syntax. |
| Sponsored Brands (SB) | v4 (`/sb/v4/campaigns`) for multi-ad group | v3 (most reporting still via legacy endpoints; some remain v2 internally) | Amazon recommends migrating all v3 SB campaigns to v4; legacy v3 pre-Oct 2022 marked ARCHIVED by Aug 15 2024. |
| Sponsored Display (SD) | v2/v3 transitional (check docs) | v2 (scheduled shutdown Oct 31 2024; migrate to new version when GA) | Monitor deprecation timeline; plan migration before sunset. |

## Recommended Usage
- **SP**: Use `/sp/v3/` endpoints for both campaign reads and reporting. Avoid deprecated `/sp/campaigns` without version segment.
- **SB**: Use v4 for creating & managing campaigns (multi-ad group). Continue using existing reporting endpoints (v3) until Amazon publishes stable v4 reporting.
- **SD**: Prioritize migration planning; track official announcements for v3+ reporting endpoints.

## Permission Diagnostics Pattern
- Consistent 403 with body containing `Invalid key=value pair (missing equal-sign)` on SP endpoints while profiles succeed → Sponsored Products permission revoked/missing.
- Mixed success (SB/SD 200, SP 403) → isolate remediation to SP scope reauthorization.

## Headers & Version Indicators
- Primary versioning now conveyed via endpoint path (e.g. `/sp/v3/`). Older flows used `Amazon-Advertising-API-Version` header (keep only if explicitly required by docs; avoid sending mismatched versions).
- Ensure `Amazon-Advertising-API-ClientId`, `Amazon-Advertising-API-Scope` (profile ID), and `Authorization: Bearer <access_token>` always present.

## Migration Checklist (Summary)
1. Inventory endpoints used per ad product.
2. Replace legacy paths with versioned paths (`/sb/v4/`, `/sp/v3/`).
3. Re-test campaign CRUD and reporting retrieval.
4. Implement permission diagnostics (see `diagnose_sp_permissions.py`).
5. Document token & scope grant date in secret metadata.

---
Maintained: Nov 19 2025
