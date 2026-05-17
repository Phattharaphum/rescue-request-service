# Service Data

เอกสารนี้อธิบายโครงสร้างข้อมูลที่ระบบใช้งานจริง (runtime truth) ของ `rescue-request-service` โดยอ้างอิงจากโค้ดและ `template.yaml` ณ วันที่ตรวจสอบ **2026-05-16**

แหล่งอ้างอิงหลัก:
- `template.yaml`
- `src/application/usecases/*`
- `src/application/services/*`
- `src/adapters/persistence/*`
- `stream-service/src/*`

---

## 1) ภาพรวม Data Stores

ระบบใช้ DynamoDB 4 ตารางหลักดังนี้

| Logical Name | Physical Name Pattern | Key Schema | TTL | วัตถุประสงค์ |
|---|---|---|---|---|
| Rescue Request Domain Table | `RescueRequestTable-{stage}` | `PK` (HASH), `SK` (RANGE) | ไม่มี | เก็บข้อมูลคำร้องแบบ Single-table (master/current/events/lookup/projection) |
| Idempotency Table | `IdempotencyTable-{stage}` | `idempotencyKeyHash` (HASH) | `expiresAt` | กันการประมวลผลซ้ำและ replay response |
| Incident Catalog Table | `IncidentCatalogTable-{stage}` | `incidentId` (HASH) + GSI `CatalogOrderIndex` | ไม่มี | แคตตาล็อก incident สำหรับให้ client เลือก |
| Stream Event Log Table | `RescueRequestStreamEventLog-{stage}` | `streamKey` (HASH), `eventKey` (RANGE) | `expiresAt` | event log ภายในสำหรับ SSE stream relay |

---

## 2) RescueRequestTable-{stage}

### 2.1 Single-table Key Design

- Partition key: `PK` (String)
- Sort key: `SK` (String)
- ไม่มี GSI/LSI ในตารางนี้

### 2.2 Item Types ที่เขียนจริง

| itemType | PK Pattern | SK Pattern | ผู้เขียนหลัก | หน้าที่ |
|---|---|---|---|---|
| `MASTER` | `REQ#{requestId}` | `META` | `create_rescue_request` | ข้อมูลคำร้องตั้งต้น |
| `CURRENT_STATE` | `REQ#{requestId}` | `CURRENT` | `create_rescue_request`, transition/ingest/update usecases | snapshot สถานะปัจจุบัน |
| `STATUS_EVENT` | `REQ#{requestId}` | `EVENT#{version:010d}` | create/transition/ingest | event history แบบ append |
| `CITIZEN_UPDATE` | `REQ#{requestId}` | `UPDATE#{createdAt}#{updateId}` | `create_citizen_update` | audit ข้อมูลที่ประชาชนส่งเพิ่ม |
| `TRACKING_LOOKUP` | `TRACK#{phoneHash}` | `CODE#{trackingCodeHash}` | `create_rescue_request` | lookup จากเบอร์+tracking code |
| `PHONE_UNIQUE` | `PHONE#{phoneHash}` | `UNIQUE` | `create_rescue_request` | เก็บร่องรอยความเป็น unique ต่อเบอร์ |
| `INCIDENT_PROJECTION` | `INCIDENT#{incidentId}` | `REQUEST#{submittedAt}#{requestId}` | `create_rescue_request` | list คำร้องราย incident |
| `DUPLICATE_SIGNATURE` | `DUP#{signature}` | `REQUEST#{requestId}` | `create_rescue_request` | ตรวจคำร้องซ้ำใน time bucket |

### 2.3 Field Contract ราย itemType

#### 2.3.1 `MASTER`

ฟิลด์ที่เขียนจริง:

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `PK` | string | N | `REQ#{requestId}` |
| `SK` | string | N | `META` |
| `itemType` | string | N | `MASTER` |
| `requestId` | string (UUID) | N | uuid4 จากระบบ |
| `incidentId` | string | N | ต้องมีใน `IncidentCatalogTable` |
| `incidentType` | string | Y | มาจาก incident catalog (`incidentType`/`incident_type`) |
| `requestType` | enum string | N | `MEDICAL`, `EVACUATION`, `SUPPLY` |
| `description` | string | N | รายละเอียดคำร้อง |
| `peopleCount` | integer | N | ต้อง `>=1` |
| `specialNeeds` | any | Y | เก็บค่าตาม payload |
| `latitude` | number | N | ช่วง `-90..90` |
| `longitude` | number | N | ช่วง `-180..180` |
| `locationDetails` | any | Y | เก็บค่าตาม payload |
| `province` | string | Y |  |
| `district` | string | Y |  |
| `subdistrict` | string | Y |  |
| `addressLine` | string | Y |  |
| `contactName` | string | N |  |
| `contactPhone` | string | N | เก็บ raw ตามที่รับเข้า |
| `contactPhoneNormalized` | string | N | normalize เป็นตัวเลข (ไทย `+66/66` -> `0`) |
| `contactPhoneHash` | string | N | SHA-256 ของ `phone:{normalized_phone}` |
| `trackingCodeHash` | string | N | SHA-256 ของ `tracking:{tracking_code}` |
| `sourceChannel` | enum string | N | `WEB`, `MOBILE`, `LINE`, `PHONE`, `WALK_IN`, `OTHER` |
| `submittedAt` | ISO-8601 string | N | เวลา create |
| `lastCitizenUpdateAt` | ISO-8601 string | Y | อัปเดตเมื่อมี citizen update |

