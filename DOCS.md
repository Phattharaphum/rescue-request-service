# ภาพรวมของบริการ (Service Overview)

## RescueRequest Service

### 0. Repository
- GitHub: https://github.com/Phattharaphum/rescue-request-service

### 1. Service Owner
- นายภัทรภูมิ กิ่งชัย
- รหัสนักศึกษา 6609612160
- ภาคปกติ

### 2. Service Purpose
RescueRequest Service เป็นบริการที่รับผิดชอบการจัดการคำร้อง สถานะของคำร้องขอความช่วยเหลือจากประชาชน (Citizens) ตั้งแต่การรับเรื่อง การจัดเก็บรายละเอียดที่สำคัญ เช่น พิกัด, จำนวนคน, ความต้องการพิเศษ รวมถึงการแจ้งข้อมูลรายละเอียดเพิ่มเติม ไปจนถึงการติดตามสถานะการช่วยเหลือ โดยทำหน้าที่เป็นจุดรับข้อมูล (Intake) กลาง เพื่อให้มั่นใจว่าคำร้องทุกรายการถูกบันทึกและสามารถตรวจสอบสถานะได้ตลอดเวลา

### 3. Pain Point ที่แก้ไข
ในสถานการณ์ภัยพิบัติ ผู้ประสบภัยมักประสบปัญหาในการแจ้งขอความช่วยเหลือเนื่องจากขาดช่องทางที่ระบุรายละเอียดสำคัญ เช่น พิกัดที่แม่นยำ หรือผู้ป่วยติดเตียง ได้อย่างครบถ้วนในครั้งเดียว และมักเกิดความกังวลเมื่อไม่ทราบสถานะว่ามีใครรับเรื่องแล้วหรือไม่ นอกจากนี้ ปัญหาเครือข่ายที่ไม่เสถียรทำให้เกิดการส่งข้อมูลซ้ำซ้อน (Duplicate requests) จนเจ้าหน้าที่สับสน บริการนี้จึงถูกออกแบบมาเพื่อรวบรวมข้อมูลให้เป็นระบบ ลดความซ้ำซ้อน และให้ผู้ประสบภัยติดตามความคืบหน้าได้ (Trackable status)

### 4. Target Users
- **Citizens (ผู้ประสบภัย):** ส่งคำร้อง + แจ้งรายละเอียดเพิ่มเติม + ตรวจสอบสถานะ
- **Dispatchers / Triage Staff:** คัดกรอง / จัดลำดับความสำคัญ / ปรับสถานะ
- **Rescue Teams:** ใช้ข้อมูลหน้างานผ่านระบบที่เชื่อมต่อ เช่น Dispatch/Operations

### 5. Service Boundary

#### In-scope Responsibilities (สิ่งที่บริการนี้รับผิดชอบ)

**Request Ingestion & Validation**  
รับคำร้อง ตรวจสอบรูปแบบและความครบถ้วนของข้อมูลสำคัญ เช่น Location, Contact, Needs

**State Machine Management**  
จัดการสถานะของคำร้องตาม flow:

`SUBMITTED → TRIAGED → ASSIGNED → IN_PROGRESS → RESOLVED หรือ CANCELLED`

**Duplicate Handling (Idempotency)**  
ตรวจสอบและจัดการคำร้องที่ซ้ำกันจากผู้ใช้คนเดิมในเวลาใกล้เคียงกัน

**Status Tracking**  
ให้บริการข้อมูลสถานะปัจจุบันแก่ผู้ร้องขอ

**Audit Trail / Logs**  
เก็บประวัติการเปลี่ยนแปลงสถานะทั้งหมด เพื่อใช้ตรวจสอบย้อนหลัง

#### Out-of-scope / Not Responsible For (ไม่รับผิดชอบ)
- **Resource Dispatching:** การสั่งการหรือจัดสรรยานพาหนะ / ทีมกู้ภัย (เป็นหน้าที่ของ Dispatch Service)
- **Incident Management:** การจัดการข้อมูลภาพรวมของภัยพิบัติ (เป็นหน้าที่ของ Incident Service)
- **Medical Diagnosis:** การประเมินอาการทางการแพทย์เชิงลึก
- **Social Media Scraping/Crawling:** ดึงข้อมูลขอความช่วยเหลือจากโพสต์ในโซเชียลมีเดีย เช่น Facebook, X โดยตรง

