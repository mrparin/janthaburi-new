# แนวทางการพัฒนา Dashboard สำหรับระบบหลายโซน

## สรุปทั่วไป
ปรับปรุงจาก "จอเดียว-เซนเซอร์เดียว" ไปเป็น "โครงสร้างหลายโซนแบบสเกลได้" โดยออกแบบ 3 ชั้น: ข้อมูล, หน้าจอ, การแจ้งเตือน

---

## 1. โครงสร้างข้อมูล

### เอนทิตีหลัก
- **Zone**: โซนหรือพื้นที่ที่ต้องการตรวจสอบ
  - `zone_id`, `zone_name`, `description`, `location`, `status`
  - มี baseline/threshold ของโซน
  
- **Sensor**: เซนเซอร์แต่ละตัว
  - `sensor_id`, `zone_id`, `sensor_type`, `sensor_name`, `unit`
  - เช่น: Temperature, Humidity, CO2, Pressure

- **Reading**: ค่าที่อ่านจากเซนเซอร์
  - `reading_id`, `sensor_id`, `zone_id`, `value`, `timestamp`
  - เก็บทุกค่า ต้องอนุญาตให้ query ย้อนหลัง

- **AlertRule**: กฎการแจ้งเตือน
  - `rule_id`, `zone_id`, `sensor_type`, `condition`, `threshold_min`, `threshold_max`, `severity`
  - รองรับหลายกฎต่อเซนเซอร์

- **Alert/Event**: เหตุการณ์ที่เกิดขึ้น
  - `alert_id`, `zone_id`, `sensor_id`, `rule_id`, `triggered_at`, `resolved_at`, `severity`, `acknowledged`

### หลักการสำคัญ
- ทุกค่าเซนเซอร์ต้องมี `zone_id`, `sensor_id`, `timestamp`
- รองรับทั้งค่าปัจจุบันและสถิติย้อนหลัง (avg/min/max)
- เก็บ alert history สำหรับวิเคราะห์เทรนด์

---

## 2. หน้า Dashboard หลัก (Overview)

### ที่ไปและการแสดงผล
- เป็นหน้าแรกที่เห็นทุกหน้าที่เปิดจอในครั้งแรก
- ใช้การ์ด (Card) โซนเรียงเป็นกริด: 1 การ์ด = 1 โซน

### สิ่งที่ต้องแสดงในการ์ดโซน
1. **ชื่อโซน** และลำดับความสำคัญ
2. **KPI หลัก**: 
   - ค่าอุณหภูมิ, ความชื้น, หรือค่าสำคัญอื่น
   - ค่า Min/Max ของวันนี้ (ถ้าเกี่ยวข้อง)
3. **สถานะสี**:
   - 🟢 ปกติ (All OK)
   - 🟡 เตือน (Warning - threshold exceeded)
   - 🔴 วิกฤต (Critical - severe threshold)
4. **เวลาอัปเดตล่าสุด**: เพื่อบอกว่าข้อมูลยังสดใหม่
5. **จำนวน Alert ที่ pending**: แสดงจำนวนเตือนที่ยังไม่ได้ handle

### การจัดเรียง
- โซนที่มีความเสี่ยงสูง (Critical/Warning) ขึ้นบนสุด
- ตามด้วยโซนปกติ
- สามารถเรียงลำดับตามระดับความสำคัญได้

### ฟังก์ชัน
- **คลิกการ์ด**: ไปหน้า Zone Detail
- **Auto-rotate** (สำหรับ kiosk): เลื่อนไปยังโซนต่อไปทุก 10-20 วินาที (ถ้าไม่มี interaction)
- **ปุ่มรีเฟรช**: อัปเดตข้อมูลทันที

---

## 3. หน้าเจาะลึกโซน (Zone Detail)

### ที่ไปและจุดประสงค์
- เมื่อกดการ์ดโซนจากหน้า Overview จะมาที่นี่
- ดูรายละเอียดทั้งหมดของโซนนั้น

### สิ่งที่แสดง
1. **ข้อมูลโซน**
   - ชื่อโซน, ตำแหน่ง, คำอธิบาย
   - สถานะรวม และเวลาอัปเดตล่าสุด

