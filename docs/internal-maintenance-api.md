# Internal Maintenance API

เอกสารนี้อธิบายเส้น internal สำหรับดูแลข้อมูลของ Rescue Request Service

ทุกเส้นต้องส่ง header:

```http
api-key: <internal api key>
```

ค่า `api-key` จะถูกเทียบกับค่าใน environment variable `INTERNAL_API_KEY`
ซึ่งตอนนี้ตั้งค่าไว้ใน SAM template เป็น `6609612160G`

ถ้า header หายไปหรือค่าไม่ตรง ระบบจะตอบ `401 UNAUTHORIZED`

## Configuration

Lambda ใช้ environment variable:

| Name | Value |
|---|---|
| `INTERNAL_API_KEY` | Internal maintenance API key |

ใน SAM template มี resource:

| Resource | Purpose |
|---|---|
| `InternalListIncidentCatalogFunction` | อ่าน IncidentCatalog แบบ internal |
| `InternalMaintenanceFunction` | ลบ IncidentCatalog และ/หรือ RescueRequest data |

## Routes

Base URL:

```text
https://{api-id}.execute-api.{region}.amazonaws.com/{stage}
```

### 1. List IncidentCatalog

```http
GET /v1/internal/incidents/catalog
```

คืนรายการ IncidentCatalog ใน shape สำหรับ internal/debug

### 2. Clear IncidentCatalog Only

```http
DELETE /v1/internal/incidents/catalog
```

ลบ IncidentCatalog ทั้งหมด แต่ไม่ลบ request เก่า

Response:

```json
{
  "operation": "clear_incident_catalog",
  "deletedIncidents": 10,
  "deletedRequestItems": 0
}
```

### 3. Clear IncidentCatalog With Existing Requests

```http
DELETE /v1/internal/incidents/catalog/with-requests
```

ลบ IncidentCatalog ทั้งหมด และลบ request เก่าทั้งหมดใน `RescueRequestTable`

Response:

```json
{
  "operation": "clear_incident_catalog",
  "deletedIncidents": 10,
  "deletedRequestItems": 250
}
```

### 4. Delete Requests Whose Incident Is Missing From IncidentCatalog

```http
DELETE /v1/internal/rescue-requests/orphaned
```

ลบ request ทั้งหมดที่ `MASTER.incidentId` ไม่มีอยู่ใน IncidentCatalog ปัจจุบัน
การลบจะลบทุก item ที่มี `requestId` เดียวกัน เช่น `META`, `CURRENT`, `EVENT`, `UPDATE`,
tracking lookup, phone unique, duplicate signature, และ incident projection

Response:

```json
{
  "operation": "delete_orphaned_requests",
  "deletedRequests": 3,
  "deletedRequestItems": 21
}
```

### 5. Clear All Requests

```http
DELETE /v1/internal/rescue-requests
```

ลบ request ทั้งหมดใน `RescueRequestTable` แต่ไม่ลบ IncidentCatalog

Response:

```json
{
  "operation": "clear_requests",
  "deletedRequestItems": 250
}
```

### 6. Clear IncidentCatalog And All Requests

```http
DELETE /v1/internal/maintenance/all
```

ลบ IncidentCatalog ทั้งหมด และลบ request ทั้งหมด

Response:

```json
{
  "operation": "clear_all_data",
  "deletedIncidents": 10,
  "deletedRequestItems": 250
}
```

## IAM

Internal functions ใช้ least-privilege IAM:

| Function | Permission |
|---|---|
| `InternalListIncidentCatalogFunction` | `dynamodb:Scan` เฉพาะ `IncidentCatalogTable` |
| `InternalMaintenanceFunction` | `dynamodb:Scan`, `dynamodb:BatchWriteItem`, `dynamodb:DeleteItem` เฉพาะ `IncidentCatalogTable` และ `RescueRequestTable` |

## cURL Examples

```bash
curl -X DELETE "$BASE_URL/v1/internal/rescue-requests/orphaned" \
  -H "api-key: $INTERNAL_API_KEY"
```

```bash
curl -X DELETE "$BASE_URL/v1/internal/maintenance/all" \
  -H "api-key: $INTERNAL_API_KEY"
```

## Notes

- เส้นเหล่านี้เป็น destructive operation และไม่มีการ publish domain event ออก SNS
- การลบ request หมายถึงลบ item ทั้งหมดใน `RescueRequestTable` ที่เกี่ยวข้องกับ request นั้น
- ถ้าต้องการล้างข้อมูล production ควร backup DynamoDB ก่อนเรียกใช้งาน
