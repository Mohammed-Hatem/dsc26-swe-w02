# AI usage
## Tools

    I used claude code to understand the requiremnts and match it against my implementations 
    Additionally, I also used it to suggest a cursor implemtation

## What AI got wrong

I fixed the cursor calculation
to store the last returned creation position and then changed the cursor value to
a random opaque token instead of the base64 to prevent the clients from constructing their own cursor
## In my own words

1. Why does `listParcels` need a cursor rather than an offset?

because the parcel state can change between requests. Applying the offset on the filtered results will cause rows skipping or duplicate parcels.

2. Which of your four operations would break the courier app if you renamed one field, and who would have to approve that change?

renaming a field in the createParcel would break the merchant and the curior app beacuse both depend on the API contract. So both the teams working on the 2 apps would have to approve this change 
