# Rescue Request Service: เอกสารอธิบายการทำงานแบบละเอียด

## 1. ภาพรวมของ Service

`Rescue Request Service` เป็น backend service สำหรับรับและจัดการคำร้องขอความช่วยเหลือจากประชาชนในสถานการณ์ภัยพิบัติ เช่น น้ำท่วม ไฟไหม้ เหตุฉุกเฉินทางการแพทย์ หรือเหตุที่ต้องอพยพคนออกจากพื้นที่เสี่ยง ระบบถูกออกแบบให้เป็นศูนย์กลางของข้อมูลคำร้อง ตั้งแต่การรับเรื่อง การบันทึกรายละเอียด การติดตามสถานะ การคัดกรอง การมอบหมายทีมกู้ภัย ไปจนถึงการปิดคำร้องเมื่อภารกิจเสร็จสิ้นหรือถูกยกเลิก

Service นี้ทำงานบนสถาปัตยกรรมแบบ serverless โดยใช้ AWS Lambda เป็นตัวประมวลผลหลัก, API Gateway เป็นทางเข้า REST API, DynamoDB เป็นฐานข้อมูลหลัก และ SNS/SQS เป็นกลไกสื่อสารแบบ asynchronous กับระบบอื่น เช่น Rescue Request Prioritization Service, Mission Progress Service และระบบ stream สำหรับ frontend

เป้าหมายหลักของ service คือทำให้คำร้องทุกคำร้องถูกเก็บอย่างเป็นระบบ ตรวจสอบย้อนหลังได้ ลดปัญหาคำร้องซ้ำ รองรับการ retry จากฝั่ง client อย่างปลอดภัย และเปิดให้ระบบอื่นเข้ามาช่วยประเมินความสำคัญหรืออัปเดตสถานะภารกิจได้โดยไม่ผูกติดกับ flow หลักของการรับคำร้อง

## 2. ขอบเขตความรับผิดชอบ

Service นี้รับผิดชอบงานหลักดังนี้

- รับคำร้องขอความช่วยเหลือจากประชาชนผ่าน public API
- ตรวจสอบข้อมูลที่จำเป็น เช่น incident, ประเภทคำร้อง, จำนวนคน, พิกัด และเบอร์ติดต่อ
- สร้าง `requestId` และ `trackingCode` สำหรับใช้ติดตามคำร้อง
- เก็บข้อมูลคำร้องหลัก สถานะล่าสุด ประวัติสถานะ และข้อมูลอัปเดตจากประชาชน
- ป้องกันการสร้างคำร้องซ้ำด้วย idempotency key, phone uniqueness และ duplicate signature
- จัดการ state machine ของคำร้อง เช่น `SUBMITTED`, `TRIAGED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CANCELLED`
- เปิด API สำหรับเจ้าหน้าที่ดูรายละเอียด แก้ไขข้อมูล ปรับ priority และเปลี่ยนสถานะ
- Publish domain events ไปยัง SNS เมื่อมีเหตุการณ์สำคัญเกิดขึ้น
- รับผลการประเมินความสำคัญจากระบบ Prioritization ผ่าน SQS
- รับสถานะภารกิจจาก Mission Progress Service ผ่าน SQS
- Sync รายการ incident จาก IncidentTracking Service มาเก็บไว้ใน local catalog
- ให้ health check สำหรับ liveness/readiness และตรวจสอบ dependency สำคัญ

สิ่งที่ service นี้ไม่ได้รับผิดชอบโดยตรง ได้แก่ การจัดสรรทรัพยากรกู้ภัยจริง การคำนวณแผนเส้นทาง การวินิจฉัยทางการแพทย์ การจัดการข้อมูล incident ต้นทางแบบเต็มรูปแบบ และการ scrape ข้อมูลจาก social media

## 3. ผู้ใช้งานและระบบที่เกี่ยวข้อง

### 3.1 ประชาชน

ประชาชนใช้ระบบเพื่อสร้างคำร้อง ติดตามสถานะ และส่งข้อมูลเพิ่มเติม เช่น จำนวนคนเปลี่ยน จุดรอความช่วยเหลือเปลี่ยน หรือมีความต้องการพิเศษเพิ่มเติม ประชาชนจะได้รับ `trackingCode` หลังสร้างคำร้องสำเร็จ และใช้คู่กับเบอร์ติดต่อในการยืนยันตัวตนสำหรับบาง flow

### 3.2 เจ้าหน้าที่คัดกรองและ dispatcher

เจ้าหน้าที่ใช้ระบบเพื่อดูรายละเอียดคำร้อง ตรวจสอบความครบถ้วน ปรับข้อมูล จัดลำดับความสำคัญ เปลี่ยนสถานะ และมอบหมายหน่วยกู้ภัยหรือทีมตอบสนอง

### 3.3 ทีมกู้ภัยหรือระบบภารกิจ

ทีมกู้ภัยหรือ Mission Progress Service สามารถส่งสถานะภารกิจกลับมายังระบบ เช่น ทีมกำลังเดินทางหรือภารกิจเสร็จสิ้น ข้อมูลเหล่านี้จะถูกแปลงเป็นสถานะของ rescue request ตาม mapping ที่กำหนด

### 3.4 ระบบภายนอก

- `IncidentTracking Service`: เป็นแหล่งข้อมูล incident ต้นทาง ระบบนี้ sync มาเก็บใน `IncidentCatalogTable`
- `Rescue Request Prioritization Service`: รับ event จากคำร้องหรือการอัปเดต แล้วส่งผลประเมิน priority กลับมา
- `Mission Progress Service`: ส่ง event สถานะภารกิจ เช่น `EN_ROUTE`, `ON_SITE`, `RESOLVED`, `NEED_BACKUP`
- frontend/stream consumers: รับ event หรืออ่านข้อมูลเพื่อแสดงผลแบบ real-time หรือ near real-time

## 4. สถาปัตยกรรมโดยรวม

องค์ประกอบหลักของระบบประกอบด้วย

- `API Gateway`: รับ HTTP request จาก frontend, citizen client, staff console และ internal tooling
- `AWS Lambda`: แยก handler ตาม use case เช่น create request, get status, patch request, command transition, ingest event
- `DynamoDB`: เก็บข้อมูลหลักของ service แบบ single-table design และตารางประกอบอื่น ๆ
- `SNS`: กระจาย domain event ที่ service publish ออกไปให้ระบบ downstream
- `SQS`: รับ event จากระบบภายนอกกลับเข้ามาประมวลผลแบบ asynchronous
- `EventBridge`: trigger scheduled sync สำหรับ incident catalog ทุก 30 นาที
- `LocalStack/SAM`: ใช้จำลอง resource สำหรับพัฒนาและทดสอบในเครื่อง

แนวคิดสำคัญคือแยก synchronous API flow ออกจาก asynchronous integration flow ให้ชัดเจน การสร้างคำร้องจะตอบกลับผู้ใช้ทันทีเมื่อบันทึกข้อมูลสำเร็จ ส่วนการประเมิน priority หรือการแจ้งระบบอื่นจะทำผ่าน event ภายหลัง ทำให้ flow หลักไม่ต้องรอระบบภายนอก

## 5. ข้อมูลหลักที่ Service เป็นเจ้าของ

### 5.1 Rescue Request

เป็นข้อมูลคำร้องหลักที่ประชาชนสร้าง ประกอบด้วย `requestId`, `incidentId`, `requestType`, `description`, `peopleCount`, พิกัด, รายละเอียดสถานที่, ข้อมูลติดต่อ, source channel, เวลาที่ส่งคำร้อง และข้อมูลอื่นที่เกี่ยวข้อง

### 5.2 Current State

เป็น snapshot สถานะล่าสุดของคำร้อง ใช้สำหรับตอบ API ที่ต้องการดูสถานะปัจจุบันอย่างรวดเร็ว เช่น status, stateVersion, priorityScore, priorityLevel, assignedUnitId, latestNote, lastUpdatedAt รวมถึง metadata จาก prioritization และ mission progress

### 5.3 Status Event

เป็นประวัติการเปลี่ยนสถานะแบบ append-only ทุกครั้งที่สถานะเปลี่ยน ระบบจะสร้าง event ใหม่พร้อม version ที่เพิ่มขึ้น ทำให้สามารถตรวจสอบย้อนหลังได้ว่าใครเปลี่ยนจากสถานะใดไปสถานะใด เมื่อไร และด้วยเหตุผลอะไร

### 5.4 Citizen Update

