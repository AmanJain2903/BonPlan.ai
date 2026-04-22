# get_address

Reverse-geocode a lat/lng pair to a formatted street address.

### When to use
- A prior tool returned only coordinates and you need a human-readable address to store in an event or to display to the user.

### Arguments
- **`lat`** (float, required): −90..90.
- **`lng`** (float, required): −180..180.
- **`timeout_seconds`** (int, optional): Only raise if a prior call timed out.

### Returns
`{ "address": "<formal formatted address>" }`
