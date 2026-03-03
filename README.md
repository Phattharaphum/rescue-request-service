# 🛟 Rescue Request Service

**GitHub Repository:** [https://github.com/Phattharaphum/rescue-request-service](https://github.com/Phattharaphum/rescue-request-service)

📄 **เอกสารรายละเอียด (Proposal):** [docs/RescueRequest_Service_Proposal_6609612160_V2.pdf](./docs/RescueRequest_Service_Proposal_6609612160_V2.pdf)

---

## 📌 ภาพรวมของบริการ (Service Overview)

**Rescue Request Service** คือ "ศูนย์กลางรับคำร้องขอความช่วยเหลือ" สำหรับสถานการณ์ภัยพิบัติ ทำหน้าที่รับเรื่อง รวบรวมข้อมูลสำคัญ (เช่น พิกัด, จำนวนคน, ความต้องการพิเศษ) และบริหารจัดการสถานะของคำร้องตั้งแต่เริ่มต้นจนจบภารกิจ 

บริการนี้ถูกออกแบบมาเพื่อแก้ปัญหาการแจ้งข้อมูลซ้ำซ้อนเมื่อเครือข่ายไม่เสถียร (ผ่านระบบ Idempotency) และช่วยลดความกังวลของผู้ประสบภัยโดยการออก **"Tracking Code 6 หลัก"** เพื่อให้ประชาชนสามารถติดตามสถานะความช่วยเหลือและแจ้งข้อมูลเพิ่มเติมได้ด้วยตนเอง

**สถาปัตยกรรมหลัก:**
- **Synchronous (REST API):** สำหรับงานที่ต้องการผลลัพธ์ทันที เช่น สร้างคำร้อง, ตรวจสอบสถานะ, และเปลี่ยนสถานะ (อัปเดตข้อมูลลงตาราง Master/Current State ใน DynamoDB)
- **Asynchronous (Event-Driven):** ทุกการสร้างคำร้องหรือเปลี่ยนสถานะ ระบบจะ Publish Events (เช่น `rescue-request.created`, `rescue-request.status-changed`) ผ่าน **SNS → SQS** เพื่อกระจายงานไปยังบริการอื่นๆ (Dispatch, Notification, Analytics) โดยไม่กระทบการทำงานหลัก

---

## 🚀 เส้น API พื้นฐาน (Core API Routes)

ระบบใช้ Base Path: `/v1` แบ่งตามกลุ่มผู้ใช้งานดังนี้:

### 🧑‍🤝‍🧑 สำหรับประชาชน (Citizens / Public Channels)
เน้นการรับเรื่อง ยืนยันตัวตนด้วยเบอร์โทรศัพท์และ Tracking Code เพื่อความปลอดภัยและเป็นส่วนตัว

* `POST /v1/rescue-requests` - สร้างคำร้องขอความช่วยเหลือ (ได้ Tracking Code กลับไป)
* `POST /v1/citizen/tracking/lookup` - ค้นหาคำร้องด้วยเบอร์โทรศัพท์ + Tracking Code
* `GET /v1/citizen/rescue-requests/{requestId}/status` - ดูสถานะล่าสุดของคำร้อง
* `POST /v1/citizen/rescue-requests/{requestId}/updates` - แจ้งข้อมูลเพิ่มเติม (เช่น ระดับน้ำ, ตำแหน่งอ้างอิง)
* `GET /v1/citizen/rescue-requests/{requestId}/updates` - ดูประวัติการแจ้งข้อมูลเพิ่มเติม

### 👨‍💻 สำหรับเจ้าหน้าที่ (Staff / Dispatcher / Rescue Team)
เน้นการจัดการสถานะ (State Machine) ควบคุมการเปลี่ยนสถานะตามขั้นตอนที่กำหนดอย่างเคร่งครัด

* `GET /v1/incidents/{incidentId}/rescue-requests` - ดึงรายการคำร้องทั้งหมดในเหตุการณ์ภัยพิบัตินั้นๆ
* `GET /v1/rescue-requests/{requestId}` - ดูรายละเอียดข้อมูลของคำร้องทั้งหมด
* `PATCH /v1/rescue-requests/{requestId}` - แก้ไขรายละเอียดคำร้อง (ข้อมูลทั่วไป)
* `GET /v1/rescue-requests/{requestId}/events` - ดู Audit Trail / Timeline การเปลี่ยนสถานะทั้งหมด

**คำสั่งจัดการสถานะ (State Machine Commands):**
* `POST /v1/rescue-requests/{requestId}:triage` - คัดกรองและให้คะแนนความเร่งด่วน (`SUBMITTED` -> `TRIAGED`)
* `POST /v1/rescue-requests/{requestId}:assign` - มอบหมายทีมกู้ภัย (`TRIAGED` -> `ASSIGNED`)
* `POST /v1/rescue-requests/{requestId}:start` - ทีมกู้ภัยเริ่มปฏิบัติงานพื้นที่ (`ASSIGNED` -> `IN_PROGRESS`)
* `POST /v1/rescue-requests/{requestId}:resolve` - ช่วยเหลือสำเร็จ ปิดงาน (`IN_PROGRESS` -> `RESOLVED`)
* `POST /v1/rescue-requests/{requestId}:cancel` - ยกเลิกคำร้อง พร้อมระบุเหตุผล (เปลี่ยนจากสถานะใดก็ได้ไปเป็น `CANCELLED`)

---

## 🛠 ข้อมูลนักศึกษา (Service Owner)
* **ชื่อ-นามสกุล:** นายภัทรภูมิ กิ่งชัย
* **รหัสนักศึกษา:** 6609612160 (ภาคปกติ)