เป็นข้อมูลเพิ่มเติมจากประชาชนหลังจากสร้างคำร้องแล้ว เช่น note, รายละเอียดสถานที่, จำนวนคน, special needs หรือข้อมูลติดต่อเพิ่มเติม ข้อมูลนี้ช่วยให้เจ้าหน้าที่เห็นสถานการณ์ล่าสุดและ trigger ให้ระบบ prioritization ประเมินใหม่ได้

### 5.5 Incident Catalog

เป็นรายการ incident ที่ sync มาจาก IncidentTracking Service และเก็บไว้ใน local table เพื่อให้ frontend และ API อ่านได้โดยไม่ต้องเรียก upstream ทุกครั้ง

### 5.6 Idempotency Record

เป็นข้อมูลสำหรับจำคำขอที่เคยถูกประมวลผลแล้ว โดยใช้ `X-Idempotency-Key` เพื่อให้ client retry ได้โดยไม่สร้างข้อมูลซ้ำ ระบบจะเก็บ fingerprint, status, lock, response body และ TTL

## 6. ตาราง DynamoDB ที่ใช้

ระบบใช้ตารางหลักดังนี้

| Table | หน้าที่ |
| --- | --- |
| `RescueRequestTable-{stage}` | เก็บคำร้องหลัก current state status events citizen updates tracking lookup phone uniqueness incident projection และ duplicate signature |
| `IdempotencyTable-{stage}` | เก็บ idempotency key สำหรับ mutating operations |
| `IncidentCatalogTable-{stage}` | เก็บ incident catalog ที่ sync จาก IncidentTracking Service |
| `RescueRequestStreamEventLog-{stage}` | เก็บ event สำหรับ internal stream relay ของ frontend |

ใน `RescueRequestTable` ใช้ single-table design โดยมี item หลายชนิด เช่น `MASTER`, `CURRENT_STATE`, `STATUS_EVENT`, `CITIZEN_UPDATE`, `TRACKING_LOOKUP`, `PHONE_UNIQUE`, `INCIDENT_PROJECTION` และ `DUPLICATE_SIGNATURE`

## 7. ฟีเจอร์หลักของระบบ

### 7.1 สร้างคำร้องขอความช่วยเหลือ

ประชาชนส่งข้อมูลผ่าน `POST /v1/rescue-requests` โดยต้องระบุ incident, ประเภทคำร้อง, คำอธิบาย, จำนวนคน, พิกัด, ชื่อผู้ติดต่อ, เบอร์โทร และช่องทางที่ส่งคำร้อง ระบบจะตรวจสอบข้อมูลก่อนบันทึก และต้องตรวจว่า `incidentId` มีอยู่ใน `IncidentCatalogTable`

เมื่อสร้างสำเร็จ ระบบจะสร้าง

- `requestId` เป็น UUID ของคำร้อง
- `trackingCode` สำหรับประชาชนใช้ติดตามคำร้อง
- master record ของคำร้อง
- current state เริ่มต้นเป็น `SUBMITTED`
- status event แรก version `1`
- tracking lookup จาก phone hash + tracking code hash
- phone uniqueness record
- incident projection สำหรับ query ตาม incident
- duplicate signature สำหรับตรวจคำร้องซ้ำ

หลังจากบันทึกสำเร็จ ระบบจะ publish event `rescue-request.created` ไปยัง SNS เพื่อให้ downstream เช่น prioritization service นำไปประเมินความสำคัญต่อ

### 7.2 ติดตามสถานะโดยประชาชน

ประชาชนสามารถติดตามสถานะได้จาก `GET /v1/citizen/rescue-requests/{requestId}/status` ระบบจะคืนข้อมูลที่เหมาะสำหรับ citizen view เช่น สถานะล่าสุด คำอธิบาย จำนวนคน ข้อมูลสถานที่ เบอร์โทรแบบ masked priority ล่าสุด หน่วยที่ได้รับมอบหมาย และ recent events

ถ้าประชาชนจำ `requestId` ไม่ได้ สามารถใช้ `POST /v1/citizen/tracking/lookup` โดยส่งเบอร์ติดต่อและ tracking code เพื่อ lookup กลับมาเป็น `requestId` และ `incidentId`

### 7.3 ส่งข้อมูลเพิ่มเติมจากประชาชน

ประชาชนใช้ `POST /v1/citizen/rescue-requests/{requestId}/updates` เพื่อส่งข้อมูลเพิ่มเติม ต้องมี `trackingCode` เพื่อยืนยันว่าเป็นผู้ที่เกี่ยวข้องกับคำร้องจริง ระบบรองรับ update type ได้แก่

- `NOTE`: ข้อความทั่วไป
- `LOCATION_DETAILS`: รายละเอียดสถานที่เพิ่มเติม
- `PEOPLE_COUNT`: จำนวนคนที่ต้องการความช่วยเหลือ
- `SPECIAL_NEEDS`: ความต้องการพิเศษ
- `CONTACT_INFO`: ข้อมูลติดต่อเพิ่มเติม

คำร้องที่อยู่ใน terminal state (`RESOLVED` หรือ `CANCELLED`) จะไม่สามารถอัปเดตจากประชาชนได้ เมื่อบันทึก update สำเร็จ ระบบจะ publish `rescue-request.citizen-updated` เพื่อให้ระบบ prioritization หรือ consumer อื่นประเมินผลต่อ

### 7.4 ดูและจัดการคำร้องโดยเจ้าหน้าที่

เจ้าหน้าที่สามารถใช้ API กลุ่ม staff เพื่อดูรายละเอียด แก้ไขข้อมูล และตรวจสอบ timeline ของคำร้องได้ เช่น

- `GET /v1/rescue-requests/{requestId}` ดูรายละเอียดคำร้อง
- `PATCH /v1/rescue-requests/{requestId}` แก้ไขบาง field เช่น description, peopleCount, specialNeeds, locationDetails, addressLine
- `GET /v1/rescue-requests/{requestId}/events` ดูประวัติ status events
- `POST /v1/rescue-requests/{requestId}/events` append status event โดยระบุ `newStatus`
- `GET /v1/rescue-requests/{requestId}/current` ดู current state
- `GET /v1/incidents/{incidentId}/rescue-requests` ดูคำร้องทั้งหมดภายใต้ incident
- `PATCH /v1/rescue-requests/{requestId}/priority` ปรับ priority score, priority level หรือ note
- `GET /v1/idempotency-keys/{idempotencyKeyHash}` ตรวจสอบ idempotency record สำหรับ support/debug

### 7.5 State machine และ command endpoints

ระบบมี endpoint สำหรับเปลี่ยนสถานะตาม workflow โดยตรง

- `POST /v1/rescue-requests/{requestId}/triage`
- `POST /v1/rescue-requests/{requestId}/assign`
- `POST /v1/rescue-requests/{requestId}/start`
- `POST /v1/rescue-requests/{requestId}/resolve`
- `POST /v1/rescue-requests/{requestId}/cancel`

ทุก command จะเรียก logic เดียวกันคือ `execute_transition` เพื่อตรวจสอบสถานะปัจจุบัน ตรวจ version ถ้ามี `If-Match` ตรวจว่า transition ถูกต้องหรือไม่ สร้าง status event ใหม่ อัปเดต current state แล้ว publish event ที่เกี่ยวข้อง

### 7.6 จัดการ priority

Priority ของคำร้องสามารถมาจากสองทาง

1. เจ้าหน้าที่ปรับเองผ่าน `PATCH /v1/rescue-requests/{requestId}/priority`
2. ระบบ Prioritization ส่งผลประเมินกลับมาทาง SQS

ค่า priority ที่ใช้ ได้แก่ `priorityScore` ซึ่งเป็นตัวเลขระหว่าง `0` ถึง `1` และ `priorityLevel` เช่น `LOW`, `NORMAL`, `HIGH`, `CRITICAL`

เมื่อ priority score ถูกเปลี่ยนผ่าน staff endpoint ระบบจะ publish `rescue-request.priority-score-updated` เพื่อให้ dashboard, monitoring หรือระบบ downstream รับรู้

### 7.7 Incident catalog

ระบบไม่เรียก IncidentTracking Service โดยตรงทุกครั้งที่ผู้ใช้เปิดรายการ incident แต่ใช้ scheduled sync ผ่าน EventBridge ทุก 30 นาที แล้วเก็บผลไว้ใน `IncidentCatalogTable` จากนั้น API `GET /v1/incidents` จะอ่านจาก local catalog เท่านั้น ทำให้ client ยังใช้งานได้แม้ upstream incident service มีปัญหาชั่วคราว