2. **กราฟย้อนหลังของทุกเซนเซอร์ในโซน**
   - แสดง 24 ชั่วโมงที่ผ่านมา (หรือช่วงเวลาที่ปรับได้)
   - เส้นแต่ละสีแทนเซนเซอร์ต่างกัน
   - มี line chart ที่มี min/max/avg

3. **ตารางค่าเซนเซอร์ปัจจุบัน**
   - | Sensor Name | Current | Min (24h) | Max (24h) | Status |
   - ทีละแถว

4. **เหตุการณ์ผิดปกติและ Alert ล่าสุด**
   - Timeline หรือ log ของ alert ที่เกิดขึ้นใน 7 วันที่ผ่านมา
   - แสดง: triggered_at, severity, reason (ค่าใด exceeded), resolved_at

5. **เปรียบเทียบกับ baseline**
   - ระบุว่าค่าปัจจุบันเทียบกับ baseline/target เป็นอย่างไร
   - เช่น: Temp = 25°C (+2 vs target 23°C) 🟡

### ฟังก์ชัน
- **ตัวเลือกช่วงเวลา**: 24h, 7d, 30d, Custom
- **ปุ่มกลับ**: ไปหน้า Overview
- **Export**: ดาวน์โหลด CSV ของข้อมูลโซนนี้

---

## 4. หน้าเปรียบเทียบหลายโซน (Compare View)

### ที่ไปและจุดประสงค์
- เทียบค่าข้ามโซนทันที
- หารูปแบบ และปัญหาที่ซ้ำกัน

### ตัวเลือกแสดงผล
1. **ตารางเปรียบเทียบ (Comparison Table)**
   - แถวแต่ละแถว = โซน
   - คอลัมน์ = เซนเซอร์ประเภทต่างๆ
   - ทำให้เห็นค่าทั้งหมดในแบบ tabular

2. **Heatmap**
   - เซล = (โซน, เซนเซอร์)
   - สีแสดงว่าค่าเป็นอย่างไร: 🔵 ต่ำ, 🟢 ปกติ, 🟡 เตือน, 🔴 วิกฤต
   - ง่ายต่อการ spot anomalies

3. **โหมด "Top N ผิดปกติ"**
   - แสดงเฉพาะ N โซนที่มี alert มากที่สุด
   - ช่วยให้ต้องการหาปัญหา priority high ก่อน

### ตัวกรอง
- ✓ ตัวเลือกช่วงเวลา (24h, 7d, 30d)
- ✓ ตัวกรองตามประเภทเซนเซอร์ (Temperature, Humidity, ...)
- ✓ ตัวกรองตามสถานะเตือน (All, Critical Only, Warning+)
- ✓ ตัวกรองตามโซน (All zones, or specific zones)

### ฟังก์ชัน
- **เรียงลำดับ**: ตามค่า, ตามสถานะ, ตามชื่อ
- **Export**: ดาวน์โหลด CSV ของตารางนี้

---

## 5. ระบบแจ้งเตือน (Alert System)

### หลักการ
- ตั้งกฎรายโซนได้ สำหรับแต่ละประเภทเซนเซอร์
- สนับสนุน **hysteresis** หรือ **debounce** เพื่อลด false alarm
- แยก **severity** ชัดเจน

### ระดับความรุนแรง
1. **INFO** - ข้อมูล ไม่ต้อง alert แต่เก็บ log
2. **WARNING** - ต้องเตือน แต่ยังใช้งานได้
3. **CRITICAL** - จำเป็นต้องจัดการโดยด่วน
4. **EMERGENCY** - ต้องรีเซ็ตระบบหรือ escalate ทันที

### ส่วนประกอบของกฎ (Alert Rule)
```
{
  "rule_id": "R001",
  "zone_id": "Z01",
  "sensor_type": "Temperature",
  "condition": "out_of_range",
  "threshold_min": 20,
  "threshold_max": 28,
  "severity": "WARNING",
  "debounce_seconds": 30,
  "hysteresis": 2  // ค่าต้องกลับเข้า hysteresis ขอบเขต ก่อนยกเลิก alert
}
```

### ลำดับขั้นการ trigger
1. ค่ากดใน sensor reading
2. เปรียบเทียบกับกฎทั้งหมด
3. หากกฎถูก trigger → รอ debounce_seconds (เช่น 30 วิ) หากค่า stable → สร้าง alert
4. แจ้งเตือน: log, dashboard highlight, email/SMS (ถ้ากำหนด)