### 6. Autonomy / Decision Logic
บริการมีความเป็นอิสระในการตัดสินใจเกี่ยวกับ:
- การยอมรับ (Accept) หรือปฏิเสธ (Drop) คำร้องที่ซ้ำซ้อน (De-duplication logic)
- การตรวจสอบความถูกต้องของรูปแบบข้อมูล (Data Validation) ก่อนบันทึก
- การอนุญาตให้เปลี่ยนสถานะ (State Transition) ว่าเป็นไปตาม flow ที่กำหนดหรือไม่

#### หลักการตัดสินใจ (Decision inputs)

##### 6.1 Idempotency (Strong)
- ใช้ `X-Idempotency-Key` (UUID) จาก client
- ถ้า key เดิมถูกใช้แล้ว → ต้องคืนผลลัพธ์เดิมเสมอ (TTL 24 ชม.)
- คืนผลเดิม (รวม status code) พร้อม `Idempotency-Replayed: true`

##### 6.2 Duplicate Heuristic (Weak, เมื่อไม่มี key)
ตรวจจับคำร้องซ้ำโดยใช้ uniqueness key:
- `incidentId(UUID) + normalizedPhonePrimary + requestType + geoHash(7) + timeBucket(5 minutes)`

ถ้าซ้ำ:
- ตอบ `409 Conflict`
- พร้อม `existingRequestId` เพื่อให้ user track รายการเดิม

##### 6.3 Current Status & Completeness
- ถ้า `RESOLVED` หรือ `CANCELLED` แล้ว: เป็น terminal state อาจไม่อนุญาตแก้ไข
- ต้องมีข้อมูลจำเป็นครบ: Location, Phone number, `peopleCount ≥ 1`

บริการสามารถตัดสินใจจัดการข้อมูลซ้ำได้เอง (System decision) โดยไม่ต้องรออนุมัติจากมนุษย์

### 7. Owned Data
- **Rescue Request Records (Core Domain):** ข้อมูลหลักของคำร้อง ได้แก่ `requestId`, `description`, `peopleCount`, `specialNeeds`, `location`, `contact` ซึ่งเป็นข้อมูล Core Domain ที่บริการนี้สร้างและดูแลความถูกต้อง
- **Request Lifecycle State:** ข้อมูลสถานะปัจจุบัน (`status`) และเวลาที่รับเรื่อง (`submittedAt`) ซึ่งสะท้อนความเป็นไปของคำร้องนั้น ๆ
- **Audit Trail:** ประวัติการเปลี่ยนสถานะครบทุกครั้ง

### 8. Linked Data (Reference Only)
- **incidentId:** อ้างอิงจาก Incident Service เพื่อระบุว่าคำร้องนี้อยู่ภายใต้เหตุการณ์ภัยพิบัติใด ใช้เพื่อจัดกลุ่มคำร้อง แต่ไม่ได้เก็บรายละเอียดเหตุการณ์ไว้ที่นี่

### 9. Non-Functional Requirements
- **Idempotency:** ระบบต้องรองรับการส่งคำร้องซ้ำ (Retry) จากฝั่ง Client กรณีเครือข่ายไม่ดี โดยต้องไม่สร้าง Record ใหม่ แต่ให้คืนค่า `requestId` เดิมและสถานะล่าสุดกลับไป
- **High Availability:** API สำหรับรับคำร้อง (Create Request) ต้องมีความพร้อมใช้งานสูง รองรับ Load ได้มากในช่วงวิกฤต
- **Data Consistency:** สถานะ (`status`) ต้องมีความถูกต้อง เพื่อให้ผู้ประสบภัยและเจ้าหน้าที่เห็นข้อมูลตรงกัน
- **Response Time:** การตรวจสอบสถานะ (Get Details) ต้องรวดเร็วเพื่อลดความกังวลของผู้ใช้งาน

### 10. State Machine Specification

#### Status Enum (Global)
- `SUBMITTED`
- `TRIAGED`
- `ASSIGNED`
- `IN_PROGRESS`
- `RESOLVED`
- `CANCELLED`

#### Terminal States
- `RESOLVED`
- `CANCELLED`