### 7.8 Health check

ระบบมี health endpoints สำหรับ infrastructure และ monitoring

- `GET /v1/health/live`: ตรวจว่า Lambda/process ยังทำงานได้
- `GET /v1/health/ready`: ตรวจว่า dependency หลัก เช่น DynamoDB tables พร้อมใช้งาน
- `GET /v1/health`: รวม liveness และ readiness

## 8. สถานะของคำร้องและกฎการเปลี่ยนสถานะ

สถานะหลักของคำร้องมีดังนี้

| Status | ความหมาย |
| --- | --- |
| `SUBMITTED` | รับคำร้องเข้าระบบแล้ว ยังไม่ได้คัดกรอง |
| `TRIAGED` | เจ้าหน้าที่หรือระบบประเมินเบื้องต้นแล้ว |
| `ASSIGNED` | มีการมอบหมายหน่วยตอบสนองแล้ว |
| `IN_PROGRESS` | ทีมกู้ภัยกำลังดำเนินการ |
| `RESOLVED` | ภารกิจเสร็จสิ้น คำร้องถูกปิดสำเร็จ |
| `CANCELLED` | คำร้องถูกยกเลิก |

กฎ transition ที่ระบบอนุญาตคือ

| From | To ที่อนุญาต |
| --- | --- |
| `SUBMITTED` | `TRIAGED`, `ASSIGNED`, `CANCELLED` |
| `TRIAGED` | `ASSIGNED`, `CANCELLED` |
| `ASSIGNED` | `IN_PROGRESS`, `CANCELLED` |
| `IN_PROGRESS` | `RESOLVED`, `CANCELLED` |
| `RESOLVED` | ไม่มี |
| `CANCELLED` | ไม่มี |

เงื่อนไขเพิ่มเติมคือ

- ถ้าเปลี่ยนเป็น `ASSIGNED` ต้องมี `responderUnitId`
- ถ้าเปลี่ยนเป็น `CANCELLED` ต้องมี `reason`
- ถ้าคำร้องอยู่ใน `RESOLVED` หรือ `CANCELLED` แล้ว จะเปลี่ยนสถานะต่อไม่ได้
- ถ้าส่ง header `If-Match` ระบบจะเทียบกับ `stateVersion` ปัจจุบันเพื่อกัน concurrent update

## 9. Flow การทำงานหลักของระบบ

### 9.1 Flow สร้างคำร้องใหม่

1. ประชาชนเลือก incident จากรายการที่ sync ไว้ในระบบ
2. ประชาชนกรอกข้อมูลคำร้อง เช่น ประเภทคำร้อง รายละเอียด จำนวนคน พิกัด และเบอร์โทร
3. frontend เรียก `POST /v1/rescue-requests`
4. handler parse body และอ่าน header เช่น `X-Idempotency-Key`, client IP, user agent
5. use case ตรวจ required fields, phone, latitude, longitude, request type, source channel และ people count
6. ถ้ามี idempotency key ระบบจะ reserve key ก่อนเริ่มงาน
7. ระบบตรวจว่า `incidentId` มีอยู่ใน `IncidentCatalogTable`
8. ระบบ normalize เบอร์โทรและ hash เบอร์เพื่อใช้ตรวจ uniqueness
9. ถ้าเบอร์นี้เคยมีคำร้องอยู่แล้ว ระบบคืน `409 Conflict`
10. ถ้าไม่มี idempotency key ระบบตรวจ duplicate signature จาก incident, เบอร์, request type, geohash และ time bucket
11. ระบบสร้าง `requestId`, `trackingCode`, `eventId` และ timestamp
12. ระบบเขียนข้อมูลหลาย item ลง DynamoDB เช่น master, current, event, tracking lookup, phone unique และ projection
13. ระบบตอบ `201 Created` พร้อม `requestId`, `trackingCode`, `status=SUBMITTED`, `submittedAt`
14. ระบบ publish `rescue-request.created`
15. ถ้า publish สำเร็จ ระบบบันทึก source event metadata ลง current state เพื่อใช้ตรวจ correlation เมื่อผล priority กลับมา

### 9.2 Flow ประชาชนติดตามสถานะ

1. ประชาชนส่ง `requestId` มาที่ `GET /v1/citizen/rescue-requests/{requestId}/status`
2. ระบบอ่าน master, current state และ status events ล่าสุด
3. ระบบ mask เบอร์โทรก่อนส่งกลับ
4. ระบบคืนสถานะล่าสุด เช่น `SUBMITTED`, `ASSIGNED`, `IN_PROGRESS`
5. ถ้ามี assigned unit, priority, latest note หรือ recent events ระบบส่งรวมใน response

### 9.3 Flow ประชาชนส่งข้อมูลเพิ่มเติม

1. ประชาชนเรียก `POST /v1/citizen/rescue-requests/{requestId}/updates`
2. ระบบตรวจ `updateType`, `updatePayload` และ `trackingCode`
3. ระบบอ่าน master/current state
4. ระบบ hash tracking code ที่ส่งมาแล้วเทียบกับ tracking code hash ใน master
5. ถ้า code ไม่ตรง ระบบคืน `403 Forbidden`
6. ถ้าคำร้องปิดแล้ว ระบบคืน `409 Conflict`
7. ระบบสร้าง citizen update item และบันทึกลง DynamoDB
8. ระบบอัปเดต `lastCitizenUpdateAt`
9. ระบบตอบ `201 Created`
10. ระบบ publish `rescue-request.citizen-updated`
11. ถ้า publish สำเร็จ ระบบเก็บ latest priority source event metadata เพื่อรอผลประเมินใหม่

### 9.4 Flow เจ้าหน้าที่เปลี่ยนสถานะ

1. เจ้าหน้าที่เรียก command endpoint เช่น `/triage`, `/assign`, `/start`, `/resolve`, `/cancel`
2. ระบบอ่าน `X-Idempotency-Key` และ `If-Match` ถ้ามี
3. ระบบ reserve idempotency key ถ้ามีการส่งมา
4. ระบบอ่าน current state จาก DynamoDB
5. ระบบตรวจว่า `If-Match` ตรงกับ `stateVersion` หรือไม่
6. ระบบตรวจ transition ตามกฎ state machine
7. ระบบตรวจ requirement เพิ่มเติม เช่น assign ต้องมี `responderUnitId`, cancel ต้องมี `reason`
8. ระบบสร้าง status event ใหม่ version เพิ่มขึ้น 1
9. ระบบอัปเดต current state เช่น status, stateVersion, lastEventId, assignedUnitId, latestNote
10. ระบบตอบผล transition กลับเจ้าหน้าที่
11. ระบบ publish `rescue-request.status-changed`
12. ถ้าสถานะใหม่เป็น `RESOLVED` จะ publish `rescue-request.resolved`
13. ถ้าสถานะใหม่เป็น `CANCELLED` จะ publish `rescue-request.cancelled`

### 9.5 Flow รับผล Prioritization

1. Rescue Request Service publish `rescue-request.created` หรือ `rescue-request.citizen-updated`
2. Prioritization Service รับ event และประเมินความสำคัญ
3. Prioritization Service ส่งผลกลับผ่าน SQS queue `rescue-prioritization-evaluated-{stage}`
4. ingest Lambda normalize message และตรวจ header/body
5. ระบบตรวจ `messageType`, `correlationId`, `sentAt`, `version`, `requestId`, `incidentId`, `evaluateId`, `priorityScore`, `priorityLevel` และข้อมูลสำคัญอื่น
6. ระบบสร้าง idempotency key จาก `evaluateId` เพื่อกัน message ซ้ำ
7. ระบบอ่าน current state ของคำร้อง
8. ระบบตรวจว่า `correlationId` ตรงกับ `latestPrioritySourceEventId` ล่าสุดหรือไม่ เพื่อกันผลประเมินเก่ามาทับข้อมูลใหม่
9. ถ้าคำร้องปิดแล้ว ระบบ skip
10. ถ้าคำร้องยังเป็น `SUBMITTED` ระบบเปลี่ยนเป็น `TRIAGED`; ถ้าเป็นสถานะอื่นจะคงสถานะเดิมแต่ update priority
11. ระบบ append status event และ update current state ด้วย priority fields
12. ระบบ publish `rescue-request.status-changed`

### 9.6 Flow รับสถานะจาก Mission Progress Service