### ส่วนติดตาม (Acknowledge & Snooze)
- **Acknowledge**: ผู้ใช้ยอมรับว่ารู้เรื่องแล้ว (ไม่ปิดแจ้ง แต่บันทึกว่าทรราชรู้)
- **Snooze**: ปิดการแจ้งเตือนชั่วคราว 5/15/60 นาที (กลับมาแจ้งอีกครั้งถ้ายังเป็นปัญหา)
- **Resolve**: ปิดเมื่อปัญหาแก้ไขแล้ว (ค่ากลับเข้าช่วง)

---

## 6. ประสบการณ์บนจอ Kiosk

### จุดเด่น
- จอทั่ว 24/7 ต้องได้ info ที่ "readable at a glance"
- ไม่มีโต้ตอบ (touch) ส่วนใหญ่ เพราะเป็น kiosk ประจำจุด

### การไหล (Layout & Flow)
1. **หน้าแรก**: Overview กับการ์ดทุกโซน
2. **Auto-rotate**: ถ้า idle ตั้ง 15-20 วิ → หมุนไปยังโซนต่อไป
3. **Sticky Alert Bar**: แถบด้านบน/ล่างตลอดเวลาแสดง
   - 🔴 Critical alert summary: "Z03 Temperature HIGH (28°C)"
   - หรือ "3 Alerts Pending"
4. **Interaction Timeout**: ถ้าผู้ใช้ไม่กด/scroll นาน > 5 นาที → กลับหน้า Overview อัตโนมัติ

### ตัวอักษร และความคมชัด
- ใช้ฟอนต์ใหญ่สำหรับค่า (16pt+)
- ใช้สี high-contrast (มีพื้นหลัง dark หรือ light ให้เห็นชัด)
- ไอคอนขนาดใหญ่ เพื่อ quick recognition

### ปรับปรุงจาก current kiosk launcher
- เพิ่ม logic ใน [setup_pi_kiosk.sh](scripts/setup_pi_kiosk.sh) เพื่อ serve dashboard ที่สนับสนุนหลายโซน

---

## 7. ลำดับพัฒนา (Phased Approach)

### เฟส 1: Data & Basic Overview (สัปดาห์ที่ 1-2)
**Scope**:
- เพิ่ม `zone_id` + `zone_name` ในฐานข้อมูล (table Zone, Sensor update)
- ปรับ API: MQTT client ส่ง zone info
- ปรับ dashboard ให้เป็นหน้า Overview แบบการ์ด (1 card = 1 zone)
- บันทึกค่า min/max/avg ต่อวัน

**เอาต์พุต**:
- ✅ Zone table ใน database
- ✅ Updated MQTT message format
- ✅ Overview page with zone cards

**ทดสอบ**:
- Mock data หลายโซน, ตรวจสอบหน้าแสดงผลถูกต้อง

---

### เฟส 2: Zone Detail + Historical Graph (สัปดาห์ที่ 3-4)
**Scope**:
- สร้างหน้า Zone Detail ให้โหลดกราฟ 24h ของเซนเซอร์ทั้งหมดในโซน
- ทำ API endpoint: `/api/zone/{zone_id}/readings?period=24h`
- ทำตารางค่าเซนเซอร์ปัจจุบัน min/max
- เพิ่มลิงก์จาก Overview card ไปหน้า Zone Detail

**เอาต์พุต**:
- ✅ Zone Detail page
- ✅ Historical graph (24h, 7d, 30d)
- ✅ Readings table with stats

**ทดสอบ**:
- Verify กราฟ data accuracy
- Test responsive design บน Pi screen

---

### เฟส 3: Alert Rules + Event Logging (สัปดาห์ที่ 5-6)
**Scope**:
- สร้าง AlertRule table + logic
- Implement trigger logic: check reading vs rules, trigger alert
- ทำ debounce/hysteresis logic
- เพิ่ม Event table เพื่อเก็บ alert history
- หน้า Overview highlight zone ที่มี alert
- ทำ alert section ใน Zone Detail page

**เอาต์พุต**:
- ✅ Alert Rule CRUD (backend + frontend)
- ✅ Real-time alert generation
- ✅ Alert history view

**ทดสอบ**:
- Trigger manual readings ที่ exceed threshold
- Verify false alarm prevention (debounce)

---

