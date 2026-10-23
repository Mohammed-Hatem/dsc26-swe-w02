# Parcel lifecycle in a pure domain module

## Status

Accepted

## Context

Parcel lifecycle rules must remain consistent regardless of whether they are called
through HTTP or another interface. Putting the rules in the API layer would couple
business behavior to FastAPI and make the lifecycle harder to test independently.

## Decision

We will keep the parcel state machine in `app/domain.py` using plain Python dataclasses,
enums, and an `apply_event` function. The HTTP layer will translate requests and
responses but will delegate lifecycle decisions to the domain module.

## Consequences

The lifecycle can be tested without starting a web application, and the domain module
has no framework dependencies. The API layer must translate domain exceptions into
appropriate HTTP responses.