1. Mission Progress Service ส่ง `MissionStatusChanged` event เข้า SQS queue `rescue-mission-status-changed-{stage}`
2. ingest Lambda normalize payload รองรับทั้ง snake_case และ camelCase บางรูปแบบ
3. ระบบตรวจ schema version, requestId, incidentId, missionId, rescueTeamId, newStatus, changedAt, changedBy
4. ระบบสร้าง idempotency key จาก requestId, missionId, newStatus และ changedAt
5. ระบบอ่าน current state ของคำร้อง
6. ระบบตรวจว่า incidentId ใน event ตรงกับ incidentId ของคำร้อง
7. ถ้าคำร้องปิดแล้ว ระบบ skip
8. ถ้า `newStatus` เป็น `ON_SITE` หรือ `NEED_BACKUP` ระบบอัปเดต metadata ของ mission แต่ไม่เปลี่ยน rescue request status
9. ถ้า `newStatus` เป็น `EN_ROUTE` ระบบ map เป็น `IN_PROGRESS`
10. ถ้า `newStatus` เป็น `RESOLVED` ระบบ map เป็น `RESOLVED`
11. ถ้าสถานะเปลี่ยนจริง ระบบ append status event และ update current state
12. ระบบ publish `rescue-request.status-changed`
13. ถ้า mapped status เป็น `RESOLVED` ระบบ publish `rescue-request.resolved`

### 9.7 Flow sync incident catalog

1. EventBridge trigger sync Lambda ทุก 30 นาที
2. Lambda เรียก IncidentTracking Service ด้วย config จาก environment variables
3. ระบบอ่าน incident ทั้งหมดจาก upstream
4. ระบบอ่านรายการที่มีอยู่ใน `IncidentCatalogTable`
5. ถ้า incident ใหม่ ระบบสร้าง sequence ใหม่และตั้งชื่อเช่น `IncidentA`, `IncidentB`, `IncidentAA`
6. ถ้า incident เดิม ระบบคง sequence/name เดิมและ update fields ล่าสุด
7. ระบบ upsert ข้อมูลลง `IncidentCatalogTable`
8. `GET /v1/incidents` และ internal catalog endpoint จะอ่านข้อมูลจาก local table นี้

## 10. Idempotency และการป้องกันข้อมูลซ้ำ

### 10.1 Idempotency key

Mutating endpoints รองรับ `X-Idempotency-Key` เพื่อให้ client retry ได้ปลอดภัย ตัวอย่างเช่นถ้า network timeout หลัง server สร้างคำร้องสำเร็จแล้ว client retry ด้วย key เดิม ระบบจะคืน response เดิมโดยไม่สร้างคำร้องใหม่

พฤติกรรมหลักคือ

- key ใหม่: reserve แล้วประมวลผลจริง
- key เดิม + payload เดิม: replay response เดิม
- key เดิม + payload ต่างกัน: คืน `409 Conflict`
- key หมดอายุหลัง TTL: ถือเป็น key ใหม่

ค่า TTL ปัจจุบันคือ 24 ชั่วโมง และ lock timeout ระหว่างประมวลผลคือ 5 นาที

### 10.2 Phone uniqueness

ระบบบังคับว่าเบอร์โทรหนึ่งเบอร์มี active/request record ได้เพียงรายการเดียวผ่าน phone hash หากเบอร์เดิมสร้างคำร้องอีก ระบบจะคืน `409 Conflict` พร้อมข้อมูลว่าเบอร์นี้มีคำร้องอยู่แล้ว

### 10.3 Duplicate detection

ถ้าไม่มี idempotency key ระบบจะตรวจคำร้องซ้ำด้วย signature จาก

```text
incidentId | normalizedPhone | requestType | geohash(latitude, longitude, precision=7) | timeBucket(5 minutes)
```

ถ้าพบ signature เดิมในช่วงเวลาเดียวกัน ระบบจะคืน `409 Conflict` เพื่อป้องกันการกดส่งซ้ำหรือ network retry ที่ไม่ได้ใช้ idempotency key

## 11. Event ที่ระบบ Publish

| Event | เกิดเมื่อ | จุดประสงค์ |
| --- | --- | --- |
| `rescue-request.created` | สร้างคำร้องสำเร็จ | แจ้ง downstream และ trigger prioritization |
| `rescue-request.citizen-updated` | ประชาชนส่ง update หรือ staff patch บาง field | ให้ระบบอื่นประเมินข้อมูลล่าสุด |
| `rescue-request.status-changed` | สถานะคำร้องเปลี่ยน | แจ้ง dashboard, stream consumer หรือระบบอัตโนมัติ |
| `rescue-request.resolved` | คำร้องเปลี่ยนเป็น `RESOLVED` | แจ้งการปิดภารกิจสำเร็จ |
| `rescue-request.cancelled` | คำร้องเปลี่ยนเป็น `CANCELLED` | แจ้งการยกเลิกคำร้อง |
| `rescue-request.priority-score-updated` | priority score ถูกปรับผ่าน staff endpoint | แจ้งการปรับ priority เชิง operational |

event ทุกตัวถูก publish ผ่าน SNS โดยมี envelope/header เช่น messageId, eventType, schemaVersion, producer, occurredAt, traceId, correlationId, partitionKey และ contentType

## 12. API Endpoint สรุป

### 12.1 Public endpoints

| Method | Path | หน้าที่ |
| --- | --- | --- |
| `GET` | `/v1/health` | ตรวจสุขภาพรวมของ service |
| `GET` | `/v1/health/live` | ตรวจ liveness |
| `GET` | `/v1/health/ready` | ตรวจ readiness และ dependency |
| `POST` | `/v1/rescue-requests` | สร้างคำร้องใหม่ |
| `GET` | `/v1/incidents` | ดูรายการ incident จาก local catalog |
| `POST` | `/v1/citizen/tracking/lookup` | lookup คำร้องจากเบอร์และ tracking code |
| `GET` | `/v1/citizen/rescue-requests/{requestId}/status` | ดูสถานะคำร้องสำหรับประชาชน |
| `POST` | `/v1/citizen/rescue-requests/{requestId}/updates` | ส่งข้อมูลเพิ่มเติมจากประชาชน |
| `GET` | `/v1/citizen/rescue-requests/{requestId}/updates` | ดูรายการ update ของประชาชน |

### 12.2 Staff endpoints

| Method | Path | หน้าที่ |
| --- | --- | --- |
| `GET` | `/v1/rescue-requests/{requestId}` | ดูรายละเอียดคำร้อง |
| `PATCH` | `/v1/rescue-requests/{requestId}` | แก้ไขข้อมูลคำร้องบาง field |
| `PATCH` | `/v1/rescue-requests/{requestId}/priority` | ปรับ priority |
| `GET` | `/v1/rescue-requests/{requestId}/events` | ดู status events |
| `POST` | `/v1/rescue-requests/{requestId}/events` | append status event |
| `GET` | `/v1/rescue-requests/{requestId}/current` | ดู current state |
| `GET` | `/v1/incidents/{incidentId}/rescue-requests` | list คำร้องตาม incident |
| `GET` | `/v1/idempotency-keys/{idempotencyKeyHash}` | ตรวจ idempotency record |

### 12.3 Command endpoints

| Method | Path | สถานะเป้าหมาย |
| --- | --- | --- |
| `POST` | `/v1/rescue-requests/{requestId}/triage` | `TRIAGED` |
| `POST` | `/v1/rescue-requests/{requestId}/assign` | `ASSIGNED` |
| `POST` | `/v1/rescue-requests/{requestId}/start` | `IN_PROGRESS` |
| `POST` | `/v1/rescue-requests/{requestId}/resolve` | `RESOLVED` |
| `POST` | `/v1/rescue-requests/{requestId}/cancel` | `CANCELLED` |

### 12.4 Internal endpoints

| Method | Path | หน้าที่ |
| --- | --- | --- |
| `GET` | `/v1/internal/incidents/catalog` | ดู incident catalog ทั้งหมด |
| `DELETE` | `/v1/internal/incidents/catalog` | ล้าง catalog |
| `DELETE` | `/v1/internal/incidents/catalog/with-requests` | ล้าง catalog พร้อมข้อมูลที่เกี่ยวข้องกับคำร้อง |
| `DELETE` | `/v1/internal/rescue-requests/orphaned` | ลบ orphaned requests |
| `DELETE` | `/v1/internal/rescue-requests` | ล้าง rescue requests |
| `DELETE` | `/v1/internal/maintenance/all` | ล้างข้อมูลทั้งหมดสำหรับ maintenance/test |

