from __future__ import annotations

from typing import Optional, Dict, Any
import os
import structlog

try:
    import geoip2.database  # type: ignore
except Exception:
    geoip2 = None  # optional

logger = structlog.get_logger("memory.geo_risk")

class GeoRisk:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.reader = None
        if db_path and geoip2:
            try:
                self.reader = geoip2.database.Reader(db_path)
            except Exception as e:
                logger.warning("geoip_init_failed", error=str(e))

    def score_ip(self, ip: str) -> Dict[str, Any]:
        score = 0
        geo = {}
        if self.reader:
            try:
                resp = self.reader.city(ip)
                country = resp.country.iso_code or "UNK"
                asn = getattr(resp, "traits", None)
                risky_countries = {"RU","KP","IR"}  # example policy
                if country in risky_countries:
                    score += 2
                geo = {"country": country, "city": resp.city.name}
            except Exception:
                pass
        return {"ip": ip, "risk": score, "geo": geo}