#### 2.3.2 `CURRENT_STATE`

ฟิลด์ที่เขียนจริง:

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `PK` | string | N | `REQ#{requestId}` |
| `SK` | string | N | `CURRENT` |
| `itemType` | string | N | `CURRENT_STATE` |
| `requestId` | string | N |  |
| `incidentId` | string | N |  |
| `lastEventId` | string | N | ชี้ event ล่าสุดที่ apply แล้ว |
| `stateVersion` | integer | N | เวอร์ชันสถานะปัจจุบัน |
| `status` | enum string | N | `SUBMITTED`, `TRIAGED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CANCELLED` |
| `priorityScore` | number | Y | ระบบ validate 0..1 ตอน update/ingest |
| `priorityLevel` | string | Y | เช่น `LOW`, `NORMAL`, `HIGH`, `CRITICAL` จาก prioritization |
| `assignedUnitId` | string | Y | หน่วยที่ถูก assign |
| `assignedAt` | ISO-8601 string | Y | เวลา assign |
| `latestNote` | string | Y | note ล่าสุด |
| `lastUpdatedBy` | string | Y | ผู้/ระบบที่แก้ล่าสุด |
| `lastUpdatedAt` | ISO-8601 string | Y | เวลาแก้ล่าสุด |
| `latestPrioritySourceEventId` | string | Y | correlation สำหรับเทียบผลประเมิน prioritization |
| `latestPrioritySourceEventType` | string | Y | event type ต้นทางที่ส่งไป |
| `latestPrioritySourceOccurredAt` | ISO-8601 string | Y | เวลาของ source event |
| `latestPriorityEvaluationId` | string | Y | evaluate id ล่าสุดที่ ingest |
| `latestPriorityReason` | string | Y | เหตุผลจากผลประเมินล่าสุด |
| `latestPriorityEvaluatedAt` | ISO-8601 string | Y | เวลาที่ prioritization ประเมิน |
| `latestPriorityCorrelationId` | string | Y | correlationId ของข้อความประเมินที่รับเข้า |
| `lastPriorityIngestedAt` | ISO-8601 string | Y | เวลาที่ ingest ล่าสุด |
| `latestMissionId` | string | Y | mission id ล่าสุดที่ ingest |
| `latestMissionIncidentId` | string | Y | incident id จาก mission event ล่าสุด |
| `latestMissionRescueTeamId` | string | Y | rescue team ล่าสุด |
| `latestMissionChangedBy` | string | Y | changedBy จาก mission event ล่าสุด |
| `latestMissionStatus` | string | Y | ค่า mission status ล่าสุด (`EN_ROUTE`, `ON_SITE`, `RESOLVED`, `NEED_BACKUP`) |
| `latestMissionStatusChangedAt` | ISO-8601 string | Y | changedAt จาก mission event |
| `lastMissionStatusIngestedAt` | ISO-8601 string | Y | เวลา ingest mission ล่าสุด |

หมายเหตุสำคัญ:
- API บางเส้นจะซ่อน field ภายในบางตัว (เช่น `PK`, `SK`, `itemType`, `latestPrioritySource*`) ออกจาก response
- ในโค้ดมี field legacy ที่ถูกซ่อน (`lastPrioritizationMessageId`, `lastPrioritizationMessageType`, `lastPrioritizationSentAt`) แต่ flow ปัจจุบันไม่ได้เขียนค่า field กลุ่มนี้

#### 2.3.3 `STATUS_EVENT`

