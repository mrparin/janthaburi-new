from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx


THAI_PROVINCES_FALLBACK = [
    "กรุงเทพมหานคร",
    "กระบี่",
    "กาญจนบุรี",
    "กาฬสินธุ์",
    "กำแพงเพชร",
    "ขอนแก่น",
    "จันทบุรี",
    "ฉะเชิงเทรา",
    "ชลบุรี",
    "ชัยนาท",
    "ชัยภูมิ",
    "ชุมพร",
    "เชียงราย",
    "เชียงใหม่",
    "ตรัง",
    "ตราด",
    "ตาก",
    "นครนายก",
    "นครปฐม",
    "นครพนม",
    "นครราชสีมา",
    "นครศรีธรรมราช",
    "นครสวรรค์",
    "นนทบุรี",
    "นราธิวาส",
    "น่าน",
    "บึงกาฬ",
    "บุรีรัมย์",
    "ปทุมธานี",
    "ประจวบคีรีขันธ์",
    "ปราจีนบุรี",
    "ปัตตานี",
    "พระนครศรีอยุธยา",
    "พะเยา",
    "พังงา",
    "พัทลุง",
    "พิจิตร",
    "พิษณุโลก",
    "เพชรบุรี",
    "เพชรบูรณ์",
    "แพร่",
    "ภูเก็ต",
    "มหาสารคาม",
    "มุกดาหาร",
    "แม่ฮ่องสอน",
    "ยโสธร",
    "ยะลา",
    "ร้อยเอ็ด",
    "ระนอง",
    "ระยอง",
    "ราชบุรี",
    "ลพบุรี",
    "ลำปาง",
    "ลำพูน",
    "เลย",
    "ศรีสะเกษ",
    "สกลนคร",
    "สงขลา",
    "สตูล",
    "สมุทรปราการ",
    "สมุทรสงคราม",
    "สมุทรสาคร",
    "สระแก้ว",
    "สระบุรี",
    "สิงห์บุรี",
    "สุโขทัย",
    "สุพรรณบุรี",
    "สุราษฎร์ธานี",
    "สุรินทร์",
    "หนองคาย",
    "หนองบัวลำภู",
    "อ่างทอง",
    "อำนาจเจริญ",
    "อุดรธานี",
    "อุตรดิตถ์",
    "อุทัยธานี",
    "อุบลราชธานี",
]


