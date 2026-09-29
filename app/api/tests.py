"""Diagnostic test routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.test import TestResponse
from app.services import centre_service

router = APIRouter(prefix="/api/tests", tags=["tests"])


@router.get("", response_model=list[TestResponse])
def list_tests(db: Session = Depends(get_db)):
    return centre_service.list_tests(db)


@router.get("/{test_id}", response_model=TestResponse)
def get_test(test_id: str, db: Session = Depends(get_db)):
    try:
        tid = uuid.UUID(test_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Test not found")
    test = centre_service.get_test(db, tid)
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )
    return test
