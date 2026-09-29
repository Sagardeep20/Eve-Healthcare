"""Centre routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.centre import CentreDetailResponse, CentreResponse, CentreTestItem
from app.services import centre_service

router = APIRouter(prefix="/api/centres", tags=["centres"])


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} not found",
        )


@router.get("", response_model=list[CentreResponse])
def list_centres(db: Session = Depends(get_db)):
    return centre_service.list_centres(db)


@router.get("/{centre_id}", response_model=CentreResponse)
def get_centre(centre_id: str, db: Session = Depends(get_db)):
    centre = centre_service.get_centre(db, _parse_uuid(centre_id, "Centre"))
    if centre is None:
        raise HTTPException(status_code=404, detail="Centre not found")
    return centre


@router.get("/{centre_id}/tests", response_model=CentreDetailResponse)
def get_centre_tests(centre_id: str, db: Session = Depends(get_db)):
    centre, rows = centre_service.get_tests_for_centre(
        db, _parse_uuid(centre_id, "Centre")
    )
    if centre is None:
        raise HTTPException(status_code=404, detail="Centre not found")
    return CentreDetailResponse(
        id=centre.id,
        name=centre.name,
        location=centre.location,
        tests=[
            CentreTestItem(
                id=test.id,
                name=test.name,
                description=test.description,
                price=centre_test.price,
            )
            for test, centre_test in rows
        ],
    )
