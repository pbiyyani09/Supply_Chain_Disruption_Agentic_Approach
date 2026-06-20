from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from data.geo_matcher import get_lat_lng
from db.crud import get_suppliers, upsert_supplier
from db.database import get_db

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


class SupplierOut(BaseModel):
    id: str
    name: str
    country_code: str
    region: str | None
    product_category: str
    tier: int
    lat: float | None
    lng: float | None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)):
    return get_suppliers(db)


@router.post("/upload-csv", response_model=dict)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a CSV with columns: name,country_code,product_category,tier,region"""
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))

    required = {"name", "country_code", "product_category", "tier"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain columns: {required}",
        )

    count = 0
    for row in reader:
        code = row["country_code"].strip().upper()
        lat, lng = get_lat_lng(code)
        data = {
            "name": row["name"].strip(),
            "country_code": code,
            "product_category": row.get("product_category", "").strip(),
            "tier": int(row.get("tier", 1)),
            "region": row.get("region", "").strip() or None,
            "lat": lat,
            "lng": lng,
        }
        upsert_supplier(db, data)
        count += 1

    return {"imported": count}
