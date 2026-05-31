# Durian Dashboard (Python Native)

Lightweight MQTT dashboard for Raspberry Pi 3 without Node-RED, InfluxDB, or ThingsBoard.

## Stack

- FastAPI (web app + API + websocket)
- paho-mqtt (MQTT subscriber)
- SQLite (short-term history)
- Jinja2 + Chart.js (dashboard UI)

## Features

- Subscribes to `durian_farm1/node_sensor`
- Normalizes payload fields (`air_temp`/`Air_temp`, `soil_temp`/`Soil_temp`)
- Calculates derived metrics:
  - `es_kpa`, `ea_kpa`, `vpd_kpa`
  - `solar_wm2_est`, `solar_mj_m2_h_est`
  - `eto_mm_h_est`, `eto_mm_day_est`
- Computes status and recommendation fields:
  - `vpd_status`, `vpd_message`, `vpd_action`
  - `ph_status`, `ph_message`, `ph_action`
- Realtime cards and history charts (24h / 7d)
- TMD Weather Forecast API integration (province/amphoe/tambon)
- Merged farm summary from onsite sensors + TMD forecast
- LINE push alerts for warning/danger risk levels

## Version updates (May 2026)

รายการอัปเดตสำคัญในเวอร์ชันนี้:

- เปลี่ยนแหล่งพยากรณ์จาก Open-Meteo เป็น TMD NWP API (OAuth Bearer token)
- เพิ่ม endpoint ใหม่สำหรับพยากรณ์และสรุปความเสี่ยง:
  - `GET /api/weather`
  - `GET /api/farm-summary`
  - `POST /api/line/test-alert`
- เพิ่มการรวมข้อมูลสถานีในสวน + พยากรณ์ TMD เพื่อคำนวณ `risk_level` (`normal`/`warning`/`danger`)
- เพิ่มการแจ้งเตือน LINE ทั้งแบบ manual test และแบบ periodic auto-alert (ตั้งค่าได้จาก `.env`)
- ปรับข้อความ LINE เป็นรูปแบบอ่านง่ายพร้อมไอคอน
- ปรับ UI ส่วนพยากรณ์ 7 วัน และช่องกรอกตำแหน่ง (ตำบล/อำเภอ/จังหวัด)
- เพิ่ม fallback ตอนค้นหาพื้นที่ TMD:
  - ลอง `ตำบล+อำเภอ+จังหวัด`
  - ถ้าไม่พบจะลดเป็น `อำเภอ+จังหวัด`
  - ถ้ายังไม่พบจะลอง `จังหวัด` เพื่อไม่ให้หน้าเว็บล้มง่ายเมื่อสะกดชื่อพื้นที่ไม่ตรง

## การรันบนเครื่อง local (Windows) เพื่อทดสอบ

ใช้ขั้นตอนนี้เพื่อทดสอบโปรเจกต์บนเครื่องนี้ (path ปัจจุบัน: `D:\codeArduino\vscode\pi-dashboard`)

### แบบใช้ Command Prompt (cmd)

1) เข้าโฟลเดอร์โปรเจกต์

```bat
cd /d D:\codeArduino\vscode\pi-dashboard
```

2) สร้าง virtual environment (ครั้งแรกเท่านั้น)

```bat
py -3 -m venv .venv
```

3) activate environment

```bat
.venv\Scripts\activate
```

4) ติดตั้ง dependencies

```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5) รันแอปเพื่อทดสอบ

```bat
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

6) เปิดหน้าเว็บทดสอบ

- Dashboard: http://127.0.0.1:8080
- Latest API: http://127.0.0.1:8080/api/latest

7) หยุดแอป

กด `Ctrl + C` ในหน้าต่าง cmd ที่กำลังรัน Uvicorn

### แบบใช้ PowerShell

```powershell
cd D:\codeArduino\vscode\pi-dashboard
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

หมายเหตุ:
- ถ้าระบบบล็อกการรันสคริปต์ตอน activate บน PowerShell ให้รันคำสั่งนี้ครั้งเดียวก่อน:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## คู่มือการติดตั้งและอัปเดต

### 1) การติดตั้งลงใน Raspberry Pi

เหมาะกับ Raspberry Pi OS (Bookworm/Bullseye) และทดสอบกับ Pi 3

เตรียมเครื่องครั้งแรก:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git
```

ดึงโปรเจกต์ครั้งแรก:

```bash
cd /opt
sudo git clone <YOUR_REPO_URL> durian-dashboard
sudo chown -R pi:pi /opt/durian-dashboard
```

ตั้งค่าไฟล์ `.env` (ครั้งแรก):