### เฟส 4: Compare View + Kiosk Enhancements (สัปดาห์ที่ 7-8)
**Scope**:
- สร้าง Compare View: ตาราง / heatmap ของทั้งระบบ
- ทำตัวกรอง: date range, sensor type, severity
- ทำ auto-rotate logic สำหรับ kiosk
- เพิ่ม sticky alert bar
- Interaction timeout logic

**เอาต์พุต**:
- ✅ Compare View page
- ✅ Kiosk auto-rotate + timeout
- ✅ Alert bar ที่ sticky

**ทดสอบ**:
- Long-running test บน Pi 24h+
- Verify rotate mechanism
- Screen timeout ที่ set ไว้ยังคงใช้งาน

---

## 8. โครงสร้างฐานข้อมูล (Reference)

### Schema หลัก
```sql
-- Zone
CREATE TABLE zone (
  zone_id TEXT PRIMARY KEY,
  zone_name TEXT NOT NULL,
  description TEXT,
  location TEXT,
  status TEXT DEFAULT 'OK'
);

-- Sensor
CREATE TABLE sensor (
  sensor_id TEXT PRIMARY KEY,
  zone_id TEXT NOT NULL,
  sensor_type TEXT,
  sensor_name TEXT,
  unit TEXT,
  FOREIGN KEY (zone_id) REFERENCES zone(zone_id)
);

-- Reading (core data)
CREATE TABLE reading (
  reading_id TEXT PRIMARY KEY,
  sensor_id TEXT NOT NULL,
  zone_id TEXT NOT NULL,
  value REAL,
  timestamp DATETIME,
  FOREIGN KEY (sensor_id) REFERENCES sensor(sensor_id),
  FOREIGN KEY (zone_id) REFERENCES zone(zone_id),
  INDEX (zone_id, timestamp),
  INDEX (sensor_id, timestamp)
);

-- AlertRule
CREATE TABLE alert_rule (
  rule_id TEXT PRIMARY KEY,
  zone_id TEXT NOT NULL,
  sensor_type TEXT,
  condition TEXT, -- "out_of_range", "above", "below"
  threshold_min REAL,
  threshold_max REAL,
  severity TEXT, -- "INFO", "WARNING", "CRITICAL"
  debounce_seconds INT DEFAULT 0,
  hysteresis REAL DEFAULT 0,
  FOREIGN KEY (zone_id) REFERENCES zone(zone_id)
);

-- Event/Alert (triggered events)
CREATE TABLE event (
  event_id TEXT PRIMARY KEY,
  zone_id TEXT NOT NULL,
  sensor_id TEXT,
  rule_id TEXT,
  triggered_at DATETIME,
  resolved_at DATETIME,
  severity TEXT,
  acknowledged BOOLEAN DEFAULT FALSE,
  FOREIGN KEY (zone_id) REFERENCES zone(zone_id),
  FOREIGN KEY (sensor_id) REFERENCES sensor(sensor_id),
  FOREIGN KEY (rule_id) REFERENCES alert_rule(rule_id)
);
```

---

## 9. Checklist เริ่มต้น

- [ ] ออกแบบ ER diagram สำหรับหลายโซน
- [ ] สร้าง Zone & Sensor table ในฐานข้อมูล
- [ ] ปรับ MQTT client ให้ส่ง zone_id
- [ ] ปรับ API ให้ return zone info
- [ ] ทำหน้า Overview (phase 1)
- [ ] ทำหน้า Zone Detail (phase 2)
- [ ] Implement Alert Rule (phase 3)
- [ ] ทำ Compare View (phase 4)
- [ ] ทดสอบ end-to-end หลายโซน
- [ ] Update Kiosk launcher script

---

## 10. หมายเหตุสำคัญ

1. **ข้อมูลสตรีมมิ่ง**: ระวังปริมาณข้อมูล ถ้า sensor หลาย ๆ ตัว ต้องเพิ่ม index และเก็บแบบ time-series DB (InfluxDB, TimescaleDB) เพื่อ query ได้เร็ว

2. **ระบบเตือนแน่น**: ควร log ทุก trigger ทั้ง true & false ปลอย เพื่อ analyze pattern

3. **UI/UX ที่ readable**: สำคัญมากสำหรับ kiosk ที่ไม่มี interaction หลัก

4. **Backward compatibility**: ควรให้ current dashboard ทำงานได้ หลังจากเปลี่ยนไป multi-zone

