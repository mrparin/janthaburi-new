from __future__ import annotations

from typing import Any


COND_LABELS = {
    1: "ท้องฟ้าแจ่มใส",
    2: "มีเมฆบางส่วน",
    3: "เมฆมาก",
    4: "เมฆครึ้ม",
    5: "ฝนเล็กน้อย",
    6: "ฝนปานกลาง",
    7: "ฝนหนัก",
    8: "ฝนฟ้าคะนอง",
    9: "อากาศหนาวจัด",
}


def _safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_rain(day: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    rain_raw = _safe_float(day.get("rain"))
    rain_mm = _safe_float(day.get("rain_mm"))
    rain_pct = _safe_float(day.get("rain_pct"))

    # If backend receives only one "rain" value, keep backward-compatible interpretation.
    if rain_pct is None and rain_raw is not None and 0.0 <= rain_raw <= 100.0:
        rain_pct = rain_raw
    if rain_mm is None and rain_raw is not None and rain_raw > 100.0:
        rain_mm = rain_raw

    return rain_raw, rain_mm, rain_pct


def build_farm_summary(sensor_latest: dict[str, Any] | None, weather: dict[str, Any] | None) -> dict[str, Any]:
    days = weather.get("days", []) if isinstance(weather, dict) else []
    today = days[0] if days else {}
    next_3_days = days[:3]

    reasons: list[str] = []
    actions: list[str] = []
    risk_score = 0

    vpd = _safe_float((sensor_latest or {}).get("vpd_kpa"))
    soil_humi = _safe_float((sensor_latest or {}).get("soil_humi"))
    air_temp = _safe_float((sensor_latest or {}).get("air_temp"))
    air_humi = _safe_float((sensor_latest or {}).get("air_humi"))

    max_temp_3d = max((_safe_float(x.get("tc_max")) for x in next_3_days), default=None)
    rain_triplets = [_normalize_rain(x) for x in next_3_days]
    rain_mm_values = [mm for _, mm, _ in rain_triplets if mm is not None]
    rain_pct_values = [pct for _, _, pct in rain_triplets if pct is not None]
    rain_3d_mm = sum(rain_mm_values) if rain_mm_values else None
    rain_3d_pct_max = max(rain_pct_values) if rain_pct_values else None

    today_rain_raw, today_rain_mm, today_rain_pct = _normalize_rain(today)
    today_cond = today.get("cond")

    if vpd is not None and vpd > 1.8:
        risk_score += 2
        reasons.append("VPD ในสวนอยู่ในระดับวิกฤต")
        actions.append("เพิ่มความชื้นในทรงพุ่มและตรวจรอบน้ำ")
    elif vpd is not None and vpd > 1.4:
        risk_score += 1
        reasons.append("VPD ในสวนค่อนข้างสูง")
        actions.append("เฝ้าระวังการคายน้ำของต้น")

    if max_temp_3d is not None and max_temp_3d >= 35:
        risk_score += 2
        reasons.append("พยากรณ์อุณหภูมิสูงสุด 3 วันเกิน 35°C")
        actions.append("เตรียมแผนให้น้ำช่วงเช้าตรู่และเย็น")
    elif max_temp_3d is not None and max_temp_3d >= 33:
        risk_score += 1
        reasons.append("พยากรณ์อุณหภูมิสูงสุด 3 วันค่อนข้างสูง")
        actions.append("ติดตามอุณหภูมิทรงพุ่มอย่างใกล้ชิด")

    if rain_3d_mm is not None:
        if rain_3d_mm >= 60:
            risk_score += 2
            reasons.append("พยากรณ์ฝนสะสม 3 วันสูง (มม.)")
            actions.append("ระบายน้ำโคนต้นและลดการให้น้ำ")
        elif rain_3d_mm >= 25:
            risk_score += 1
            reasons.append("พยากรณ์มีฝนต่อเนื่อง (มม.)")
            actions.append("ตรวจการระบายน้ำและโรคจากความชื้น")
    elif rain_3d_pct_max is not None:
        if rain_3d_pct_max >= 80:
            risk_score += 2
            reasons.append("โอกาสเกิดฝน 3 วันอยู่ในระดับสูง (%)")
            actions.append("เตรียมทางระบายน้ำและลดการให้น้ำล่วงหน้า")
        elif rain_3d_pct_max >= 60:
            risk_score += 1
            reasons.append("โอกาสเกิดฝน 3 วันอยู่ในระดับเฝ้าระวัง (%)")
            actions.append("ติดตามเรดาร์ฝนและวางแผนการให้น้ำ")

    if soil_humi is not None and soil_humi < 35:
        risk_score += 1
        reasons.append("ความชื้นดินปัจจุบันต่ำ")
        actions.append("ตรวจระบบน้ำหยดและเพิ่มรอบน้ำอย่างเหมาะสม")
    elif soil_humi is not None and soil_humi > 80:
        risk_score += 1
        reasons.append("ความชื้นดินปัจจุบันสูงมาก")
        actions.append("เฝ้าระวังน้ำขังและรากขาดอากาศ")

    if risk_score >= 4:
        level = "danger"
        headline = "ความเสี่ยงสูง ควรจัดการทันที"
    elif risk_score >= 2:
        level = "warning"
        headline = "มีความเสี่ยงปานกลาง ควรเฝ้าระวัง"
    else:
        level = "normal"
        headline = "สภาพรวมอยู่ในเกณฑ์ปกติ"

    if not reasons:
        reasons.append("ค่าจากสถานีและพยากรณ์ยังไม่พบความเสี่ยงเด่น")
    if not actions:
        actions.append("รักษาแผนดูแลปัจจุบันและติดตามข้อมูลต่อเนื่อง")

    return {
        "risk_level": level,
        "headline": headline,
        "reasons": reasons,
        "actions": actions,
        "snapshot": {
            "air_temp": air_temp,
            "air_humi": air_humi,
            "vpd_kpa": vpd,
            "soil_humi": soil_humi,
            "forecast_today": {
                "tc_min": _safe_float(today.get("tc_min")),
                "tc_max": _safe_float(today.get("tc_max")),
                "rh": _safe_float(today.get("rh")),
                "rain": today_rain_raw,
                "rain_mm": today_rain_mm,
                "rain_pct": today_rain_pct,
                "cond": today_cond,
                "cond_text": COND_LABELS.get(today_cond, "ไม่ระบุ"),
            },
            "forecast_3d": {
                "max_temp": max_temp_3d,
                "rain_sum_mm": rain_3d_mm,
                "rain_max_pct": rain_3d_pct_max,
            },
        },
    }


def format_line_alert(location_name: str, summary: dict[str, Any]) -> str:
    s = summary.get("snapshot", {}) if isinstance(summary, dict) else {}
    f_today = s.get("forecast_today", {}) if isinstance(s.get("forecast_today"), dict) else {}
    rain_mm = f_today.get("rain_mm")
    rain_pct = f_today.get("rain_pct")

    if rain_mm is None and isinstance(f_today.get("rain"), (int, float)) and float(f_today.get("rain")) > 100.0:
        rain_mm = f_today.get("rain")
    if rain_pct is None and isinstance(f_today.get("rain"), (int, float)) and 0.0 <= float(f_today.get("rain")) <= 100.0:
        rain_pct = f_today.get("rain")

    rain_mm_text = f"{rain_mm:.1f}" if isinstance(rain_mm, (int, float)) else "-"
    rain_pct_text = f"{rain_pct:.0f}" if isinstance(rain_pct, (int, float)) else "-"

    risk_level = str(summary.get("risk_level", "-")).lower()
    if risk_level == "danger":
        risk_icon = "🚨"
    elif risk_level == "warning":
        risk_icon = "⚠️"
    else:
        risk_icon = "✅"

    lines = [
        "🌳 [ระบบเตือนภัยสภาพอากาศสวนทุเรียน] 🌳",
        f"📍 พื้นที่: {location_name}",
        f"{risk_icon} ระดับความเสี่ยง: {summary.get('risk_level', '-')}",
        f"📝 สรุป: {summary.get('headline', '-')}",
        "",
        "📡 สถานีในสวน:",
        f"🌡️ Air Temp: {s.get('air_temp', '-')}",
        f"💧 Air Humi: {s.get('air_humi', '-')}",
        f"🌀 VPD: {s.get('vpd_kpa', '-')}",
        f"🌱 Soil Humi: {s.get('soil_humi', '-')}",
        "",
        "🌤️ พยากรณ์วันนี้ (TMD):",
        f"🌡️ Tmax/Tmin: {f_today.get('tc_max', '-')}/{f_today.get('tc_min', '-')} C",
        f"💧 RH: {f_today.get('rh', '-')}%",
        f"🌧️ Rain: {rain_mm_text} mm | {rain_pct_text}%",
        f"☁️ Condition: {f_today.get('cond_text', '-')}",
        "",
        "🛠️ ข้อแนะนำ:",
    ]

    for action in summary.get("actions", [])[:3]:
        lines.append(f"• {action}")

    message = "\n".join(lines)
    return message[:4900]