```bash
cd /opt/durian-dashboard
cp .env.example .env
```

ติดตั้งแบบ kiosk (เปิด browser อัตโนมัติ):

```bash
cd /opt/durian-dashboard
sudo bash scripts/setup_pi_kiosk.sh --yes
```

ตรวจผลหลังติดตั้ง:

```bash
sudo systemctl status durian-dashboard --no-pager
sudo ss -tulpn | grep 8080
```

ปิดหน้า browser/kiosk ปัจจุบัน (กรณีต้องการหยุดชั่วคราว):

```bash
pkill -f start-dashboard-kiosk.sh
pkill -f "chromium|chromium-browser"
```

หมายเหตุ:
- ถ้าหน้างานไม่ได้ใช้ broker ในเครื่องเดียวกัน ให้ตั้ง `MQTT_HOST` เป็น broker ปลายทาง
- ถ้าเก็บข้อมูลจริงไว้ที่ server อยู่แล้ว แนะนำตั้ง `RETAIN_DAYS=90` (เก็บ local cache 3 เดือน)

### 2) การ update software จาก git ใหม่

ใช้เมื่อมีการเปลี่ยนแปลงซอฟต์แวร์ใหม่ใน repository

```bash
cd /opt/durian-dashboard
git status
git branch --show-current
```

กรณีต้องการอัปเดต branch `02_addweather` (แนะนำ):

```bash
git fetch origin
git switch 02_addweather
git pull --ff-only origin 02_addweather
```

ถ้าโครงการใช้ branch `main`:

```bash
git pull --ff-only origin main
```

ถ้าโครงการใช้ branch `master`:

```bash
git pull --ff-only origin master
```

ถ้า pull ไม่ได้เพราะมีไฟล์แก้ค้าง:

```bash
git stash
git pull --ff-only origin 02_addweather
git stash pop
```

อัปเดต dependency/service หลัง pull:

```bash
sudo bash scripts/setup_pi_kiosk.sh --yes
sudo systemctl restart durian-dashboard
```

### 2.1) การเปลี่ยนผ่านกรณีเครื่องเดิมเคยติดตั้งโปรแกรมเก่า (ที่ไม่ได้มาจาก repository นี้ หรือชื่อต่างกัน)

หากเครื่อง Raspberry Pi ของคุณเคยติดตั้งระบบเวอร์ชันเดิมมาก่อน (เช่น รันด้วย Service ชื่ออื่น หรืออยู่ในโฟลเดอร์อื่นที่มีชื่อไม่ตรงกัน หรือดึงมาจาก Git repository ตัวเดิมที่ไม่ได้อัปเดต) และต้องการเปลี่ยนมาใช้งานโปรแกรมจาก repository นี้แทนอย่างสมบูรณ์ ให้ทำตามขั้นตอนด้านล่างนี้:

**ขั้นตอนที่ 1: ตรวจสอบและหยุดการทำงานของระบบเดิม**
1. ตรวจสอบชื่อ Service เก่าที่รันอยู่ในระบบ (มักมีชื่อคล้ายๆ `durian-dashboard` หรือชื่ออื่นตามที่คุณเคยตั้งไว้)
2. สั่งหยุดการทำงาน (Stop) และยกเลิกการเริ่มทำงานอัตโนมัติตอนเปิดเครื่อง (Disable) ของระบบเก่า:
   ```bash
   sudo systemctl stop <ชื่อ-service-เก่า>
   sudo systemctl disable <ชื่อ-service-เก่า>
   ```

**ขั้นตอนที่ 2: ดึงข้อมูลโปรเจกต์ใหม่จาก GitHub**
เราแนะนำให้ติดตั้งโปรเจกต์นี้ไว้ที่โฟลเดอร์ `/opt/durian-dashboard` เพื่อให้สอดคล้องกับสคริปต์ควบคุมและชื่อ Service มาตรฐาน:

*หมายเหตุ: เนื่องจากเครื่องเดิมมีโฟลเดอร์ `/opt/durian-dashboard` อยู่แล้ว หากรันคำสั่ง `git clone` จะขึ้นข้อผิดพลาดแจ้งว่าโฟลเดอร์ไม่ว่าง ให้สั่งเปลี่ยนชื่อโฟลเดอร์เก่าเพื่อสำรองข้อมูลไว้ก่อน ดังนี้:*
```bash
sudo mv /opt/durian-dashboard /opt/durian-dashboard-old
```

1. ดาวน์โหลด (clone) โปรเจกต์ใหม่จาก repository นี้:
   ```bash
   cd /opt
   sudo git clone https://github.com/mrparin/Phanmanee.git durian-dashboard
   ```
