# No Secrets Manager Configuration Change

This change removes AWS Secrets Manager from Rescue Request Service runtime configuration.
IncidentTracking Service config and the internal maintenance API key now come directly
from Lambda environment variables.

## Runtime Values

| Config | Value | Used by |
|--------|-------|---------|
| `INCIDENT_SYNC_API_URL` | `https://incident-gateway-859kfcr6.uk.gateway.dev/api/v1/incidents` | Incident catalog sync Lambda |
| `INCIDENT_SYNC_API_KEY` | `123` | Incident catalog sync Lambda |
| `INCIDENT_SYNC_ACCEPT` | `application/json` | Incident catalog sync Lambda |
| `INCIDENT_SYNC_TRANSACTION_ID_HEADER` | `X-IncidentTNX-Id` | Incident catalog sync Lambda |
| `INTERNAL_API_KEY` | `6609612160G` | Internal maintenance APIs |

## What Changed

| Area | File | Change |
|------|------|--------|
| Runtime config constants | `src/shared/config.py` | Added direct env vars and removed `INCIDENT_SYNC_SECRET_ID` / `INTERNAL_API_KEY_SECRET_ID` usage. |
| Incident sync client | `src/adapters/external/incident_tracking_client.py` | Removed Secrets Manager client and reads IncidentTracking config from env vars. |
| Internal API key auth | `src/adapters/auth/internal_api_key.py` | Removed Secrets Manager client and compares requests against `INTERNAL_API_KEY`. |
| Deploy SAM template | `template.yaml` | Removed Secrets Manager resources, outputs, and IAM policies. Added literal env values. |
| Local SAM template | `template.local.yaml` | Removed local secret resource. Added literal env values. |
| Local bootstrap | `local/bootstrap/bootstrap_resources.ps1` | Stopped creating/updating Secrets Manager secrets and stopped waiting for the service. |
| LocalStack compose | `local/docker-compose.yml` | Removed `secretsmanager` from enabled LocalStack services. |
| Local env files | `.env`, `.env.example`, `.env.json` | Replaced secret ids with direct config variables. |
| Tests | `tests/unit/test_incident_tracking_client.py`, `tests/unit/test_internal_maintenance.py`, `tests/integration/test_internal_incident_catalog_flow.py` | Updated tests to use direct env configuration. |
| Docs | `README.md`, `docs/api-summary.md`, `docs/prioritization-incident-sync.md`, `docs/internal-maintenance-api.md` | Replaced Secrets Manager setup with environment variable setup. |

## Removed AWS Resources

- `IncidentTrackingApiSecret`
- `InternalApiKeySecret`
- `IncidentTrackingApiSecretArn` output
- `InternalApiKeySecretArn` output

## Removed IAM Permissions

- `AWSSecretsManagerGetSecretValuePolicy` from `InternalListIncidentCatalogFunction`
- `AWSSecretsManagerGetSecretValuePolicy` from `InternalMaintenanceFunction`
- `AWSSecretsManagerGetSecretValuePolicy` from `SyncIncidentCatalogFunction`

## Operational Note

Because the values are now stored as Lambda environment variables, rotating either API key
requires updating the SAM template or deployment environment and redeploying the stack.