#### Allowed Transitions

| From | To | Allowed Roles | Notes |
|------|----|---------------|-------|
| SUBMITTED | TRIAGED | TRIAGE, DISPATCHER | คัดกรอง + กำหนด priority |
| TRIAGED | ASSIGNED | DISPATCHER | ต้องมี `responderUnitId` |
| ASSIGNED | IN_PROGRESS | RESCUE_TEAM, DISPATCHER | เริ่มปฏิบัติ |
| IN_PROGRESS | RESOLVED | RESCUE_TEAM, DISPATCHER | จบภารกิจ |
| SUBMITTED | CANCELLED | DISPATCHER, ADMIN | ต้องมี reason |
| TRIAGED | CANCELLED | DISPATCHER, ADMIN | ต้องมี reason |
| ASSIGNED | CANCELLED | DISPATCHER, ADMIN | ต้องมี reason |
| IN_PROGRESS | CANCELLED | DISPATCHER, ADMIN | ต้องมี reason |
| RESOLVED / CANCELLED | any | ✗ | ห้ามเปลี่ยน |

---

# Service Architecture

![Service Architecture](/docs/Service_Architecture_V02.jpeg)

## Components

### Citizen Client (Mobile/Web)
ช่องทางที่ประชาชนใช้ติดต่อระบบเพื่อแจ้งเหตุ ขอความช่วยเหลือ ติดตามความคืบหน้า และส่งข้อมูลเพิ่มเติมระหว่างที่คำร้องยังดำเนินอยู่

**หน้าที่หลัก:**
- สร้างคำร้องขอความช่วยเหลือ
- ติดตามสถานะคำร้อง
- ส่งข้อมูลอัปเดตเพิ่มเติมจากหน้างานหรือผู้แจ้งเหตุ

### Staff Client (Triage / Dispatcher / Admin Console)
ช่องทางสำหรับเจ้าหน้าที่ใช้บริหารจัดการคำร้องและควบคุมการทำงานภายใน

**หน้าที่หลัก:**
- ดูรายละเอียดคำร้อง
- ตรวจสอบสถานะปัจจุบันและประวัติการเปลี่ยนแปลง
- บันทึกข้อมูลเพิ่มเติมจากฝั่งเจ้าหน้าที่
- สนับสนุนการคัดกรอง การประสานงาน และการติดตามการช่วยเหลือ

### Command / Workflow Layer
กลไกสำหรับควบคุมการเปลี่ยนสถานะของคำร้องตาม business workflow หรือ state machine ของระบบ

**หน้าที่หลัก:**
- บังคับให้การเปลี่ยนสถานะเป็นไปตามลำดับที่กำหนด
- แยกคำสั่งเชิง workflow ออกจากการแก้ไขข้อมูลทั่วไป
- ทำให้ lifecycle ของ rescue request มีความชัดเจนและตรวจสอบได้

### Amazon API Gateway
จุดรับคำขอแบบ synchronous ของระบบจาก client ทุกประเภท

**หน้าที่หลัก:**
- เป็น entry point กลางของบริการ
- ทำ routing ไปยัง service logic ภายใน
- รองรับ security control, throttling และการป้องกันทราฟฟิกผิดปกติ

### Lambda: RescueRequest Service Handler
แกนกลางของ RescueRequest Service ทำหน้าที่ประมวลผล business logic ทั้งหมดของระบบ

**หน้าที่หลัก:**
- รับและประมวลผลคำขอจาก client
- ตรวจสอบความถูกต้องของข้อมูลและกฎทางธุรกิจ
- จัดการ lifecycle ของ rescue request
- ควบคุม state transition
- บันทึกข้อมูลหลักและประวัติการเปลี่ยนแปลง
- publish domain events ไปยังระบบ downstream

### Amazon DynamoDB
ฐานข้อมูลหลักที่ RescueRequest Service เป็นเจ้าของและดูแลเอง

**องค์ประกอบหลัก:**
1. **RescueRequestTable**  
   เก็บข้อมูลหลักของคำร้อง รวมถึง current state หรือข้อมูลล่าสุดที่ระบบใช้ตอบ query
2. **IdempotencyTable**  
   เก็บข้อมูลสำหรับป้องกันการประมวลผลซ้ำจากคำขอเดิม