## 13. Error handling และ response behavior

ระบบใช้ error response รูปแบบเดียวกัน โดยมี `message`, `errorCode`, `traceId`, `requestId`, `timestamp`, `path`, `method` และ `details`

สถานะ HTTP ที่พบบ่อยคือ

| HTTP | ความหมาย |
| --- | --- |
| `400` | request format ผิด เช่น JSON ไม่ถูกต้อง path/query/header coercion ไม่ผ่าน |
| `403` | tracking code หรือข้อมูลยืนยันตัวตนไม่ถูกต้อง |
| `404` | ไม่พบ resource |
| `409` | conflict เช่น duplicate, version mismatch, invalid transition, idempotency key reuse |
| `422` | validation error ของ field |
| `500` | internal error |

ทุก response จะมี `X-Trace-Id` เพื่อใช้ debug และเชื่อมโยง log

## 14. การตรวจสอบข้อมูลเข้าของระบบแบบละเอียด

การตรวจสอบข้อมูลเข้าเป็นชั้นป้องกันสำคัญของ Rescue Request Service เพราะ service นี้เป็นจุดรับข้อมูลจากหลายแหล่ง ได้แก่ ประชาชน เจ้าหน้าที่ ระบบภายใน และ event จาก service ภายนอก หากข้อมูลผิดรูปแบบ ซ้ำซ้อน หรือไม่สอดคล้องกับสถานะปัจจุบัน ระบบอาจสร้างคำร้องผิด เปลี่ยนสถานะผิด หรือทำให้ข้อมูล downstream ผิดตามไปด้วย ดังนั้นระบบจึงตรวจสอบข้อมูลหลายระดับ ตั้งแต่ HTTP request, path parameter, header, request body, business rules, state machine, idempotency และ async message contract

### 14.1 หลักการตรวจสอบข้อมูลโดยรวม

ระบบไม่ได้ตรวจสอบเฉพาะว่า field มีอยู่หรือไม่ แต่ตรวจหลายมิติพร้อมกัน ได้แก่

- ตรวจว่า request body เป็น JSON ที่อ่านได้
- ตรวจ path parameter เช่น `requestId` ต้องเป็น UUID เมื่อ endpoint ต้องการ UUID
- ตรวจ query parameter เช่น `limit`, `cursor`, `since`
- ตรวจ header สำคัญ เช่น `X-Idempotency-Key` และ `If-Match`
- ตรวจ required fields ว่ามีค่าและไม่เป็น string ว่าง
- ตรวจชนิดข้อมูล เช่น number, integer, object, string
- ตรวจช่วงค่าที่อนุญาต เช่น latitude, longitude, priorityScore
- ตรวจ enum เช่น requestType, sourceChannel, updateType, request status
- ตรวจความสัมพันธ์กับข้อมูลในฐานข้อมูล เช่น incident ต้องมีอยู่จริง
- ตรวจสิทธิ์เชิงข้อมูล เช่น tracking code ต้องตรงกับคำร้อง
- ตรวจสถานะปัจจุบัน เช่น ห้ามแก้ไขคำร้องที่ปิดแล้ว
- ตรวจ state transition ว่าเปลี่ยนสถานะได้ตาม workflow
- ตรวจ idempotency เพื่อกัน retry ซ้ำและกัน key เดิมถูกใช้กับ payload คนละชุด
- ตรวจ correlation ของ async event เพื่อกันผลประเมินเก่าหรือ message ผิดชุด

เมื่อข้อมูลไม่ผ่านการตรวจสอบ ระบบจะคืน error ที่เหมาะสม เช่น `400`, `403`, `409` หรือ `422` พร้อมรายละเอียดใน `details` เพื่อให้ client หรือผู้ดูแลระบบรู้ว่า field ใดผิดและผิดเพราะอะไร

### 14.2 การตรวจสอบระดับ HTTP request

ก่อนเข้าสู่ use case ระบบจะตรวจสอบรูปแบบ request เบื้องต้นผ่าน handler utilities

- ถ้า request body ไม่ใช่ JSON ที่ parse ได้ ระบบถือเป็น malformed request และคืน `400 BAD_REQUEST`
- ถ้า path parameter ที่ควรเป็น UUID เช่น `requestId` ไม่ใช่ UUID ระบบคืน `400 BAD_REQUEST`
- ถ้า header `If-Match` ถูกส่งมาแต่แปลงเป็น integer ไม่ได้ ระบบคืน `400 BAD_REQUEST`
- ถ้า `If-Match` มีค่าน้อยกว่า `1` ระบบคืน `400 BAD_REQUEST`
- ถ้า query parameter `limit` ไม่ใช่ integer หรืออยู่นอกช่วง `1-100` ระบบคืน `400 BAD_REQUEST`
- ถ้า query parameter `since` ต้องเป็น datetime แต่รูปแบบไม่ถูกต้อง ระบบคืน `400 BAD_REQUEST`

การตรวจสอบระดับนี้ช่วยคัด request ที่ผิดรูปแบบก่อนเข้าสู่ business logic ทำให้ use case ทำงานกับข้อมูลที่ถูก normalize แล้วมากขึ้น

### 14.3 การตรวจสอบ required fields

ระบบใช้หลักการเดียวกันกับหลาย endpoint คือ field ที่จำเป็นต้องมีต้องไม่หาย ไม่เป็น `null` และถ้าเป็น string ต้องไม่ใช่ string ว่างหรือมีแต่ช่องว่าง

ตัวอย่าง field จำเป็นของ `POST /v1/rescue-requests` ได้แก่

| Field | เหตุผลที่ต้องมี |
| --- | --- |
| `incidentId` | ใช้ผูกคำร้องกับเหตุการณ์ภัยพิบัติ |
| `requestType` | ใช้จำแนกประเภทความช่วยเหลือ |
| `description` | ใช้อธิบายสถานการณ์ |
| `peopleCount` | ใช้ประเมินขนาดและความเร่งด่วน |
| `latitude` | ใช้ระบุตำแหน่ง |
| `longitude` | ใช้ระบุตำแหน่ง |
| `contactName` | ใช้ติดต่อกลับ |
| `contactPhone` | ใช้ติดต่อและสร้าง tracking lookup |
| `sourceChannel` | ใช้ระบุช่องทางที่ส่งคำร้อง |

ถ้าข้อมูลเหล่านี้ขาด ระบบจะคืน `422 VALIDATION_ERROR` พร้อม `details` เช่น field `contactPhone` มี issue ว่า `is required`

### 14.4 การตรวจสอบการสร้างคำร้องใหม่

การสร้างคำร้องเป็น flow ที่ตรวจละเอียดที่สุด เพราะเป็นจุดที่ข้อมูลใหม่เข้าสู่ระบบครั้งแรก การตรวจประกอบด้วย

| กลุ่มข้อมูล | กฎตรวจสอบ |
| --- | --- |
| `incidentId` | ต้องอ้างอิง incident ที่มีอยู่ใน `IncidentCatalogTable` |
| `requestType` | ต้องเป็น `MEDICAL`, `EVACUATION` หรือ `SUPPLY` |
| `sourceChannel` | ต้องเป็น `WEB`, `MOBILE`, `LINE`, `PHONE`, `WALK_IN` หรือ `OTHER` |
| `contactPhone` | ต้องเป็น string ความยาว 7-20 ตัวอักษร และใช้ได้เฉพาะตัวเลข, `+`, `-`, space, `(`, `)` |
| `latitude` | ต้องแปลงเป็นตัวเลข finite ได้ และอยู่ระหว่าง `-90` ถึง `90` |
| `longitude` | ต้องแปลงเป็นตัวเลข finite ได้ และอยู่ระหว่าง `-180` ถึง `180` |
| `peopleCount` | ต้องเป็น integer มากกว่า `0` และไม่เกินข้อจำกัด precision ของ DynamoDB Number |
| phone uniqueness | เบอร์โทรที่ normalize แล้วต้องยังไม่เคยมีคำร้อง |
| duplicate signature | ถ้าไม่มี idempotency key ต้องไม่ซ้ำกับคำร้องใน incident/type/location/time bucket เดียวกัน |

ระบบจะแปลง `latitude` และ `longitude` เป็น `float` และแปลง `peopleCount` เป็น `int` ก่อนบันทึก เพื่อให้ข้อมูลใน DynamoDB มีรูปแบบที่คาดเดาได้ นอกจากนี้ยัง normalize เบอร์โทรและ hash เบอร์โทรก่อนใช้ตรวจ uniqueness หรือทำ tracking lookup