class ThaiLocationCatalog:
    """Lazy-loaded Thai province/amphoe/tambon catalog for cascading selectors."""

    PROVINCES_URL = "https://raw.githubusercontent.com/kongvut/thai-province-data/master/api_province.json"
    AMPHOES_URL = "https://raw.githubusercontent.com/kongvut/thai-province-data/master/api_amphure.json"
    TAMBONS_URL = "https://raw.githubusercontent.com/kongvut/thai-province-data/master/api_tambon.json"
    LOCAL_GEO_PATH = Path(__file__).resolve().parents[1] / "data" / "thai_geo.json"

    def __init__(self, timeout: int = 20, fallback_provinces: list[str] | None = None) -> None:
        self.timeout = timeout
        merged_fallback = [*THAI_PROVINCES_FALLBACK, *(fallback_provinces or [])]
        self._fallback_provinces = [x.strip() for x in merged_fallback if x and x.strip()]

        self._loaded = False
        self._lock = asyncio.Lock()

        self._provinces: list[str] = []
        self._province_name_to_id: dict[str, int] = {}
        self._amphoes_by_province_id: dict[int, list[str]] = defaultdict(list)
        self._amphoe_ids_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
        self._tambons_by_amphoe_id: dict[int, list[str]] = defaultdict(list)

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    async def _fetch_json(self, client: httpx.AsyncClient, url: str) -> list[dict[str, Any]]:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []
        return [x for x in payload if isinstance(x, dict)]

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        async with self._lock:
            if self._loaded:
                return

            # Prefer local dataset so cascading selectors work even without internet.
            if self.LOCAL_GEO_PATH.exists():
                try:
                    geo_data = json.loads(self.LOCAL_GEO_PATH.read_text(encoding="utf-8"))
                    if isinstance(geo_data, list):
                        self._build_indices_from_geo(geo_data)
                        self._loaded = True
                        return
                except Exception:
                    pass

            provinces_payload: list[dict[str, Any]] = []
            amphoes_payload: list[dict[str, Any]] = []
            tambons_payload: list[dict[str, Any]] = []

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    provinces_payload, amphoes_payload, tambons_payload = await asyncio.gather(
                        self._fetch_json(client, self.PROVINCES_URL),
                        self._fetch_json(client, self.AMPHOES_URL),
                        self._fetch_json(client, self.TAMBONS_URL),
                    )
            except Exception:
                provinces_payload = []
                amphoes_payload = []
                tambons_payload = []

            self._build_indices(provinces_payload, amphoes_payload, tambons_payload)
            self._loaded = True

    def _build_indices_from_geo(self, geo_data: list[dict[str, Any]]) -> None:
        self._provinces = []
        self._province_name_to_id = {}
        self._amphoes_by_province_id = defaultdict(list)
        self._amphoe_ids_by_key = defaultdict(list)
        self._tambons_by_amphoe_id = defaultdict(list)

        for p in geo_data:
            if not isinstance(p, dict):
                continue
            pid = self._parse_int(p.get("code"))
            province_name = self._clean_text(p.get("name_th"))
            if pid is None or province_name is None:
                continue

            self._province_name_to_id[province_name] = pid
            self._provinces.append(province_name)

            districts = p.get("districts")
            if not isinstance(districts, list):
                continue

            for d in districts:
                if not isinstance(d, dict):
                    continue
                aid = self._parse_int(d.get("code"))
                amphoe_name = self._clean_text(d.get("name_th"))
                if aid is None or amphoe_name is None:
                    continue

                self._amphoes_by_province_id[pid].append(amphoe_name)
                self._amphoe_ids_by_key[(pid, amphoe_name)].append(aid)

                subdistricts = d.get("subdistricts")
                if not isinstance(subdistricts, list):
                    continue
                for t in subdistricts:
                    if not isinstance(t, dict):
                        continue
                    tambon_name = self._clean_text(t.get("name_th"))
                    if tambon_name is None:
                        continue
                    self._tambons_by_amphoe_id[aid].append(tambon_name)

        self._provinces = sorted(set(self._provinces))
        for key, values in list(self._amphoes_by_province_id.items()):
            self._amphoes_by_province_id[key] = sorted(set(values))
        for key, values in list(self._tambons_by_amphoe_id.items()):
            self._tambons_by_amphoe_id[key] = sorted(set(values))

        if not self._provinces and self._fallback_provinces:
            self._provinces = sorted(set(self._fallback_provinces))

    def _build_indices(
        self,
        provinces_payload: list[dict[str, Any]],
        amphoes_payload: list[dict[str, Any]],
        tambons_payload: list[dict[str, Any]],
    ) -> None:
        self._provinces = []
        self._province_name_to_id = {}
        self._amphoes_by_province_id = defaultdict(list)
        self._amphoe_ids_by_key = defaultdict(list)
        self._tambons_by_amphoe_id = defaultdict(list)

        for item in provinces_payload:
            pid = self._parse_int(item.get("id"))
            name = self._clean_text(item.get("name_th"))
            if pid is None or name is None:
                continue
            self._province_name_to_id[name] = pid
            self._provinces.append(name)

        for item in amphoes_payload:
            aid = self._parse_int(item.get("id"))
            pid = self._parse_int(item.get("province_id"))
            name = self._clean_text(item.get("name_th"))
            if aid is None or pid is None or name is None:
                continue
            self._amphoes_by_province_id[pid].append(name)
            self._amphoe_ids_by_key[(pid, name)].append(aid)

        for item in tambons_payload:
            amphoe_id = self._parse_int(item.get("amphure_id"))
            name = self._clean_text(item.get("name_th"))
            if amphoe_id is None or name is None:
                continue
            self._tambons_by_amphoe_id[amphoe_id].append(name)

        self._provinces = sorted(set(self._provinces))

        for key, values in list(self._amphoes_by_province_id.items()):
            self._amphoes_by_province_id[key] = sorted(set(values))

        for key, values in list(self._tambons_by_amphoe_id.items()):
            self._tambons_by_amphoe_id[key] = sorted(set(values))

        if not self._provinces and self._fallback_provinces:
            self._provinces = sorted(set(self._fallback_provinces))

    async def list_provinces(self) -> list[str]:
        await self._ensure_loaded()
        return list(self._provinces)

    async def list_amphoes(self, province: str | None) -> list[str]:
        await self._ensure_loaded()
        if not province:
            return []
        pid = self._province_name_to_id.get(province.strip())
        if pid is None:
            return []
        return list(self._amphoes_by_province_id.get(pid, []))

    async def list_tambons(self, province: str | None, amphoe: str | None) -> list[str]:
        await self._ensure_loaded()
        if not province or not amphoe:
            return []

        pid = self._province_name_to_id.get(province.strip())
        if pid is None:
            return []

        amphoe_name = amphoe.strip()
        amphoe_ids = self._amphoe_ids_by_key.get((pid, amphoe_name), [])
        if not amphoe_ids:
            return []

        result: list[str] = []
        for amphoe_id in amphoe_ids:
            result.extend(self._tambons_by_amphoe_id.get(amphoe_id, []))

        return sorted(set(result))