**หน้าที่หลัก:**
- เก็บข้อมูลธุรกรรมหลักของคำร้อง
- เก็บสถานะล่าสุดของแต่ละคำร้อง
- รองรับการติดตาม request ที่ถูกส่งซ้ำ
- สนับสนุนการออกแบบที่ต้องการทั้งความเร็วและความทนทานในการรับโหลด

### Event Bus (Amazon SNS)
ช่องทางกลางสำหรับกระจายเหตุการณ์สำคัญที่เกิดขึ้นใน RescueRequest Service ไปยังบริการอื่นแบบ asynchronous

**หน้าที่หลัก:**
- ประกาศ domain events ของระบบ
- ลดการผูกกันโดยตรงระหว่าง RescueRequest Service กับ downstream services
- รองรับการขยาย consumer ในอนาคตได้ง่าย

## Explanation
สถาปัตยกรรมของ RescueRequest Service ถูกออกแบบให้เป็นศูนย์กลางจัดการ rescue request โดยแยกบทบาทของระบบออกเป็นส่วนรับคำขอ, ส่วนประมวลผล, ส่วนจัดเก็บข้อมูล และส่วนกระจายเหตุการณ์ไปยังบริการอื่นอย่างชัดเจน

ในฝั่งผู้ใช้งาน ระบบรองรับทั้งประชาชนและเจ้าหน้าที่ผ่าน client คนละบริบท แต่เชื่อมเข้าสู่บริการกลางเดียวกันผ่าน API Gateway ทำให้การควบคุมด้านความปลอดภัย การกำหนดนโยบายการเข้าถึง และการจัดการทราฟฟิกทำได้จากจุดเดียว

แกนหลักของระบบคือ Lambda-based RescueRequest Service Handler ซึ่งเป็นจุดรวมของ business logic ทั้งหมด ไม่ว่าจะเป็นการรับคำร้อง การดูแลสถานะ การจัดการ workflow และการตรวจสอบความถูกต้องของข้อมูลที่เกี่ยวข้องกับ incident โดยเมื่อจำเป็น ระบบจะอ้างอิง IncidentTracking Service เพื่อยืนยันข้อมูล incident จากแหล่งข้อมูลต้นทางที่เชื่อถือได้

ในด้านการจัดเก็บข้อมูล ระบบใช้ DynamoDB เป็น owned data store เพื่อให้ RescueRequest Service ควบคุมโครงสร้างข้อมูลและ lifecycle ของข้อมูลได้เอง โดยแยกข้อมูลคำร้องหลักออกจากข้อมูล idempotency อย่างชัดเจน ช่วยให้ระบบรองรับทั้งการทำงานแบบธุรกรรมหลักและการป้องกันคำสั่งซ้ำจากการ retry ได้อย่างเหมาะสม

อีกส่วนสำคัญคือการแยกการประมวลผลแบบ synchronous ออกจากการสื่อสารแบบ asynchronous เมื่อเกิดเหตุการณ์สำคัญในคำร้อง ระบบจะ publish event ไปยัง Amazon SNS เพื่อให้ downstream services รับไปทำงานต่อได้โดยไม่ทำให้เส้นทางหลักของระบบช้าลง แนวทางนี้ช่วยลด coupling ระหว่างบริการ และทำให้สามารถเพิ่มความสามารถใหม่ในอนาคตได้ง่าย

บริการปลายทางที่เชื่อมต่ออยู่ในระบบปัจจุบัน เช่น RecommendRescueTeam Service และ Rescue Prioritization Service มีบทบาทเฉพาะทางในการช่วยวิเคราะห์และตัดสินใจต่อจากข้อมูลคำร้อง โดยไม่ต้องฝัง logic เหล่านั้นไว้ใน RescueRequest Service เอง ส่งผลให้บริการหลักยังคงเรียบง่าย ดูแลได้ง่าย และโฟกัสกับหน้าที่หลักคือการเป็นระบบรับและจัดการคำร้อง