ฟิลด์ที่เขียนจริง:

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `PK` | string | N | `REQ#{requestId}` |
| `SK` | string | N | `EVENT#{version:010d}` |
| `itemType` | string | N | `STATUS_EVENT` |
| `eventId` | string (UUID) | N |  |
| `requestId` | string | N |  |
| `previousStatus` | string | Y | event แรกเป็น `null` |
| `newStatus` | string | N | request status ใหม่ |
| `changedBy` | string | N | ผู้กระทำ/ระบบต้นทาง |
| `changedByRole` | string | N | role ของผู้กระทำ |
| `changeReason` | string | Y |  |
| `meta` | object | Y | metadata เพิ่มเติม |
| `priorityScore` | number | Y |  |
| `responderUnitId` | string | Y |  |
| `missionId` | string | Y | มีใน mission-ingest event |
| `rescueTeamId` | string | Y | มีใน mission-ingest event |
| `version` | integer | N | เพิ่มทีละ 1 |
| `occurredAt` | ISO-8601 string | N | เวลาเกิด event |

#### 2.3.4 `CITIZEN_UPDATE`

ฟิลด์ที่เขียนจริง:

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `PK` | string | N | `REQ#{requestId}` |
| `SK` | string | N | `UPDATE#{createdAt}#{updateId}` |
| `itemType` | string | N | `CITIZEN_UPDATE` |
| `updateId` | string (UUID) | N |  |
| `requestId` | string | N |  |
| `updateType` | enum string | N | `NOTE`, `LOCATION_DETAILS`, `PEOPLE_COUNT`, `SPECIAL_NEEDS`, `CONTACT_INFO` |
| `updatePayload` | object | N | schema ตาม `updateType` |
| `citizenAuthMethod` | string | Y | ปัจจุบันตั้งค่าเป็น `tracking_code` |
| `citizenPhoneHash` | string | Y | เก็บเพื่อ audit (ปัจจุบันอาจเป็น `null`) |
| `trackingCodeHash` | string | N | hash ของ tracking code ที่ยืนยัน |
| `clientIp` | string | Y |  |
| `userAgent` | string | Y |  |
| `createdAt` | ISO-8601 string | N |  |

`updatePayload` ที่ระบบตรวจจริง:
- `NOTE`: ต้องมี `note` (string ไม่ว่าง)
- `LOCATION_DETAILS`: ต้องมี `locationDetails` (string ไม่ว่าง)
- `PEOPLE_COUNT`: ต้องมี `peopleCount` (int >= 1)
- `SPECIAL_NEEDS`: ต้องมี `specialNeeds` (string ไม่ว่าง)
- `CONTACT_INFO`: ต้องมีอย่างน้อยหนึ่งค่าใน `contactPhone` หรือ `contactName`

#### 2.3.5 `TRACKING_LOOKUP`

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `PK` | string | N | `TRACK#{phoneHash}` |
| `SK` | string | N | `CODE#{trackingCodeHash}` |
| `itemType` | string | N | `TRACKING_LOOKUP` |
| `phoneHash` | string | N | SHA-256 ของ `phone:{normalized_phone}` |
| `trackingCodeHash` | string | N | SHA-256 ของ `tracking:{tracking_code}` |
| `requestId` | string | N |  |
| `incidentId` | string | N |  |
| `createdAt` | ISO-8601 string | N |  |

#### 2.3.6 `PHONE_UNIQUE`

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `PK` | string | N | `PHONE#{phoneHash}` |
| `SK` | string | N | `UNIQUE` |
| `itemType` | string | N | `PHONE_UNIQUE` |
| `phoneHash` | string | N |  |
| `requestId` | string | N |  |
| `createdAt` | ISO-8601 string | N |  |

#### 2.3.7 `INCIDENT_PROJECTION`

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `PK` | string | N | `INCIDENT#{incidentId}` |
| `SK` | string | N | `REQUEST#{submittedAt}#{requestId}` |
| `itemType` | string | N | `INCIDENT_PROJECTION` |
| `requestId` | string | N |  |
| `incidentId` | string | N |  |
| `status` | string | N | snapshot ตอนสร้าง (เริ่มที่ `SUBMITTED`) |
| `requestType` | string | N |  |
| `contactName` | string | N |  |
| `submittedAt` | ISO-8601 string | N |  |

หมายเหตุ:
- flow ปัจจุบันไม่ได้ update `status` ของ projection item นี้ตาม lifecycle ทุกครั้ง
- ตอน list ตาม incident ระบบจะ merge กับ `CURRENT_STATE` อีกทีเพื่อให้ status ล่าสุด

#### 2.3.8 `DUPLICATE_SIGNATURE`

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `PK` | string | N | `DUP#{signature}` |
| `SK` | string | N | `REQUEST#{requestId}` |
| `itemType` | string | N | `DUPLICATE_SIGNATURE` |
| `requestId` | string | N |  |
| `signature` | string | N | SHA-256 signature |
| `createdAt` | ISO-8601 string | N |  |