2. เปลี่ยนสิทธิ์ความเป็นเจ้าของโฟลเดอร์ให้เหมาะสมกับผู้ใช้งาน (ตัวอย่างเป็น user `pi`):
   ```bash
   sudo chown -R pi:pi /opt/durian-dashboard
   ```

**ขั้นตอนที่ 3: โยกย้ายฐานข้อมูลและไฟล์ตั้งค่าเก่า (ทางเลือก/ถ้ามี)**
* **กรณีต้องการรักษาข้อมูลประวัติย้อนหลัง:** ให้คัดลอกไฟล์ฐานข้อมูล SQLite จากโฟลเดอร์สำรองเก่ามาไว้ในโฟลเดอร์ใหม่:
  ```bash
  cp /opt/durian-dashboard-old/data/durian_dashboard.db /opt/durian-dashboard/data/durian_dashboard.db
  ```
* **กรณีต้องการใช้ค่าคอนฟิกเดิม:** ตรวจสอบค่าต่างๆ ในไฟล์ `.env` เดิม (เช่น `MQTT_HOST`, `MQTT_TOPIC`, `RETAIN_DAYS` ฯลฯ) จากโฟลเดอร์สำรองเก่า `/opt/durian-dashboard-old/.env` แล้วนำมาใส่ไว้ในไฟล์ `.env` ของโฟลเดอร์ใหม่:
  ```bash
  cd /opt/durian-dashboard
  cp .env.example .env
  # จากนั้นเปิดแก้ไขไฟล์ .env เพื่อใส่ค่าคอนฟิกให้ตรงกับของเดิม
  nano .env
  ```

**ขั้นตอนที่ 4: รันสคริปต์ติดตั้งระบบใหม่**
เลือกประเภทการติดตั้งที่ต้องการเพื่อสร้าง Virtual Environment, ติดตั้งไลบรารีที่จำเป็น และติดตั้ง Service ใหม่เข้าระบบ:
* **แบบใช้งานจอภาพบนบอร์ด Pi (Kiosk Mode):**
  ```bash
  cd /opt/durian-dashboard
  sudo bash scripts/setup_pi_kiosk.sh --yes
  ```
* **แบบรันเฉพาะหลังบ้าน (Service Only / Server):**
  ```bash
  cd /opt/durian-dashboard
  sudo bash scripts/setup_pi_service_only.sh --yes
  ```

**ขั้นตอนที่ 5: ตรวจสอบการทำงานของระบบใหม่**
ตรวจสอบว่า Service ตัวใหม่เริ่มทำงานและเปิดพอร์ตสำเร็จ:
```bash
sudo systemctl status durian-dashboard --no-pager
sudo ss -tulpn | grep 8080
```

**ขั้นตอนที่ 6: ลบไฟล์ของระบบเก่า (เพื่อความสะอาด)**
เมื่อระบบใหม่ทำงานได้อย่างถูกต้องเรียบร้อยแล้ว สามารถลบโฟลเดอร์เก่าและไฟล์ Service เดิมเพื่อไม่ให้เกิดความสับสน:
```bash
# ลบไฟล์ Service เก่าออกจากการจัดระบบของ systemd
sudo rm /etc/systemd/system/<ชื่อ-service-เก่า>.service
sudo systemctl daemon-reload

# ลบโฟลเดอร์โปรเจกต์เดิม (ระมัดระวังตอนระบุ path)
sudo rm -rf /opt/<โฟลเดอร์โปรเจกต์เดิม>
```

### 3) ติดตั้งไปยังเครื่อง server ใหม่ (user ไม่เหมือน Raspberry Pi)

กรณีเครื่องใหม่มี user ไม่ใช่ `pi` (ตัวอย่างใช้ `bigdata`):

```bash
cd /opt/durian-dashboard
sudo PI_USER=bigdata APP_DIR=/opt/durian-dashboard bash scripts/setup_pi_service_only.sh --yes
```

ตรวจว่า service ถูก deploy ด้วย user/group ที่ถูกต้อง:

```bash
sudo systemctl cat durian-dashboard | grep -E '^(User|Group)='
```

ตัวอย่างผลที่ควรได้:

```bash
User=bigdata
Group=bigdata
```

ถ้าพอร์ต 8080 ถูกใช้งานอยู่แล้ว ให้เปลี่ยนพอร์ตในไฟล์ service แล้ว reload:

```bash
sudo sed -i 's/--port 8080/--port 8081/' /etc/systemd/system/durian-dashboard.service
sudo systemctl daemon-reload
sudo systemctl restart durian-dashboard
```

### 4) การติดตั้งเฉพาะ service อย่างเดียว (ไม่เปิด browser อัตโนมัติ)