โดยสรุป สถาปัตยกรรมนี้ทำให้ RescueRequest Service มีบทบาทเป็น transactional core ของระบบ รับผิดชอบ lifecycle ของคำร้องโดยตรง ขณะที่ความสามารถเชิงวิเคราะห์และการตัดสินใจขั้นต่อไปถูกกระจายออกไปยังบริการเฉพาะทางผ่าน event-driven architecture ซึ่งเหมาะกับระบบที่ต้องรองรับโหลดสูง ขยายต่อได้ง่าย และต้องทำงานได้ต่อเนื่องในสถานการณ์วิกฤต

---

# Service Interaction

![Service Interaction](/docs/Service_Interaction_V02.png)

## Upstream Services (บริการต้นทางที่เรียกใช้งาน RescueRequest Service)

### 1) Citizen Mobile/Web App (Citizens)
ใช้สำหรับประชาชนในการสร้างคำร้อง ติดตามสถานะ และส่ง/ดูข้อมูลอัปเดตของคำร้อง

#### Public Endpoints (Citizens)

**GET `/v1/health`**  
ใช้ตรวจสอบสุขภาพรวมของระบบ (รวม liveness + readiness)

**GET `/v1/health/live`**  
ใช้ตรวจสอบว่า process ของ service ยังทำงานอยู่ (ไม่เช็ค downstream dependency)

**GET `/v1/health/ready`**  
ใช้ตรวจสอบความพร้อมให้บริการ โดยเช็ค dependency หลักของระบบ (DynamoDB tables)

**POST `/v1/rescue-requests`**  
ใช้สร้างคำร้องขอความช่วยเหลือใหม่

**POST `/v1/citizen/tracking/lookup`**  
ใช้ค้นหาคำร้องหรือข้อมูลติดตามจากข้อมูลอ้างอิงที่ประชาชนมี

**GET `/v1/citizen/rescue-requests/{requestId}/status`**  
ใช้ตรวจสอบสถานะล่าสุดของคำร้อง

**POST `/v1/citizen/rescue-requests/{requestId}/updates`**  
ใช้ส่งข้อมูลอัปเดตเพิ่มเติมจากประชาชน เช่น อาการเปลี่ยน สถานที่เปลี่ยน หรือข้อมูลติดต่อเพิ่มเติม

**GET `/v1/citizen/rescue-requests/{requestId}/updates`**  
ใช้ดูประวัติข้อมูลอัปเดตของคำร้อง

### 2) Staff Console (Triage / Dispatcher / Admin)
ใช้สำหรับเจ้าหน้าที่ในการดูรายละเอียดคำร้อง แก้ไขข้อมูล ติดตาม event และตรวจสอบข้อมูลประกอบการปฏิบัติงาน

#### Staff Endpoints

**GET `/v1/rescue-requests/{requestId}`**  
ใช้ดูรายละเอียดของคำร้อง

**PATCH `/v1/rescue-requests/{requestId}`**  
ใช้แก้ไขข้อมูลคำร้อง

**GET `/v1/rescue-requests/{requestId}/events`**  
ใช้ดูประวัติ event หรือ timeline ของคำร้อง

**POST `/v1/rescue-requests/{requestId}/events`**  
ใช้บันทึก event ใหม่เข้าสู่คำร้อง

**GET `/v1/rescue-requests/{requestId}/current`**  
ใช้ดู current state หรือ snapshot ปัจจุบันของคำร้อง

**GET `/v1/incidents/{incidentId}/rescue-requests`**  
ใช้ค้นหารายการ rescue request ที่ผูกกับ incident เดียวกัน

**GET `/v1/idempotency-keys/{idempotencyKeyHash}`**  
ใช้ตรวจสอบสถานะของคำขอที่ทำแบบ idempotent เพื่อป้องกันการสร้างข้อมูลซ้ำ

### 3) Workflow / Staff Action / Orchestrator
ใช้สำหรับสั่งเปลี่ยน state ของคำร้องตาม business workflow หรือ state machine

#### Command Endpoints (State Machine)

**POST `/v1/rescue-requests/{requestId}/triage`**  
ใช้เปลี่ยนสถานะเข้าสู่ขั้นตอนคัดกรอง (triage)

**POST `/v1/rescue-requests/{requestId}/assign`**  
ใช้มอบหมายทีม / หน่วยให้คำร้อง

**POST `/v1/rescue-requests/{requestId}/start`**  
ใช้เปลี่ยนสถานะเมื่อเริ่มปฏิบัติงาน