ตัวอย่างข้อมูลที่ไม่ผ่าน

- `peopleCount = 0` หรือ `peopleCount = -1` ไม่ผ่าน เพราะต้องมากกว่า 0
- `latitude = 120` ไม่ผ่าน เพราะอยู่นอกช่วงพิกัดโลก
- `contactPhone = "abc"` ไม่ผ่าน เพราะรูปแบบเบอร์ไม่ถูกต้อง
- `requestType = "FOOD"` ไม่ผ่าน เพราะไม่ใช่ enum ที่ระบบรองรับ
- `incidentId` ที่ไม่มีใน catalog ไม่ผ่าน แม้รูปแบบ string จะถูกต้อง

### 14.5 การตรวจสอบ tracking lookup และ citizen authorization

ใน flow ที่ประชาชนต้องอ้างสิทธิ์กับคำร้อง เช่น tracking lookup หรือส่ง citizen update ระบบใช้เบอร์โทรและ tracking code เป็นหลักฐาน

สำหรับ `POST /v1/citizen/tracking/lookup`

- ต้องมี `contactPhone`
- ต้องมี `trackingCode`
- ระบบ normalize/hash เบอร์โทร
- ระบบ hash tracking code
- ระบบค้นหา `TRACKING_LOOKUP` ด้วย phone hash และ tracking code hash
- ถ้าไม่พบคู่ที่ตรงกัน ระบบคืน `403 FORBIDDEN`

สำหรับ `POST /v1/citizen/rescue-requests/{requestId}/updates`

- ต้องมี `trackingCode`
- ระบบ hash tracking code ที่รับมา
- ระบบเทียบกับ `trackingCodeHash` ที่เก็บใน master record ของคำร้อง
- ถ้าไม่ตรง ระบบคืน `403 FORBIDDEN`

แนวทางนี้ทำให้ประชาชนไม่จำเป็นต้อง login ด้วยบัญชีเต็มรูปแบบ แต่ยังมีการยืนยันขั้นต่ำว่าผู้ส่ง update มี tracking code ของคำร้องจริง

### 14.6 การตรวจสอบ citizen update

การส่งข้อมูลเพิ่มเติมต้องมี field หลักคือ `updateType`, `updatePayload` และ `trackingCode` จากนั้นระบบตรวจ payload ตามชนิดของ update

| updateType | กฎของ updatePayload |
| --- | --- |
| `NOTE` | ต้องมี `note` เป็น string ที่ไม่ว่าง |
| `LOCATION_DETAILS` | ต้องมี `locationDetails` เป็น string ที่ไม่ว่าง |
| `PEOPLE_COUNT` | ต้องมี `peopleCount` เป็น integer มากกว่า `0` |
| `SPECIAL_NEEDS` | ต้องมี `specialNeeds` เป็น string ที่ไม่ว่าง |
| `CONTACT_INFO` | ต้องมีอย่างน้อยหนึ่ง field ระหว่าง `contactPhone` หรือ `contactName`; ถ้ามี `contactPhone` ต้องผ่านรูปแบบเบอร์โทร |

นอกจากตรวจ payload แล้ว ระบบยังตรวจสถานะปัจจุบันของคำร้องด้วย หากคำร้องเป็น `RESOLVED` หรือ `CANCELLED` จะคืน `409 CONFLICT` เพราะประชาชนไม่ควรอัปเดตคำร้องที่จบแล้ว

### 14.7 การตรวจสอบการแก้ไขคำร้องโดยเจ้าหน้าที่

สำหรับ `PATCH /v1/rescue-requests/{requestId}` ระบบจำกัด field ที่แก้ไขได้เพื่อป้องกันการเปลี่ยนข้อมูลสำคัญโดยไม่ผ่าน workflow

Field ที่อนุญาตให้แก้ไข ได้แก่

- `description`
- `peopleCount`
- `specialNeeds`
- `locationDetails`
- `addressLine`

Field ที่ห้ามแก้ไข ได้แก่

- `incidentId`
- `status`
- `requestId`

ถ้า request body มี field ต้องห้าม ระบบคืน `422 VALIDATION_ERROR` ถ้าไม่มี field ที่แก้ไขได้เลย ระบบคืน validation error เช่นกัน และถ้าคำร้องอยู่ใน terminal state ระบบคืน `409 CONFLICT`

การแก้ไขบาง field ผ่าน staff patch จะ publish `rescue-request.citizen-updated` ในรูปแบบ update type `PATCH` เพื่อให้ downstream เห็นว่าข้อมูลที่อาจมีผลต่อการประเมินถูกเปลี่ยน

### 14.8 การตรวจสอบ priority update

สำหรับ `PATCH /v1/rescue-requests/{requestId}/priority` ระบบอนุญาตเฉพาะ field ต่อไปนี้

- `priorityScore`
- `priorityLevel`
- `note`

กฎตรวจสอบคือ

- ถ้ามี field อื่นนอกเหนือจากนี้ ระบบคืน `422 VALIDATION_ERROR`
- body ต้องมีอย่างน้อยหนึ่ง field ที่อนุญาต
- `priorityScore` ต้องเป็นตัวเลข finite ระหว่าง `0` ถึง `1` หรือเป็น `null`
- `priorityLevel` ต้องเป็น string ที่ไม่ว่าง หรือเป็น `null`
- `note` ต้องเป็น string ที่ไม่ว่าง หรือเป็น `null`
- ถ้าคำร้องเป็น `RESOLVED` หรือ `CANCELLED` แล้ว ห้ามแก้ priority และคืน `409 CONFLICT`
- ถ้าส่ง `If-Match` ระบบต้องตรวจว่า version ตรงกับ `stateVersion` ปัจจุบัน

เมื่อ priority score เปลี่ยนจริง ระบบจึง publish `rescue-request.priority-score-updated`

### 14.9 การตรวจสอบ state transition และ command endpoints

การเปลี่ยนสถานะผ่าน command endpoints หรือ append status event ต้องตรวจทั้งรูปแบบข้อมูลและกฎ state machine

สำหรับ `POST /v1/rescue-requests/{requestId}/events` ต้องมี

- `newStatus`
- `changedBy`
- `changedByRole`

`newStatus` ต้องเป็นหนึ่งใน `SUBMITTED`, `TRIAGED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CANCELLED`

หลังจากนั้นระบบตรวจสถานะปัจจุบันกับสถานะเป้าหมายตามกฎ transition

| From | To ที่อนุญาต |
| --- | --- |
| `SUBMITTED` | `TRIAGED`, `ASSIGNED`, `CANCELLED` |
| `TRIAGED` | `ASSIGNED`, `CANCELLED` |
| `ASSIGNED` | `IN_PROGRESS`, `CANCELLED` |
| `IN_PROGRESS` | `RESOLVED`, `CANCELLED` |
| `RESOLVED` | ไม่มี |
| `CANCELLED` | ไม่มี |

เงื่อนไขพิเศษคือ

- เปลี่ยนเป็น `ASSIGNED` ต้องมี `responderUnitId`
- เปลี่ยนเป็น `CANCELLED` ต้องมี `reason`
- ถ้ามี `priorityScore` ใน payload ต้องเป็นตัวเลขระหว่าง `0` ถึง `1`
- ถ้าสถานะปัจจุบันเป็น terminal state จะเปลี่ยนต่อไม่ได้
- ถ้ามี `If-Match` ต้องตรงกับ `stateVersion` ปัจจุบัน

หาก transition ไม่ถูกต้อง ระบบคืน `409 CONFLICT` แต่ถ้า field จำเป็นขาดหรือค่าผิดรูปแบบ ระบบคืน `422 VALIDATION_ERROR`

### 14.10 การตรวจสอบ idempotency

Mutating endpoint รองรับ `X-Idempotency-Key` เพื่อป้องกันการประมวลผลซ้ำจาก retry ระบบตรวจ idempotency ในหลายขั้นตอน

