from fastapi import APIRouter
from app.services.s3_reader import load_trends

router = APIRouter()

@router.get("/trends")
def get_trends():
    return load_trends()