การคำนวณ `signature`:
- ใช้ `incidentId`, เบอร์ที่ normalize แล้ว, `requestType`, geohash (precision=7), และ time bucket 5 นาที (`DUPLICATE_TIME_BUCKET_MINUTES=5`)

### 2.4 Access Patterns ที่ใช้งานจริง

| Use Case | Query Pattern |
|---|---|
| อ่านคำร้องหลัก | `PK=REQ#{requestId}`, `SK=META` |
| อ่านสถานะปัจจุบัน | `PK=REQ#{requestId}`, `SK=CURRENT` |
| list status events | `PK=REQ#{requestId}` + `begins_with(SK, 'EVENT#')` |
| list citizen updates | `PK=REQ#{requestId}` + `begins_with(SK, 'UPDATE#')` |
| tracking lookup | `PK=TRACK#{phoneHash}`, `SK=CODE#{trackingCodeHash}` |
| pre-check เบอร์ซ้ำ | query `PK=TRACK#{phoneHash}` limit 1 |
| list request by incident | `PK=INCIDENT#{incidentId}` + `begins_with(SK, 'REQUEST#')` |
| pre-check duplicate signature | query `PK=DUP#{signature}` limit 1 |

### 2.5 พฤติกรรมการเขียนข้อมูล (สำคัญ)

- สร้างคำร้องใหม่ใช้ `TransactWriteItems` เขียนหลาย item พร้อมกัน
- เพิ่ม status event ใช้ transaction เพื่อเขียน `STATUS_EVENT` + update `CURRENT_STATE` ในชุดเดียว และรองรับ optimistic concurrency ด้วย `stateVersion`
- update บางส่วน (`update_master_fields`, `update_current_fields`) ใช้ `UpdateItem` พร้อม `attribute_exists(PK)`
- Citizen update ถูกเก็บเป็นแถวใหม่เสมอ (append)

ข้อสังเกตตามโค้ดปัจจุบัน:
- การกันคำร้องซ้ำจากเบอร์โทรเป็นการตรวจแบบ application pre-check ก่อนเขียน
- transaction ตอนสร้างคำร้องไม่มี `ConditionExpression` ราย item โดยตรง

---

## 3) IdempotencyTable-{stage}

### 3.1 Key / TTL

- Partition key: `idempotencyKeyHash` (String)
- TTL field: `expiresAt` (epoch seconds)

### 3.2 Fields ที่ใช้งานจริง

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `idempotencyKeyHash` | string | N | SHA-256 scoped key |
| `operationName` | string | N | ชื่อ operation |
| `resourceScope` | string | N | scope ของ resource (เช่น `POST:/v1/rescue-requests`) |
| `scopeKey` | string | N | รูปแบบ `{operationName}:{resourceScope}` |
| `requestFingerprint` | string | N | SHA-256 ของ request body canonical JSON |
| `status` | enum string | N | `IN_PROGRESS`, `COMPLETED`, `FAILED` |
| `lockOwner` | string | Y | UUID lock owner |
| `lockedAt` | ISO-8601 string | Y |  |
| `lockExpiresAt` | ISO-8601 string | Y | timeout lock (ปัจจุบัน 5 นาที) |
| `createdAt` | ISO-8601 string | N |  |
| `updatedAt` | ISO-8601 string | N |  |
| `expiresAt` | integer | N | TTL (ปัจจุบัน 24 ชั่วโมง) |
| `clientId` | string | Y |  |
| `requestIp` | string | Y |  |
| `userAgent` | string | Y |  |
| `responseStatusCode` | integer | Y | เก็บเมื่อ finalize success |
| `responseBody` | string | Y | เก็บ body ที่ใช้ replay |
| `resultResourceId` | string | Y | เช่น requestId |
| `errorCode` | string | Y | เก็บเมื่อ finalize failure |
| `errorMessage` | string | Y | เก็บเมื่อ finalize failure |

### 3.3 Runtime Behavior

- hash key ที่ใช้จริง: `sha256("idempotency:{scopeKey}:{idempotency_key}")`
- ถ้าไม่ส่ง `resourceScope` จะ normalize เป็น `GLOBAL`
- ถ้า key เดิมแต่ fingerprint ต่างกัน -> conflict
- `IN_PROGRESS` ที่ lock หมดอายุ สามารถ reclaim ได้
- `FAILED` สามารถ retry ได้
- `COMPLETED` จะ replay จาก `responseStatusCode` และ `responseBody`
- implementation ปัจจุบันไม่ได้เขียน `responseHeaders` ลงตาราง

