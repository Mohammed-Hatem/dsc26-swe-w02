# Cursor pagination for parcel lists

## Status

Accepted

## Context

Parcel lists can be read across multiple requests while parcel states change between
requests. Offset pagination can skip or repeat parcels when earlier records move in or
out of a filtered result set.

## Decision

We will use opaque, server-issued cursors for `listParcels`. Each cursor identifies the
last position reached in the creation-ordered parcel collection, and the API will issue
a cursor only when another matching parcel exists.

## Consequences

Clients can continue walking a filtered list without relying on offsets, and the final
page can be identified with `next_cursor: null`. The server must retain the cursors it
issued for the lifetime of the in-memory application, and clients must treat cursors as
opaque values.