ใช้สคริปต์ `scripts/setup_pi_service_only.sh`

แบบ interactive:

```bash
cd /opt/durian-dashboard
sudo bash scripts/setup_pi_service_only.sh
```

แบบ non-interactive:

```bash
cd /opt/durian-dashboard
sudo bash scripts/setup_pi_service_only.sh --yes
```

สิ่งที่สคริปต์นี้ทำ:
- ติดตั้ง Python packages ที่จำเป็น
- สร้าง/อัปเดต virtual environment
- ติดตั้งและเริ่ม `durian-dashboard.service`

สิ่งที่สคริปต์นี้ไม่ทำ:
- ไม่ตั้งค่า desktop autologin
- ไม่สร้าง browser autostart

ตรวจสถานะหลังติดตั้ง:

```bash
sudo systemctl status durian-dashboard --no-pager
sudo journalctl -u durian-dashboard -n 100 --no-pager
```

### 5) การตั้งค่าความสว่างจอ Touchscreen (rpi_backlight)

ใช้ได้เฉพาะกับ **Official Raspberry Pi 7" Touchscreen** เท่านั้น (ใช้ driver `rpi_backlight`)

#### ระหว่างติดตั้งด้วย setup_pi_kiosk.sh

สคริปต์จะถามว่าใช้จอ Touchscreen หรือเปล่า:

```
ใช้จอ Touchscreen หรือเปล่า? (จะตั้งค่าความสว่างจอให้) [n]: y
ความสว่างจอ (0=ดับ, 255=เต็ม, 128=50%) [128]: 100
```

- ตอบ **y** → สคริปต์จะสร้างและเปิดใช้งาน `set-backlight.service` ซึ่งจะตั้งค่าความสว่างทุกครั้งที่ reboot
- ตอบ **n** (หรือกด Enter) → ข้ามการตั้งค่าความสว่างทั้งหมด จอจะทำงานตามปกติ

#### ระบุค่าล่วงหน้าผ่าน Environment variable

```bash
sudo USE_TOUCHSCREEN=y SCREEN_BRIGHTNESS=100 bash scripts/setup_pi_kiosk.sh --yes
```

#### ค่าความสว่างที่แนะนำ

| ค่า | ระดับความสว่าง |
|---:|---|
| 255 | เต็ม 100% (ค่าเริ่มต้นของระบบ) |
| 180 | ~70% (สว่างพอดี ในห้องสว่าง) |
| 128 | ~50% (ค่าเริ่มต้นที่แนะนำ ยืดอายุจอ) |
| 80  | ~30% (สำหรับห้องมืด/กลางคืน) |
| 0   | ดับจอ (ยังใช้งานได้ via SSH) |

#### ปรับความสว่างด้วยตนเองขณะใช้งาน

```bash
# ดูค่าปัจจุบัน
cat /sys/class/backlight/rpi_backlight/brightness

# ตั้งค่าใหม่ (เช่น 100)
echo 100 | sudo tee /sys/class/backlight/rpi_backlight/brightness
```

#### ปรับค่า default สำหรับ reboot ครั้งต่อไป

```bash
sudo nano /etc/systemd/system/set-backlight.service
# แก้บรรทัด Environment=BRIGHTNESS=128 เป็นค่าที่ต้องการ
sudo systemctl daemon-reload
```

#### ตรวจสอบสถานะ service

```bash
sudo systemctl status set-backlight --no-pager
```

## Environment variables (reference)

ค่าที่รองรับในระบบ:

```bash
MQTT_HOST
MQTT_PORT
MQTT_TOPIC
MQTT_QOS
DB_PATH
RETAIN_DAYS
APP_HOST
APP_PORT
REFRESH_SECONDS
TMD_BASE_URL
TMD_ACCESS_TOKEN
TMD_PROVINCE
TMD_AMPHOE
TMD_TAMBON
TMD_FORECAST_DAYS
LINE_CHANNEL_ACCESS_TOKEN
LINE_USER_ID
LINE_ALERT_ENABLED
LINE_ALERT_INTERVAL_SECONDS
LINE_ALERT_COOLDOWN_MINUTES
```

ค่าที่รองรับในสคริปต์ติดตั้ง (`setup_pi_kiosk.sh`):

```bash
APP_DIR            # โฟลเดอร์โปรเจกต์ (default: /opt/durian-dashboard)
SERVICE_NAME       # ชื่อ systemd service
PI_USER            # Linux user สำหรับ desktop autostart
SCREEN_TIMEOUT     # เวลาพักหน้าจอ (วินาที, default: 3600)
USE_TOUCHSCREEN    # y = ติดตั้ง backlight service, n = ข้าม (default: n)
SCREEN_BRIGHTNESS  # ความสว่างจอ 0-255 (default: 128) ใช้เมื่อ USE_TOUCHSCREEN=y
DASHBOARD_URL      # URL ของ dashboard สำหรับ kiosk browser
```