---

## 4) IncidentCatalogTable-{stage}

### 4.1 Key / Index

- PK: `incidentId` (String)
- GSI: `CatalogOrderIndex`
  - HASH: `catalogPartition`
  - RANGE: `catalogSortKey`

### 4.2 Fields ที่เขียนจริง

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `incidentId` | string | N | จาก upstream incident service |
| `incidentType` | string | Y | จาก `incident_type` |
| `incidentName` | string | N | ถ้าไม่เคยมีจะ generate แบบ `IncidentA`, `IncidentB`, ... |
| `incidentSequence` | integer | N | running sequence ภายในระบบ |
| `status` | string | Y | สถานะ incident จาก upstream |
| `incidentDescription` | string | Y | จาก `incident_description` |
| `remoteCreatedAt` | string | Y | จาก `created_at` |
| `remoteUpdatedAt` | string | Y | จาก `updated_at` |
| `lastSyncedAt` | ISO-8601 string | N | เวลา sync ล่าสุด |
| `catalogPartition` | string | N | ค่าคงที่ `CATALOG` |
| `catalogSortKey` | string | N | รูปแบบ `{sequence:06d}#{incidentId}` |

### 4.3 Sync Behavior

- sync job เรียก upstream API แล้ว upsert ลงตาราง
- หาก incident เดิมมีอยู่แล้วจะคง `incidentSequence` เดิม
- schedule ใน `template.yaml`: ทุก 30 นาที

---

## 5) RescueRequestStreamEventLog-{stage}

ตารางนี้ใช้ภายในสำหรับ stream relay (`/stream`) ไม่ใช่ domain source of truth หลัก

### 5.1 Key / TTL

- PK: `streamKey` (String)
- SK: `eventKey` (String)
- TTL: `expiresAt`

### 5.2 Item Families

#### 5.2.1 Stream Event Item

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `streamKey` | string | N | ปกติเป็น `STREAM` |
| `eventKey` | string | N | `{timestampMs(13 หลัก)}#{eventId}` |
| `payload` | object | N | ค่าหลังผ่าน `normalizeEvent(...)` |
| `createdAt` | ISO-8601 string | N | เวลา persist |
| `expiresAt` | integer | N | now + retention seconds |

#### 5.2.2 Poller Lease Item

| Field | Type | Nullable | หมายเหตุ |
|---|---|---|---|
| `streamKey` | string | N | `LOCK` |
| `eventKey` | string | N | `POLLER` (default) |
| `leaseOwner` | string | Y | owner ของ lease |
| `leaseExpiresAt` | integer(ms) | Y | lease timeout |
| `updatedAt` | ISO-8601 string | Y | เวลา update lease |

### 5.3 Retention

- `EVENT_RETENTION_SECONDS` ค่า default = `86400` (24 ชั่วโมง)

หมายเหตุเกี่ยวกับ `payload` ที่เก็บจริง:
- ถ้า message ขาเข้ามีโครงสร้าง `metadata` + `body` อยู่แล้ว จะเก็บตามนั้น
- ถ้า message ไม่ใช่รูปแบบดังกล่าว (เช่น envelope แบบ `header` + `body`) ระบบจะ wrap เป็น fallback object โดย
  - ตั้ง `metadata.eventType = rescue-request.unknown`
  - ใส่ payload เดิมไว้ใน `body`

---

## 6) Data Security / Data Exposure Notes

- ระบบเก็บ `contactPhone` แบบ raw ใน `MASTER` และใช้ hash (`contactPhoneHash`) สำหรับ lookup
- ระบบ **ไม่เก็บ tracking code แบบ plain text** (เก็บเฉพาะ `trackingCodeHash`)
- API projection บางเส้นจงใจซ่อน field ภายใน:
  - ลบ `PK`, `SK`, `itemType` ออกจาก response
  - `list_citizen_updates`/`get_rescue_request` ส่งเฉพาะ subset ของ citizen update (ไม่ส่ง hash/IP/UA)

---

## 7) ค่าคงที่สำคัญที่กระทบ Data Contract

- `IDEMPOTENCY_TTL_HOURS = 24`
- `_LOCK_TIMEOUT_MINUTES = 5` (idempotency lock)
- `DUPLICATE_TIME_BUCKET_MINUTES = 5`
- `TRACKING_CODE_LENGTH = 6`

เอกสารนี้สะท้อนพฤติกรรมและ schema ที่โค้ดเขียนลง storage จริงในปัจจุบัน หาก logic เปลี่ยนใน usecase/repository/stream-service ต้องอัปเดตเอกสารนี้ตามทันที
