from __future__ import annotations

import datetime as dt
import math
from typing import Any


def parse_sensor_time(raw: Any) -> int:
    if isinstance(raw, str):
        try:
            parsed = dt.datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
            return int(parsed.timestamp() * 1000)
        except ValueError:
            pass
    return int(dt.datetime.now().timestamp() * 1000)


def saturation_vapor_pressure_kpa(air_temp_c: float) -> float:
    return 0.6108 * math.exp((17.27 * air_temp_c) / (air_temp_c + 237.3))


def calc_vpd(air_temp_c: float, air_humi_pct: float) -> tuple[float, float, float]:
    es_kpa = saturation_vapor_pressure_kpa(air_temp_c)
    ea_kpa = es_kpa * (air_humi_pct / 100.0)
    return es_kpa, ea_kpa, es_kpa - ea_kpa


def calc_solar(lux: float) -> tuple[float, float]:
    solar_wm2 = lux / 120.0
    solar_mj_m2_h = solar_wm2 * 3600.0 / 1_000_000.0
    return solar_wm2, solar_mj_m2_h


def calc_eto_day_est(
    air_temp_c: float,
    vpd_kpa: float,
    wind_speed_ms: float,
    solar_mj_m2_h: float,
) -> tuple[float, float]:
    albedo = 0.23
    gamma = 0.0665

    rn = (1.0 - albedo) * solar_mj_m2_h
    delta = (4098.0 * saturation_vapor_pressure_kpa(air_temp_c)) / ((air_temp_c + 237.3) ** 2)

    u2 = max(0.0, wind_speed_ms)
    numerator = (0.408 * delta * rn) + (gamma * (900.0 / (air_temp_c + 273.0)) * u2 * vpd_kpa)
    denominator = delta + gamma * (1.0 + 0.34 * u2)

    eto_h = numerator / denominator if denominator else 0.0
    return eto_h, eto_h * 24.0


def get_vpd_status(vpd: float) -> dict[str, str]:
    if vpd < 0.40:
        return {
            "level": "too_low",
            "text": "VPD ต่ำเกินไป: อากาศชื้นจัด เสี่ยงโรครา",
            "action": "งดให้น้ำ/งดพ่นหมอก และเพิ่มการระบายอากาศ",
            "color": "blue",
        }
    if vpd <= 0.80:
        return {
            "level": "low_stress",
            "text": "VPD ค่อนข้างต่ำ: เฝ้าระวังความชื้นสูง",
            "action": "ระบบทำงานปกติ ไม่ต้องเปิดพ่นหมอกเพิ่ม",
            "color": "green",
        }
    if vpd <= 1.40:
        return {
            "level": "optimal",
            "text": "VPD เหมาะสมที่สุดสำหรับทุเรียน",
            "action": "รักษาระดับนี้ไว้",
            "color": "teal",
        }
    if vpd <= 1.80:
        return {
            "level": "high_stress",
            "text": "VPD เริ่มวิกฤต: อากาศแห้งและร้อน",
            "action": "ควรเปิดระบบพ่นหมอกเพื่อเพิ่มความชื้น",
            "color": "amber",
        }
    return {
        "level": "danger",
        "text": "VPD วิกฤตรุนแรง: เสี่ยงใบไหม้และผลร่วง",
        "action": "เปิดระบบพ่นหมอกเต็มกำลัง และเพิ่มรอบให้น้ำโคนต้น",
        "color": "red",
    }


def get_ph_status(ph: float) -> dict[str, str]:
    if ph < 5.0:
        return {
            "level": "strong_acid",
            "text": "ดินเป็นกรดรุนแรง",
            "action": "ตรวจสอบซ้ำและพิจารณาปรับปรุงดิน",
            "color": "red",
        }
    if ph <= 5.5:
        return {
            "level": "acid",
            "text": "ดินเป็นกรด",
            "action": "เฝ้าระวังและตรวจร่วมกับ EC/NPK",
            "color": "orange",
        }
    if ph <= 6.5:
        return {
            "level": "suitable",
            "text": "pH อยู่ในช่วงเหมาะสม",
            "action": "รักษาสภาพดินและติดตามต่อเนื่อง",
            "color": "teal",
        }
    if ph <= 7.5:
        return {
            "level": "near_neutral",
            "text": "ดินใกล้กลาง",
            "action": "ติดตามร่วมกับ EC และธาตุอาหาร",
            "color": "amber",
        }
    return {
        "level": "alkaline",
        "text": "ดินเป็นด่าง",
        "action": "ตรวจสอบสภาพดินและความพร้อมใช้ของธาตุอาหาร",
        "color": "blue",
    }


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    env = payload.get("env", {}) or {}
    npk = payload.get("npk", {}) or {}

    air_temp = env.get("air_temp", env.get("Air_temp"))
    air_humi = env.get("air_humi", env.get("Air_humi"))
    soil_temp = npk.get("soil_temp", npk.get("Soil_temp"))
    soil_humi = npk.get("soil_humi", npk.get("Soil_humi"))

    record: dict[str, Any] = {
        "timestamp_ms": parse_sensor_time(payload.get("time")),
        "node": payload.get("node", "unknown_node"),
        "zone": payload.get("zone", "unknown_zone"),
        "air_temp": air_temp,
        "air_humi": air_humi,
        "lux": env.get("lux"),
        "wind_speed_avg5m": env.get("wind_speed_avg5m"),
        "wind_dir_deg": env.get("wind_dir_deg"),
        "wind_dir_th": env.get("wind_dir_th"),
        "soil_temp": soil_temp,
        "soil_humi": soil_humi,
        "ec": npk.get("ec"),
        "ph": npk.get("ph"),
        "n": npk.get("n"),
        "p": npk.get("p"),
        "k": npk.get("k"),
    }

    if isinstance(air_temp, (int, float)) and isinstance(air_humi, (int, float)):
        es_kpa, ea_kpa, vpd_kpa = calc_vpd(float(air_temp), float(air_humi))
        record["es_kpa"] = es_kpa
        record["ea_kpa"] = ea_kpa
        record["vpd_kpa"] = vpd_kpa
        record.update({
            "vpd_status": get_vpd_status(vpd_kpa)["level"],
            "vpd_message": get_vpd_status(vpd_kpa)["text"],
            "vpd_action": get_vpd_status(vpd_kpa)["action"],
        })

    if isinstance(record.get("lux"), (int, float)):
        solar_wm2, solar_mj_m2_h = calc_solar(float(record["lux"]))
        record["solar_wm2_est"] = solar_wm2
        record["solar_mj_m2_h_est"] = solar_mj_m2_h

    if (
        isinstance(record.get("air_temp"), (int, float))
        and isinstance(record.get("vpd_kpa"), (int, float))
        and isinstance(record.get("solar_mj_m2_h_est"), (int, float))
    ):
        wind = record.get("wind_speed_avg5m") if isinstance(record.get("wind_speed_avg5m"), (int, float)) else 0.0
        eto_h, eto_day = calc_eto_day_est(
            float(record["air_temp"]),
            float(record["vpd_kpa"]),
            float(wind),
            float(record["solar_mj_m2_h_est"]),
        )
        record["eto_mm_h_est"] = eto_h
        record["eto_mm_day_est"] = eto_day

    if isinstance(record.get("ph"), (int, float)):
        ph_status = get_ph_status(float(record["ph"]))
        record["ph_status"] = ph_status["level"]
        record["ph_message"] = ph_status["text"]
        record["ph_action"] = ph_status["action"]

    return record
