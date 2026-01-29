"""Documents API package - split into modular routers following Karpathy's simplicity principle."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.documents.documents_core import router as core_router
from app.api.documents.documents_fhir import router as fhir_router
from app.api.documents.documents_bulk import router as bulk_router
from app.api.documents.documents_search import router as search_router
from app.api.documents.documents_tags import router as tags_router

# Create a combined router that includes all sub-routers
router = APIRouter()

# Include all sub-routers (they already have the /documents prefix)
router.include_router(core_router)
router.include_router(fhir_router)
router.include_router(bulk_router)
router.include_router(search_router)
router.include_router(tags_router)

__all__ = [
    "router",
    "core_router",
    "fhir_router",
    "bulk_router",
    "search_router",
    "tags_router",
]
