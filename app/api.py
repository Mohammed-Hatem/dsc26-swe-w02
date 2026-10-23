"""HTTP layer for the Tawseel parcel service.

The HTTP layer translates requests into calls to app.domain; the domain decides.
See README.md for the four operations, their operationIds and their errors.
"""
import base64
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.domain import EventType, InvalidTransition, Parcel, ParcelState, apply_event  # noqa: F401

from pydantic import BaseModel, ConfigDict, Field

PROBLEM = "application/problem+json"
PROBLEM_CONTENT = {PROBLEM: {}}


class ParcelIn(BaseModel):
    model_config = ConfigDict(strict=True)

    merchant_ref: str = Field(min_length=1, max_length=64)
    cod_amount_piastres: int = Field(ge=0, le=5_000_000)
    address_text: str = Field(min_length=1, max_length=500)


class EventIn(BaseModel):
    type: EventType


class ParcelOut(BaseModel):
    id: str
    merchant_ref: str
    cod_amount_piastres: int
    address_text: str
    state: ParcelState
    attempts: int

class ParcelListOut(BaseModel):
    items: list[ParcelOut]
    next_cursor: str | None = None

def to_parcel_out(parcel: Parcel) -> ParcelOut:
    return ParcelOut(
        id=parcel.id,
        merchant_ref=parcel.merchant_ref,
        cod_amount_piastres=parcel.cod_amount_piastres,
        address_text=parcel.address_text,
        state=parcel.state,
        attempts=parcel.attempts,
    )

def to_parcel_list_out(parcels: list[Parcel], next_cursor: str | None = None) -> ParcelListOut:
    return ParcelListOut(
        items=[to_parcel_out(parcel) for parcel in parcels],
        next_cursor=next_cursor
    )


def create_app() -> FastAPI:
    """Return a NEW FastAPI app with its own empty in-memory store.

    Tests call this once per test, so nothing may be shared between two apps
    (no module-level dicts or counters for parcels).
    """

    parcels: dict[str, Parcel] = {}
    counter = 0  # parcel id counter
    refs: set[str] = set()  # merchant_ref values must be unique across parcels
    cursor_issued: dict[str, int] = {}  # cursors we handed out -> position of last item returned
    app = FastAPI(title="Tawseel Parcel Service", version="0.1.0")

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        errors = []
        seen = set()
        for e in exc.errors():
            loc = list(e["loc"])
            if tuple(loc) in seen:  # exactly one entry per invalid field
                continue
            seen.add(tuple(loc))
            errors.append({"loc": loc, "msg": e["msg"]})
        return JSONResponse(
            status_code=422,
            media_type=PROBLEM,
            content={"type": "about:blank", "title": "Validation error",
                     "status": 422, "errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            media_type=PROBLEM,
            content={"type": "about:blank",
                     "title": HTTPStatus(exc.status_code).phrase,
                     "status": exc.status_code,
                     "detail": str(exc.detail)},
        )

    @app.post("/v1/parcels", status_code=201, operation_id="createParcel",
              response_model=ParcelOut,
              responses={409: {"description": "Duplicate merchant_ref", "content": PROBLEM_CONTENT},
                         422: {"description": "Invalid body", "content": PROBLEM_CONTENT}})
    def create_parcel(body: ParcelIn, response: Response) -> ParcelOut:
        nonlocal counter
        if body.merchant_ref in refs:
            raise HTTPException(status_code=409, detail="duplicate merchant_ref")
        counter += 1
        parcel = Parcel(
            id=f"pcl_{counter:06d}",
            merchant_ref=body.merchant_ref,
            cod_amount_piastres=body.cod_amount_piastres,
            address_text=body.address_text,
        )
        parcels[parcel.id] = parcel
        refs.add(parcel.merchant_ref)
        response.headers["Location"] = f"/v1/parcels/{parcel.id}"
        return to_parcel_out(parcel)

    @app.get("/v1/parcels/{parcel_id}", status_code=200, operation_id="getParcel",
             response_model=ParcelOut,
             responses={404: {"description": "Parcel not found", "content": PROBLEM_CONTENT}})
    def get_parcel(parcel_id: str) -> ParcelOut:
        parcel = parcels.get(parcel_id)
        if parcel is None:
            raise HTTPException(status_code=404, detail="Parcel not found")
        return to_parcel_out(parcel)

    @app.get("/v1/parcels", status_code=200, operation_id="listParcels",
             response_model=ParcelListOut,
             responses={400: {"description": "Bad cursor", "content": PROBLEM_CONTENT},
                        422: {"description": "Bad state or limit", "content": PROBLEM_CONTENT}})
    def list_parcels(state: ParcelState | None = None,
                     limit: int = Query(20, ge=1, le=100),
                     cursor: str | None = None) -> ParcelListOut:
        start = 0
        if cursor is not None:
            if cursor not in cursor_issued:
                raise HTTPException(status_code=400, detail="bad cursor")
            start = cursor_issued[cursor] + 1

        matches = []
        for index, parcel in enumerate(parcels.values()):
            if index >= start and (state is None or parcel.state == state):
                matches.append((index, parcel))
                if len(matches) == limit + 1:
                    break

        page = matches[:limit]
        if len(matches) > limit:
            last_index = page[-1][0]
            next_cursor = base64.urlsafe_b64encode(
                str(last_index).encode()
            ).decode()
            cursor_issued[next_cursor] = last_index
        else:
            next_cursor = None

        return to_parcel_list_out(
            [parcel for _, parcel in page],
            next_cursor=next_cursor,
        )

    @app.post("/v1/parcels/{parcel_id}/events", status_code=200,
              operation_id="recordParcelEvent", response_model=ParcelOut,
              responses={404: {"description": "Parcel not found", "content": PROBLEM_CONTENT},
                         409: {"description": "Invalid transition", "content": PROBLEM_CONTENT},
                         422: {"description": "Unknown or missing event type", "content": PROBLEM_CONTENT}})
    def record_parcel_event(parcel_id: str, body: EventIn) -> ParcelOut:
        parcel = parcels.get(parcel_id)
        if parcel is None:
            raise HTTPException(status_code=404, detail="Parcel not found")
        try:
            updated_parcel = apply_event(parcel, body.type)
        except InvalidTransition as e:
            raise HTTPException(status_code=409, detail=str(e))
        parcels[parcel_id] = updated_parcel
        return to_parcel_out(updated_parcel)

    return app


# `uvicorn app.api:app` needs a module-level app. Once create_app() works,
# replace the line below with:  app = create_app()
app = create_app()