### Data retention policy (local cache)

- ค่าแนะนำสำหรับหน้างานที่มีข้อมูลหลักอยู่บน server: `RETAIN_DAYS=90`
- ระบบจะลบข้อมูลที่เก่ากว่า `RETAIN_DAYS` อัตโนมัติระหว่างรัน (ตรวจทุก ~1 ชั่วโมง)
- สามารถปรับในไฟล์ `.env` ได้ตามต้องการ

## API

- `GET /api/latest`
- `GET /api/history?field=vpd_kpa&hours=24`
- `GET /api/scatter?pair=air&hours=24`
- `GET /api/weather?province=...&amphoe=...&tambon=...&duration_days=7`
- `GET /api/farm-summary?province=...&amphoe=...&tambon=...&duration_days=7`
- `POST /api/line/test-alert?province=...&amphoe=...&tambon=...`
- `WS /ws`

## วิธีทดสอบ Endpoint

ตัวอย่างนี้ใช้ host local: `http://127.0.0.1:8080`

### 1) ทดสอบด้วย Browser (เฉพาะ GET)

- Latest:
  - `http://127.0.0.1:8080/api/latest`
- Weather (TMD):
  - `http://127.0.0.1:8080/api/weather?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด&duration_days=7`
- Farm summary:
  - `http://127.0.0.1:8080/api/farm-summary?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด&duration_days=7`

หมายเหตุ: `POST /api/line/test-alert` เปิดลิงก์ตรงใน browser ไม่ได้ ต้องยิงแบบ POST ด้วยคำสั่งหรือเครื่องมือ API

### 2) ทดสอบด้วย PowerShell

```powershell
# GET /api/weather
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/weather?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด&duration_days=7" | ConvertTo-Json -Depth 8

# GET /api/farm-summary
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/farm-summary?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด&duration_days=7" | ConvertTo-Json -Depth 8

# POST /api/line/test-alert
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/line/test-alert?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด" | ConvertTo-Json -Depth 8
```

### 3) ทดสอบด้วย curl

```bash
# GET /api/weather
curl "http://127.0.0.1:8080/api/weather?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด&duration_days=7"

# GET /api/farm-summary
curl "http://127.0.0.1:8080/api/farm-summary?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด&duration_days=7"

# POST /api/line/test-alert
curl -X POST "http://127.0.0.1:8080/api/line/test-alert?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด"
```

### 4) ตรวจสอบกรณีพื้นที่สะกดไม่ตรง (fallback)

ระบบจะพยายามผ่อนเงื่อนไขพื้นที่ให้อัตโนมัติ ดังนั้นสามารถทดสอบได้ด้วยตัวอย่างนี้:

```bash
curl "http://127.0.0.1:8080/api/weather?province=จันทบุรี&amphoe=อำเภอที่ไม่มี&tambon=ตำบลที่ไม่มี&duration_days=7"
```

คาดหวังผล: ยังได้ข้อมูลพยากรณ์ (fallback ไป query ระดับจังหวัด)

## ตัวอย่าง Response (แบบย่อ)

### `GET /api/weather`

```json
{
  "source": "tmd",
  "location": {
    "province": "จันทบุรี",
    "amphoe": "นายายอาม",
    "tambon": "วังโตนด",
    "lat": 12.703082,
    "lon": 101.929916,
    "region": "E",
    "areatype": "tambon"
  },
  "days": [
    {
      "time": "2026-05-31T00:00:00+07:00",
      "tc_min": 25.04,
      "tc_max": 31.73,
      "rh": 81.76,
      "rain": 0.0,
      "ws10m": 8.07,
      "cond": 4
    }
  ]
}
```

### `GET /api/farm-summary`

