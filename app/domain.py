"""Parcel lifecycle rules for Tawseel.

Pure Python: do not import fastapi, starlette, pydantic or sqlalchemy here
(a hidden test checks). Keep the names below exactly as they are.
"""
from dataclasses import dataclass
from enum import StrEnum

MAX_ATTEMPTS = 3


class ParcelState(StrEnum):
    CREATED = "created"
    OUT_FOR_DELIVERY = "out_for_delivery"
    FAILED_ATTEMPT = "failed_attempt"
    DELIVERED = "delivered"
    RETURNED = "returned"


class EventType(StrEnum):
    DISPATCH = "dispatch"
    DELIVER = "deliver"
    FAIL = "fail"
    RETURN = "return"


class InvalidTransition(Exception): ...


@dataclass(frozen=True)
class Parcel:
    id: str
    merchant_ref: str
    cod_amount_piastres: int
    address_text: str
    state: ParcelState = ParcelState.CREATED
    attempts: int = 0


def apply_event(parcel: Parcel, event: EventType) -> Parcel:
    """Return a new Parcel. Raise InvalidTransition if the event is not allowed.

    - created + dispatch -> out_for_delivery, attempts + 1
    - out_for_delivery + deliver -> delivered
    - out_for_delivery + fail -> failed_attempt
    - failed_attempt + dispatch -> out_for_delivery, attempts + 1, only if attempts < MAX_ATTEMPTS
    - failed_attempt + return -> returned
    - delivered and returned are final; every other combination raises InvalidTransition.
    Never mutate the input parcel.
    """
    state = parcel.state
    if state == ParcelState.CREATED and event == EventType.DISPATCH:
        return Parcel(
            id=parcel.id,
            merchant_ref=parcel.merchant_ref,
            cod_amount_piastres=parcel.cod_amount_piastres,
            address_text=parcel.address_text,
            state=ParcelState.OUT_FOR_DELIVERY,
            attempts=parcel.attempts + 1
        )
    elif state == ParcelState.OUT_FOR_DELIVERY and event == EventType.DELIVER:
        return Parcel(
            id=parcel.id,
            merchant_ref=parcel.merchant_ref,
            cod_amount_piastres=parcel.cod_amount_piastres,
            address_text=parcel.address_text,
            state=ParcelState.DELIVERED,
            attempts=parcel.attempts
        )
    elif state == ParcelState.OUT_FOR_DELIVERY and event == EventType.FAIL:
        return Parcel(
            id=parcel.id,
            merchant_ref=parcel.merchant_ref,
            cod_amount_piastres=parcel.cod_amount_piastres,
            address_text=parcel.address_text,
            state=ParcelState.FAILED_ATTEMPT,
            attempts=parcel.attempts
        )
    elif state == ParcelState.FAILED_ATTEMPT and event == EventType.DISPATCH:
        if parcel.attempts < MAX_ATTEMPTS:
            return Parcel(
                id=parcel.id,
                merchant_ref=parcel.merchant_ref,
                cod_amount_piastres=parcel.cod_amount_piastres,
                address_text=parcel.address_text,
                state=ParcelState.OUT_FOR_DELIVERY,
                attempts=parcel.attempts + 1
            )
        else:
            raise InvalidTransition(f"Cannot dispatch parcel {parcel.id}: max attempts reached.")
    elif state == ParcelState.FAILED_ATTEMPT and event == EventType.RETURN:
        return Parcel(
            id=parcel.id,
            merchant_ref=parcel.merchant_ref,
            cod_amount_piastres=parcel.cod_amount_piastres,
            address_text=parcel.address_text,
            state=ParcelState.RETURNED,
            attempts=parcel.attempts
        )
    else:
        raise InvalidTransition(f"Invalid transition from {state} with event {event}.") 
       


