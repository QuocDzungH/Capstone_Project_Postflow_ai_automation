"""Deterministic shipping-price calculation based on the 2026 tariff workbook."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"


class PricingError(ValueError):
    """Raised when inputs cannot be priced from the configured tariff."""


@dataclass(frozen=True)
class PriceQuote:
    service: str
    route: str
    actual_weight_kg: float
    chargeable_weight_kg: float
    used_volumetric_weight: bool
    amount_vnd: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


REGIONS = _load("regions.json")
PRICING = _load("pricing.json")


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.strip().lower())
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]", "", without_marks.replace("đ", "d"))


_province_map = {_key(province): (province, zone) for zone, provinces in REGIONS.items() if zone.startswith("Vùng") for province in provinces}
_aliases = {_key(alias): canonical for alias, canonical in REGIONS["aliases"].items()}


def normalize_province(province: str) -> str:
    """Return the canonical province name, accepting configured spelling aliases."""
    if not isinstance(province, str) or not province.strip():
        raise PricingError("Tỉnh/thành không được để trống.")
    canonical = _aliases.get(_key(province), province.strip())
    match = _province_map.get(_key(canonical))
    if not match:
        raise PricingError(f"Chưa có vùng cước cho tỉnh/thành: {province!r}.")
    return match[0]


def determine_route(origin: str, destination: str, service: str) -> str:
    """Determine the tariff route from origin/destination and service code."""
    if service not in PRICING:
        raise PricingError(f"Dịch vụ không hợp lệ: {service}. Chọn một trong {', '.join(PRICING)}.")
    origin = normalize_province(origin)
    destination = normalize_province(destination)
    if origin == destination:
        return "Nội tỉnh"
    origin_zone = _province_map[_key(origin)][1]
    destination_zone = _province_map[_key(destination)][1]
    if origin_zone == destination_zone:
        return "Nội vùng"

    hanoi, hcm, danang = "Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng"
    pair = {origin, destination}
    if service.startswith("ETN"):
        if pair == {hanoi, hcm}:
            return "Hà Nội đi TP.HCM và ngược lại"
        if danang in pair and (hanoi in pair or hcm in pair):
            return "Đà Nẵng đi Hà Nội, TP.HCM và ngược lại"
        return "Liên vùng"
    return "Cận vùng" if "Vùng 3" in {origin_zone, destination_zone} else "Cách vùng"


def chargeable_weight_kg(actual_weight_kg: float, length_cm: float, width_cm: float, height_cm: float) -> tuple[float, bool]:
    """Use real weight unless at least one package side is over 50 cm. If volumetric, use max of actual vs volumetric."""
    measurements = (actual_weight_kg, length_cm, width_cm, height_cm)
    if any(not isinstance(value, (int, float)) or value <= 0 for value in measurements):
        raise PricingError("Khối lượng và ba kích thước phải là số lớn hơn 0.")

    has_large_dimension = any(side > 50 for side in (length_cm, width_cm, height_cm))

    if has_large_dimension:
        volumetric_weight = (length_cm * width_cm * height_cm) / 6000
        weight = max(actual_weight_kg, volumetric_weight)
        used_volume = True
    else:
        weight = actual_weight_kg
        used_volume = False

    return round(weight, 2), used_volume


def _route_index(service: str, route: str) -> int:
    etn_routes = ["Nội tỉnh", "Nội vùng", "Đà Nẵng đi Hà Nội, TP.HCM và ngược lại", "Hà Nội đi TP.HCM và ngược lại", "Liên vùng"]
    if service == "CTN001":
        routes = ["Nội tỉnh", "Nội vùng", "Cận vùng", "Cách vùng"]
    else:
        routes = etn_routes
    try:
        return routes.index(route)
    except ValueError as error:
        raise PricingError(f"Tuyến {route!r} không hợp lệ với dịch vụ {service}.") from error


def _base_price(config: dict[str, Any], grams: float, route_index: int) -> tuple[float, float]:
    for upper_bound, prices in config["base_tiers"]:
        if grams <= upper_bound:
            return prices[route_index], upper_bound
    last_bound, prices = config["base_tiers"][-1]
    return prices[route_index], last_bound


def _ceil_units(grams: float, unit_grams: int) -> int:
    return max(0, math.ceil(grams / unit_grams - 1e-12))


def _price_ctn(config: dict[str, Any], grams: float, route_index: int) -> float:
    base, base_limit = _base_price(config, grams, route_index)
    if grams <= base_limit:
        return base
    total = base
    lower = base_limit
    # Progressive blocks after 2 kg: 2–30 kg, 30–100 kg, etc.
    for upper, prices in config["progressive_tiers"]:
        upper = math.inf if upper is None else upper
        grams_in_block = min(grams, upper) - lower
        if grams_in_block > 0:
            total += _ceil_units(grams_in_block, config["unit_grams"]) * prices[route_index]
        if grams <= upper:
            return total
        lower = upper
    raise AssertionError("Bảng giá CTN001 thiếu bậc cuối.")


def calculate_shipping_fee(*, service: str, origin: str, destination: str, actual_weight_kg: float, length_cm: float, width_cm: float, height_cm: float) -> PriceQuote:
    """Calculate a tariff quote. Monetary values are rounded to two decimals."""
    if service not in PRICING:
        raise PricingError(f"Dịch vụ không hợp lệ: {service}.")
    route = determine_route(origin, destination, service)
    chargeable_kg, used_volume = chargeable_weight_kg(actual_weight_kg, length_cm, width_cm, height_cm)
    grams = chargeable_kg * 1000
    config = PRICING[service]
    index = _route_index(service, route)

    if service == "CTN001":
        amount = _price_ctn(config, grams, index)
    else:
        base, base_limit = _base_price(config, grams, index)
        if grams > base_limit:
            if "extra_per_unit" not in config:
                raise PricingError("Dịch vụ ETN001 hiện chỉ có bảng giá đến 2 kg.")
            amount = base + _ceil_units(grams - config["extra_after_grams"], config["unit_grams"]) * config["extra_per_unit"][index]
        else:
            amount = base
    return PriceQuote(service, route, float(actual_weight_kg), chargeable_kg, used_volume, round(amount, 2))