```json
{
  "place": {
    "province": "จันทบุรี",
    "amphoe": "นายายอาม",
    "tambon": "วังโตนด"
  },
  "weather": {
    "source": "tmd",
    "location": {
      "province": "จันทบุรี",
      "amphoe": "นายายอาม",
      "tambon": "วังโตนด"
    },
    "days": [
      {
        "time": "2026-05-31T00:00:00+07:00",
        "tc_min": 25.04,
        "tc_max": 31.73,
        "rh": 81.76,
        "rain": 0.0,
        "ws10m": 8.07,
        "cond": 4
      }
    ]
  },
  "summary": {
    "risk_level": "normal",
    "headline": "สภาพรวมอยู่ในเกณฑ์ปกติ",
    "reasons": ["ค่าจากสถานีและพยากรณ์ยังไม่พบความเสี่ยงเด่น"],
    "actions": ["รักษาแผนดูแลปัจจุบันและติดตามข้อมูลต่อเนื่อง"],
    "snapshot": {
      "vpd_kpa": 0.15,
      "soil_humi": 40.6,
      "forecast_today": {
        "tc_max": 31.73,
        "tc_min": 25.04,
        "rh": 81.76,
        "rain": 0.0,
        "cond_text": "เมฆครึ้ม"
      },
      "forecast_3d": {
        "max_temp": 31.73,
        "rain_sum": 38.5
      }
    }
  }
}
```

## Troubleshooting

## ตารางสรุปเกณฑ์ (VPD และฝนต่อเนื่อง)

ตารางนี้สรุปเงื่อนไขที่ระบบใช้สร้างข้อความในส่วน **สรุปข้อมูลสวน + พยากรณ์**

| ปัจจัย | ช่วง/เงื่อนไข | คะแนนความเสี่ยงที่เพิ่ม | ข้อความเหตุผลที่แสดง | ข้อความแนะนำที่แสดง |
|---|---|---:|---|---|
| VPD | `> 1.8` | +2 | `VPD ในสวนอยู่ในระดับวิกฤต` | `เพิ่มความชื้นในทรงพุ่มและตรวจรอบน้ำ` |
| VPD | `> 1.4` ถึง `<= 1.8` | +1 | `VPD ในสวนค่อนข้างสูง` | `เฝ้าระวังการคายน้ำของต้น` |
| ฝนสะสมพยากรณ์ 3 วัน (rain_3d) | `>= 60 mm` | +2 | `พยากรณ์ฝนสะสม 3 วันสูง` | `ระบายน้ำโคนต้นและลดการให้น้ำ` |
| ฝนสะสมพยากรณ์ 3 วัน (rain_3d) | `>= 25 mm` และ `< 60 mm` | +1 | `พยากรณ์มีฝนต่อเนื่อง` | `ตรวจการระบายน้ำและโรคจากความชื้น` |

เกณฑ์สรุประดับความเสี่ยงรวมจากคะแนนทั้งหมด:

| คะแนนรวม (risk_score) | risk_level | headline |
|---:|---|---|
| `>= 4` | `danger` | `ความเสี่ยงสูง ควรจัดการทันที` |
| `>= 2` และ `< 4` | `warning` | `มีความเสี่ยงปานกลาง ควรเฝ้าระวัง` |
| `< 2` | `normal` | `สภาพรวมอยู่ในเกณฑ์ปกติ` |

### Quick Troubleshooting (1 หน้า)

#### Windows (PowerShell)