1. รับ key จาก header
2. hash key ก่อนเก็บหรือค้นหา
3. สร้าง request fingerprint จาก operation, resource scope และ request body
4. ถ้า key ยังไม่เคยใช้ ระบบ reserve เป็น `IN_PROGRESS`
5. ถ้า key เดิมอยู่ในสถานะ `COMPLETED` และ fingerprint ตรงกัน ระบบ replay response เดิม
6. ถ้า key เดิมแต่ fingerprint ไม่ตรงกัน ระบบคืน `409 CONFLICT`
7. ถ้า key เดิมยัง `IN_PROGRESS` และ lock ยังไม่หมดอายุ ระบบคืน conflict ว่า request กำลังประมวลผล
8. เมื่อ operation สำเร็จ ระบบ finalize เป็น `COMPLETED` พร้อม response
9. ถ้า operation ล้มเหลว ระบบ finalize เป็น `FAILED` พร้อม error code/message

การตรวจนี้ทำให้ frontend สามารถ retry request ได้อย่างมั่นใจ โดยเฉพาะการสร้างคำร้องหรือส่ง update ในสถานการณ์เครือข่ายไม่เสถียร

### 14.11 การตรวจสอบ duplicate และ phone uniqueness

ระบบมีทั้งการกันซ้ำแบบเข้มและแบบ heuristic

แบบเข้มคือ phone uniqueness ระบบ normalize เบอร์โทรแล้ว hash จากนั้นตรวจว่าเบอร์นี้มีคำร้องอยู่แล้วหรือไม่ ถ้ามีจะคืน `409 CONFLICT`

แบบ heuristic คือ duplicate signature ใช้เมื่อไม่มี idempotency key โดยรวมข้อมูลต่อไปนี้

```text
incidentId | normalizedPhone | requestType | geohash(latitude, longitude, precision=7) | timeBucket(5 minutes)
```

ถ้ามีคำร้องที่ signature ตรงกัน ระบบถือว่าเป็นคำร้องซ้ำในช่วงเวลาใกล้กันและคืน `409 CONFLICT`

### 14.12 การตรวจสอบ async event จาก Prioritization Service

เมื่อ ingest ผลประเมิน priority ระบบไม่ได้เชื่อ message ทันที แต่ตรวจ schema และ business constraints ก่อน

Header ต้องมีหรือถูก normalize ให้มีข้อมูลสำคัญ เช่น

- `messageType` ต้องเป็น `RescueRequestEvaluatedEvent` หรือชนิด compatibility ที่ระบบรองรับ
- `correlationId` ต้องมีค่า
- `sentAt` ต้องเป็น ISO-8601 datetime
- `version` ต้องเท่ากับ `1` หรือ `1.0`

Body ต้องผ่านกฎ เช่น

- `requestId` ต้องมีค่า
- `incidentId` ต้องเป็น UUID
- `evaluateId` ต้องเป็น UUID
- `requestType` ต้องเป็น `MEDICAL`, `EVACUATION` หรือ `SUPPLY`
- `priorityScore` ต้องเป็นตัวเลข finite ระหว่าง `0` ถึง `1`
- `priorityLevel` ต้องเป็น `LOW`, `NORMAL`, `HIGH` หรือ `CRITICAL`
- `evaluateReason` ต้องเป็น string ที่ไม่ว่าง
- `description` ต้องเป็น string ที่ไม่ว่าง
- `peopleCount` ต้องเป็น integer มากกว่า `0`
- `lastEvaluatedAt` ต้องเป็น ISO-8601 datetime
- `location` ต้องเป็น object และมี `latitude`, `longitude` เป็นตัวเลข

หลังจาก schema ผ่าน ระบบยังตรวจ current state เพิ่มเติม

- `requestId` ต้องมีอยู่จริง
- `correlationId` ต้องตรงกับ `CURRENT_STATE.latestPrioritySourceEventId`
- ถ้าคำร้องเป็น terminal state จะ skip
- ใช้ idempotency key จาก `evaluateId` เพื่อกัน message ซ้ำ

การตรวจ `correlationId` สำคัญมาก เพราะช่วยป้องกันผลประเมินเก่าจาก event ก่อนหน้ามา overwrite priority ล่าสุดของคำร้อง

### 14.13 การตรวจสอบ async event จาก Mission Progress Service

สำหรับ `MissionStatusChanged` event ระบบ normalize payload เพื่อรองรับชื่อ field หลายแบบ เช่น `mission_id`, `missionId`, `MissionID` แล้วตรวจข้อมูลดังนี้

- `messageType` ถ้ามี ต้องเป็นชนิดที่ระบบรองรับ เช่น `MissionStatusChanged`, `MissionStatusChangedEvent`, `mission.status.changed`, `mission.status.changed.v1`
- `schema_version` หรือ `schemaVersion` ต้องเท่ากับ `1.0`
- ต้องมี `requestId`
- ต้องมี `incidentId`
- ต้องมี `missionId`
- ต้องมี `rescueTeamId`
- ต้องมี `newStatus`
- ต้องมี `changedAt`
- ต้องมี `changedBy`
- `newStatus` ต้องเป็น `EN_ROUTE`, `ON_SITE`, `RESOLVED` หรือ `NEED_BACKUP`
- `changedAt` ต้องเป็น ISO-8601 datetime

หลังจาก schema ผ่าน ระบบตรวจ business rule เพิ่มเติม

- `requestId` ต้องมี current state อยู่จริง
- `incidentId` ใน event ต้องตรงกับ incidentId ของคำร้อง
- ถ้าคำร้องเป็น terminal state จะ skip
- ใช้ idempotency key จาก `requestId`, `missionId`, `newStatus`, `changedAt` เพื่อกัน event ซ้ำ

การ map status ทำเฉพาะบางค่าเท่านั้น

| Mission status | ผลต่อ Rescue Request |
| --- | --- |
| `EN_ROUTE` | เปลี่ยนเป็น `IN_PROGRESS` |
| `RESOLVED` | เปลี่ยนเป็น `RESOLVED` |
| `ON_SITE` | อัปเดต mission metadata แต่ไม่เปลี่ยน lifecycle |
| `NEED_BACKUP` | อัปเดต mission metadata แต่ไม่เปลี่ยน lifecycle |

### 14.14 การตรวจสอบ incident catalog sync

ระหว่าง sync incident จาก IncidentTracking Service ระบบตรวจ payload แต่ละรายการก่อน upsert

- ต้องมี `incident_id` เป็น string ที่ไม่ว่าง
- incident ที่ไม่มี `incident_id` จะถูก skip และนับในผลลัพธ์ `skipped`
- incident ใหม่จะได้รับ sequence และชื่อ local เช่น `IncidentA`
- incident เดิมจะคง sequence/name เดิมเพื่อให้การแสดงผล stable
- field อื่น เช่น `incident_type`, `status`, `incident_description`, `created_at`, `updated_at` ถูกเก็บเป็น snapshot จาก upstream

การตรวจนี้ทำให้ catalog ไม่เสียรูปเพราะข้อมูล upstream บางรายการไม่สมบูรณ์

### 14.15 สรุปผลลัพธ์เมื่อข้อมูลไม่ผ่าน

| กรณี | HTTP / ผลลัพธ์ |
| --- | --- |
| JSON ผิดรูปแบบ | `400 BAD_REQUEST` |
| path UUID ผิดรูปแบบ | `400 BAD_REQUEST` |
| query/header แปลงชนิดข้อมูลไม่ได้ | `400 BAD_REQUEST` |
| required field ขาด | `422 VALIDATION_ERROR` |
| enum ไม่อยู่ในค่าที่รองรับ | `422 VALIDATION_ERROR` |
| field รูปแบบผิด เช่น phone/lat/lng/priorityScore | `422 VALIDATION_ERROR` |
| tracking code ไม่ตรง | `403 FORBIDDEN` |
| resource ไม่มีอยู่ | `404 NOT_FOUND` |
| duplicate request หรือ phone ซ้ำ | `409 CONFLICT` |
| idempotency key เดิมแต่ payload ต่างกัน | `409 CONFLICT` |
| stateVersion ไม่ตรงกับ `If-Match` | `409 CONFLICT` |
| transition ผิด state machine | `409 CONFLICT` |
| แก้ไขคำร้องที่ terminal state | `409 CONFLICT` |
| async message schema ผิด | batch item นั้น fail และเข้า retry/DLQ ตาม SQS behavior |

โดยรวมแล้ว การตรวจสอบข้อมูลเข้าของระบบถูกออกแบบให้ป้องกันความผิดพลาดทั้งจากผู้ใช้ ระบบเครือข่าย การ retry ซ้ำ การทำงานพร้อมกันของเจ้าหน้าที่ และ event จากระบบภายนอก ทำให้ข้อมูลคำร้องยังคงถูกต้อง สอดคล้องกับ workflow และตรวจสอบย้อนหลังได้

