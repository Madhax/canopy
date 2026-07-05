from fastapi import APIRouter, Response

from ..catalog import get_catalog

router = APIRouter()


@router.get("/catalog")
def read_catalog(response: Response) -> dict:
    catalog = get_catalog()
    # Catalog is static for a given build; allow cheap client caching.
    response.headers["Cache-Control"] = "public, max-age=300"
    return catalog.model_dump(by_alias=True, mode="json")