| อาการ | สาเหตุที่เป็นไปได้ | วิธีแก้ | คำสั่งตรวจสอบ |
|---|---|---|---|
| `TMD access token is not configured` | ไม่ได้ตั้งค่า `TMD_ACCESS_TOKEN` ใน `.env` | ใส่ token แล้ว restart service | `Select-String "TMD_ACCESS_TOKEN" .env` |
| `TMD API error: 401` | Token หมดอายุหรือไม่ถูกต้อง | ออก token ใหม่จาก TMD แล้วอัปเดต `.env` จากนั้น restart | `Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/weather?province=จันทบุรี"` |
| `province is required` | ไม่ส่ง `province` ใน query และไม่ได้ตั้ง `TMD_PROVINCE` | ใส่ `province` ใน URL หรือกำหนด `TMD_PROVINCE` ใน `.env` | `Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/weather?province=จันทบุรี"` |
| โหลดพยากรณ์ไม่สำเร็จเมื่อกรอกอำเภอ/ตำบล | สะกดชื่อพื้นที่ไม่ตรงฐานข้อมูล TMD | เริ่มทดสอบจากระดับจังหวัดก่อน แล้วค่อยเพิ่มอำเภอ/ตำบล | `Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/weather?province=จันทบุรี&amphoe=อำเภอที่ไม่มี&tambon=ตำบลที่ไม่มี"` |
| `LINE notifier is not configured` | ขาด `LINE_CHANNEL_ACCESS_TOKEN` หรือ `LINE_USER_ID` | ใส่ค่าให้ครบใน `.env` แล้ว restart | `Select-String "LINE_CHANNEL_ACCESS_TOKEN|LINE_USER_ID" .env` |
| ยิง `/api/line/test-alert` แล้วไม่เข้าไลน์ | Token/ผู้รับไม่ถูกต้อง หรือบอทส่งหา user ไม่ได้ | ตรวจ token ใหม่, ตรวจ user id, ทดสอบ POST ซ้ำ | `Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/line/test-alert?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด"` |
| หน้าเว็บไม่อัปเดตหลังแก้โค้ด | Service ยังรัน process เก่า | restart service หรือรันใหม่ | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --env-file .env` |

#### Raspberry Pi (Linux)

| อาการ | สาเหตุที่เป็นไปได้ | วิธีแก้ | คำสั่งตรวจสอบ |
|---|---|---|---|
| `TMD access token is not configured` | ไม่ได้ตั้งค่า `TMD_ACCESS_TOKEN` ใน `.env` | ใส่ token แล้ว restart service | `grep TMD_ACCESS_TOKEN .env` |
| `TMD API error: 401` | Token หมดอายุหรือไม่ถูกต้อง | ออก token ใหม่จาก TMD แล้วอัปเดต `.env` จากนั้น restart | `curl "http://127.0.0.1:8080/api/weather?province=จันทบุรี"` |
| `province is required` | ไม่ส่ง `province` ใน query และไม่ได้ตั้ง `TMD_PROVINCE` | ใส่ `province` ใน URL หรือกำหนด `TMD_PROVINCE` ใน `.env` | `curl "http://127.0.0.1:8080/api/weather?province=จันทบุรี"` |
| โหลดพยากรณ์ไม่สำเร็จเมื่อกรอกอำเภอ/ตำบล | สะกดชื่อพื้นที่ไม่ตรงฐานข้อมูล TMD | เริ่มทดสอบจากระดับจังหวัดก่อน แล้วค่อยเพิ่มอำเภอ/ตำบล | `curl "http://127.0.0.1:8080/api/weather?province=จันทบุรี&amphoe=อำเภอที่ไม่มี&tambon=ตำบลที่ไม่มี"` |
| `LINE notifier is not configured` | ขาด `LINE_CHANNEL_ACCESS_TOKEN` หรือ `LINE_USER_ID` | ใส่ค่าให้ครบใน `.env` แล้ว restart | `grep -E "LINE_CHANNEL_ACCESS_TOKEN|LINE_USER_ID" .env` |
| ยิง `/api/line/test-alert` แล้วไม่เข้าไลน์ | Token/ผู้รับไม่ถูกต้อง หรือบอทส่งหา user ไม่ได้ | ตรวจ token ใหม่, ตรวจ user id, ทดสอบ POST ซ้ำ | `curl -X POST "http://127.0.0.1:8080/api/line/test-alert?province=จันทบุรี&amphoe=นายายอาม&tambon=วังโตนด"` |
| หน้าเว็บไม่อัปเดตหลังแก้โค้ด | Service ยังรัน process เก่า | restart service หรือรันใหม่ | `sudo systemctl restart durian-dashboard` และ `sudo journalctl -u durian-dashboard -n 50 --no-pager` |

- อาการ: `TMD access token is not configured`
  สาเหตุ: ยังไม่ได้ตั้งค่า `TMD_ACCESS_TOKEN` ในไฟล์ `.env`
  วิธีแก้: ใส่ token ใหม่ แล้ว restart service

- อาการ: `TMD API error: 401` หรือดึงข้อมูลไม่ได้หลังใช้งานไปสักพัก
  สาเหตุ: token หมดอายุหรือไม่ถูกต้อง
  วิธีแก้: ออก token ใหม่จาก TMD แล้วอัปเดต `.env` จากนั้น restart service

- อาการ: `province is required`
  สาเหตุ: ไม่ได้ส่งพารามิเตอร์จังหวัดและไม่ได้ตั้ง `TMD_PROVINCE` ใน `.env`
  วิธีแก้: ระบุ `province` ใน query หรือกำหนดค่า `TMD_PROVINCE`

- อาการ: `place not found in TMD`
  สาเหตุ: ชื่อพื้นที่สะกดไม่ตรงฐานข้อมูล TMD และแม้ fallback แล้วก็ยังไม่พบ
  วิธีแก้: ตรวจสะกดชื่อจังหวัด/อำเภอ/ตำบลใหม่ (แนะนำเริ่มจากจังหวัดก่อน)

- อาการ: `LINE notifier is not configured`
  สาเหตุ: ยังไม่ได้ตั้ง `LINE_CHANNEL_ACCESS_TOKEN` หรือ `LINE_USER_ID`
  วิธีแก้: ใส่ค่าให้ครบใน `.env` แล้ว restart service

## Payload example

```json
{
  "time": "19/05/2026 09:30:00",
  "node": "node01",
  "zone": "zone01",
  "env": {
    "air_temp": 30.5,
    "air_humi": 72.0,
    "lux": 54000,
    "wind_speed_avg5m": 1.2,
    "wind_dir_deg": 135,
    "wind_dir_th": "SE"
  },
  "npk": {
    "soil_temp": 28.4,
    "soil_humi": 65.0,
    "ec": 1.25,
    "ph": 6.4,
    "n": 45,
    "p": 18,
    "k": 120
  }
}
```


## Next steps (Post-install verification)

1. Reboot the device:
  ```bash
  sudo reboot
  ```
2. After boot, verify the service is running:
  ```bash
  sudo systemctl status durian-dashboard --no-pager
  ```
3. Verify the web port is open:
  ```bash
  sudo ss -tulpn | grep 8080
  ```

### Screen timeout (xset/DPMS) usage

ใช้กับ Raspberry Pi ที่รัน X11/Chromium kiosk เพื่อกำหนดเวลาพักหน้าจอหรือดับหน้าจอ

คำสั่งที่ต้องใช้และความหมาย:

- `export DISPLAY=:0`
  - ระบุ X display หลักของเครื่อง (จอที่ kiosk ใช้งานอยู่)
- `export XAUTHORITY=/home/pi/.Xauthority`
  - ระบุไฟล์สิทธิ์เข้าถึง X session ของ user `pi` (ช่วยแก้ปัญหา `unable to open display`)
- `xset s <sec> 0`
  - ตั้ง idle timeout ของ screen saver เป็น `<sec>` วินาที
- `xset +dpms`
  - เปิดการทำงาน DPMS (โหมดประหยัดพลังงานของจอ)
- `xset dpms <standby> <suspend> <off>`
  - ตั้งเวลา DPMS เป็นวินาที
  - หากตั้งค่าเท่ากันทั้ง 3 ค่า เช่น `900 900 900` จะทำให้จอเข้าสถานะพัก/ดับที่เวลาใกล้เคียงกัน

สูตรคำนวณเวลาสำหรับตั้งค่าดับหน้าจอ:

- `T_sec = (ชั่วโมง x 3600) + (นาที x 60) + วินาที`

ตัวอย่างการคำนวณ:

- 5 นาที: `5 x 60 = 300` วินาที
- 15 นาที: `15 x 60 = 900` วินาที
- 1 ชั่วโมง: `1 x 3600 = 3600` วินาที

ตารางแปลงเวลาแบบเร็ว:

| นาที | วินาที (ใช้กับ xset) |
|---:|---:|
| 1  | 60   |
| 3  | 180  |
| 5  | 300  |
| 10 | 600  |
| 15 | 900  |
| 30 | 1800 |
| 60 | 3600 |

### Optional: Quick screen timeout test (20 seconds)

```bash
export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority
xset s 20 0
xset +dpms
xset dpms 20 20 20
```

### Example: set screen timeout to 15 minutes

```bash
export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority
xset s 900 0
xset +dpms
xset dpms 900 900 900
```

### Restore 1-hour screen timeout

```bash
export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority
xset s 3600 0
xset +dpms
xset dpms 3600 3600 3600
```

### Troubleshooting: SQLite error `database disk image is malformed`

หากดู log แล้วพบข้อความนี้ แปลว่าไฟล์ฐานข้อมูล SQLite เสียหาย (ไม่เกี่ยวกับ Wi-Fi โดยตรง)

ตรวจ log:

```bash
sudo journalctl -u durian-dashboard -n 200 --no-pager
```

ระบบเวอร์ชันใหม่จะพยายาม backup และสร้างฐานข้อมูลใหม่ให้อัตโนมัติเมื่อเจอ error นี้

หากยังไม่หาย ให้กู้คืนแบบ manual:

```bash
cd /opt/durian-dashboard
sudo systemctl stop durian-dashboard
mv data/durian_dashboard.db data/durian_dashboard.db.corrupt.$(date +%Y%m%d_%H%M%S)
sudo systemctl start durian-dashboard
```

หมายเหตุ:
- หลังสร้าง DB ใหม่ กราฟย้อนหลังจะเริ่มเก็บข้อมูลใหม่ตั้งแต่เวลาที่ service กลับมารัน
- ข้อมูลไฟล์เก่าจะยังอยู่ในชื่อ `.corrupt.*` สำหรับเก็บไว้ตรวจสอบภายหลัง

## Notes for Pi3

- If upstream server stores long-term data, keep local cache at `RETAIN_DAYS=90`.
- Use one Uvicorn worker.
- Keep MQTT publish interval at 1-5 minutes.