**POST `/v1/rescue-requests/{requestId}/resolve`**  
ใช้ปิดงานเมื่อคำร้องได้รับการช่วยเหลือหรือเสร็จสิ้น

**POST `/v1/rescue-requests/{requestId}/cancel`**  
ใช้ยกเลิกคำร้อง

## Downstream Services (บริการปลายทางที่ RescueRequest Service เรียกหรือส่งข้อมูลไป)

### A) Downstream แบบ Synchronous

#### IncidentTracking Service (Krittamet)
RescueRequest Service เรียกใช้งาน IncidentTracking Service เพื่อใช้ตรวจสอบและอ้างอิงว่า `incidentId` ถูกต้อง มีอยู่จริง และสามารถใช้เชื่อมโยงคำร้องเข้ากับ incident ที่เกี่ยวข้องได้

**ตัวอย่างการเรียก:**

**GET `/v1/incidents/{incidentId}`**

**ผลลัพธ์ที่คาดหวัง:**
- `200 OK` เมื่อพบ incident
- `404 Not Found` เมื่อไม่พบ incident
- `503 Service Unavailable` เมื่อบริการปลายทางไม่พร้อมใช้งาน

**บทบาทหลัก:**
- validate ความถูกต้องของ `incidentId`
- enrich ข้อมูลอ้างอิง incident ให้กับคำร้อง
- เป็นแหล่งอ้างอิงหลักของ incident registry / incident tracking

### B) Downstream แบบ Asynchronous (ส่งข้อมูลผ่าน Pub/Sub)

#### Event Bus (SNS)
RescueRequest Service จะ publish domain events ออกไปยัง Event Bus ผ่าน topic รูปแบบ:

`rescue-request-events-v1-{stage}`

โดย `{stage}` หมายถึง environment หรือ deployment stage เช่น:
- `rescue-request-events-v1-dev`
- `rescue-request-events-v1-uat`
- `rescue-request-events-v1-prod`

เหตุการณ์ที่ publish ครอบคลุมการเปลี่ยนแปลงสำคัญของ rescue request เช่น:
- request created
- request updated
- state transitioned
- citizen update added
- assignment changed
- request resolved
- request cancelled

#### RecommendRescueTeam Service (Kamonphan)
รับ event จาก Event Bus ผ่านคิว:

`SQS: recommend-rescue-team.inbox.v1`

**บทบาทหลัก:**
- ประมวลผลข้อมูลคำร้องและข้อมูล incident ที่เกี่ยวข้อง
- แนะนำทีมกู้ภัยหรือหน่วยปฏิบัติการที่เหมาะสม
- สนับสนุนการตัดสินใจในขั้นตอน assign หรือ dispatch

#### Rescue Prioritization Service (Nattasak)
รับ event จาก Event Bus ผ่านคิว:

`SQS: rescue-prioritization.inbox.v1`

**บทบาทหลัก:**
- ประเมินลำดับความเร่งด่วนของคำร้อง
- คำนวณ priority score จากข้อมูลเหตุการณ์ อาการ สถานที่ หรือข้อมูลประกอบอื่น
- สนับสนุน triage และการจัดลำดับคิวการช่วยเหลือ

## สรุปภาพรวมการไหลของข้อมูล
1. ประชาชนเรียกใช้งาน Public Endpoints เพื่อสร้างคำร้อง ติดตามสถานะ และส่งข้อมูลอัปเดต
2. เจ้าหน้าที่เรียกใช้งาน Staff Endpoints เพื่อดู แก้ไข และติดตามรายละเอียดของคำร้อง
3. การเปลี่ยน state หลักของคำร้องทำผ่าน Command Endpoints เพื่อให้ workflow ชัดเจนและควบคุมได้ตาม state machine
4. RescueRequest Service เรียก IncidentTracking Service แบบ synchronous เพื่อตรวจสอบความถูกต้องของ `incidentId`
5. เมื่อเกิดการเปลี่ยนแปลงสำคัญในระบบ RescueRequest Service จะ publish events ไปยัง `rescue-request-events-v1-{stage}`
6. บริการปลายทาง เช่น RecommendRescueTeam Service และ Rescue Prioritization Service จะ consume events ผ่าน SQS ของตนเองเพื่อนำไปประมวลผลต่อ