## 15. Scenario สมมติ

### Scenario 1: ประชาชนสร้างคำร้องขออพยพ

นายสมชายติดอยู่ในบ้านสองชั้นจากเหตุน้ำท่วม มีผู้ติดค้าง 5 คนและมีผู้สูงอายุหนึ่งคน เขาเปิดเว็บหรือ mobile app แล้วเลือก incident น้ำท่วม จากนั้นกรอกประเภทคำร้องเป็น `EVACUATION`, ใส่คำอธิบาย พิกัด เบอร์โทร และรายละเอียดว่าอยู่บ้านสีเหลืองใกล้ต้นไม้ใหญ่

เมื่อกดส่ง ระบบตรวจข้อมูลทั้งหมด พบว่า incident มีอยู่จริง เบอร์โทรยังไม่เคยมีคำร้อง และไม่มี duplicate signature ในช่วง 5 นาที ระบบจึงสร้างคำร้องใหม่เป็นสถานะ `SUBMITTED` แล้วคืน `requestId` และ `trackingCode` ให้สมชายเก็บไว้

เบื้องหลังระบบ publish `rescue-request.created` ไปยัง SNS เพื่อให้ Prioritization Service นำข้อมูลไปประเมิน priority เช่น จำนวนคน ความเร่งด่วน พิกัด และ special needs

### Scenario 2: ประชาชนกดส่งซ้ำเพราะเน็ตไม่ดี

หลังจากกดส่งครั้งแรก เครือข่ายของสมชายหลุดก่อนที่ frontend จะแสดงผล เขากดส่งอีกครั้งด้วยข้อมูลเดิม ถ้า frontend ส่ง `X-Idempotency-Key` เดิม ระบบจะ replay response เดิมและไม่สร้างคำร้องใหม่

ถ้า frontend ไม่ได้ส่ง idempotency key ระบบจะตรวจ duplicate signature และ phone uniqueness หากพบว่าเป็นคำร้องเดิมหรือเบอร์เดิม ระบบจะคืน `409 Conflict` พร้อมข้อมูลให้ frontend นำผู้ใช้ไปติดตามคำร้องเดิมแทน

### Scenario 3: ประชาชนแจ้งว่าจำนวนคนเพิ่ม

ผ่านไป 10 นาที มีเพื่อนบ้านเข้ามาหลบภัยเพิ่ม ทำให้จำนวนคนที่ต้องช่วยเหลือเพิ่มจาก 5 เป็น 7 สมชายใช้ `trackingCode` ส่ง update type `PEOPLE_COUNT` พร้อม payload `{ "peopleCount": 7 }`

ระบบตรวจว่า tracking code ถูกต้อง คำร้องยังไม่ปิด และ payload ถูกต้อง จากนั้นบันทึก citizen update และ publish `rescue-request.citizen-updated` เพื่อให้ Prioritization Service ประเมินใหม่ เพราะจำนวนคนเพิ่มอาจทำให้ priority สูงขึ้น

### Scenario 4: ระบบ Prioritization ประเมินคำร้อง

Prioritization Service รับ event แล้วคำนวณว่า request นี้ควรเป็น `HIGH` ด้วย score `0.82` เนื่องจากมีผู้สูงอายุและระดับน้ำเพิ่มขึ้น จากนั้นส่งผลกลับผ่าน SQS

Rescue Request Service ingest message ตรวจว่า `correlationId` ตรงกับ source event ล่าสุดของคำร้อง จึงยอมรับผลประเมิน ถ้าคำร้องยังเป็น `SUBMITTED` ระบบจะเปลี่ยนเป็น `TRIAGED`, update priority fields, เพิ่ม status event version ใหม่ และ publish `rescue-request.status-changed`

### Scenario 5: เจ้าหน้าที่มอบหมายทีมกู้ภัย

Dispatcher เห็นคำร้อง priority สูง จึงเรียก `POST /v1/rescue-requests/{requestId}/assign` พร้อม `responderUnitId=TEAM-ALPHA` และ `If-Match` เท่ากับ stateVersion ล่าสุด

ระบบตรวจว่า transition จาก `TRIAGED` ไป `ASSIGNED` ถูกต้อง และมี `responderUnitId` ครบ จากนั้นสร้าง status event ใหม่ อัปเดต `assignedUnitId`, `assignedAt`, `stateVersion` และ publish `rescue-request.status-changed`

### Scenario 6: Mission Progress Service ส่งสถานะทีมกำลังเดินทาง

เมื่อทีม `TEAM-ALPHA` เริ่มเดินทาง Mission Progress Service ส่ง event `MissionStatusChanged` โดย `new_status=EN_ROUTE`

Rescue Request Service map `EN_ROUTE` เป็น `IN_PROGRESS` ตรวจว่า incidentId ตรงกับคำร้อง และคำร้องยังไม่ปิด จากนั้น append status event เปลี่ยนจาก `ASSIGNED` เป็น `IN_PROGRESS`, เก็บ mission metadata และ publish `rescue-request.status-changed`

### Scenario 7: ภารกิจเสร็จสิ้น

หลังช่วยเหลือสำเร็จ Mission Progress Service ส่ง `new_status=RESOLVED` ระบบ map เป็น `RESOLVED`, append status event, อัปเดต current state เป็น terminal state และ publish ทั้ง `rescue-request.status-changed` และ `rescue-request.resolved`

หลังจากนั้น ถ้าประชาชนพยายามส่ง update เพิ่ม หรือเจ้าหน้าที่พยายามเปลี่ยนสถานะต่อ ระบบจะปฏิเสธเพราะ `RESOLVED` เป็น terminal state

### Scenario 8: ยกเลิกคำร้องเพราะเป็นข้อมูลผิด

ถ้าเจ้าหน้าที่ตรวจพบว่าคำร้องถูกส่งผิด incident หรือเป็นคำร้องที่ไม่ต้องดำเนินการแล้ว สามารถเรียก `POST /v1/rescue-requests/{requestId}/cancel` พร้อม `reason`

ระบบตรวจว่า transition ไป `CANCELLED` ทำได้จากสถานะปัจจุบัน และต้องมีเหตุผล จากนั้นสร้าง status event, เปลี่ยน current state เป็น `CANCELLED`, publish `rescue-request.status-changed` และ `rescue-request.cancelled`

## 16. คุณสมบัติด้านความน่าเชื่อถือ

ระบบมีแนวทางรองรับความน่าเชื่อถือดังนี้

- ใช้ idempotency key ป้องกัน retry ซ้ำใน mutating endpoints
- ใช้ stateVersion และ `If-Match` ป้องกัน concurrent update ใน flow ที่สำคัญ
- ใช้ append-only status events เพื่อ audit trail
- ใช้ current state snapshot เพื่ออ่านสถานะล่าสุดได้เร็ว
- ใช้ local incident catalog เพื่อลด dependency กับ upstream ตอน client อ่านข้อมูล
- ใช้ SNS/SQS เพื่อลด coupling ระหว่าง service และรองรับ event-driven architecture
- ใช้ DLQ สำหรับ queue ingest สำคัญ เช่น prioritization result และ mission status changed
- ใช้ correlationId/source event tracking เพื่อกันผล priority เก่าทับข้อมูลใหม่
- ใช้ terminal state rule เพื่อป้องกันการแก้ไขคำร้องที่ปิดแล้ว

## 17. สรุป

Rescue Request Service เป็น transactional core ของระบบจัดการคำร้องกู้ภัย ทำหน้าที่รับคำร้อง เก็บข้อมูลสำคัญ ควบคุม lifecycle และเชื่อมต่อกับ service อื่นผ่าน event-driven architecture จุดเด่นคือรองรับทั้ง flow ของประชาชน เจ้าหน้าที่ และระบบภายนอก โดยยังรักษาความถูกต้องของข้อมูลผ่าน validation, idempotency, duplicate detection, state machine และ audit trail

เมื่อมองทั้งระบบ end-to-end service นี้ทำหน้าที่เป็นแหล่งข้อมูลจริงของคำร้องและสถานะล่าสุด ขณะที่งานวิเคราะห์หรือปฏิบัติการเฉพาะทาง เช่น priority evaluation และ mission progress ถูกแยกออกไปเป็นระบบภายนอกที่สื่อสารกลับมาด้วย event ทำให้ระบบหลักดูแลได้ง่าย ขยายต่อได้ และเหมาะกับสถานการณ์ภัยพิบัติที่ต้องรับ load สูงและต้องทำงานต่อเนื่อง
