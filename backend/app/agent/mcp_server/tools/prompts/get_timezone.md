# get_timezone

Return the IANA timezone data (and optionally local wall-clock time) for a lat/lng pair.

### When to use
- You need the IANA zone (`timeZoneId`) of a place before scheduling or time conversion.
- You need the local date/time at a coordinate for a specific moment — pass `timestamp`.

### Arguments
- **`lat`** (float, required): −90..90.
- **`lng`** (float, required): −180..180.
- **`timestamp`** (int, optional): Unix seconds at which to resolve. If omitted, only `timeZoneId` / `timeZoneName` are returned — no offset or local time.
- **`timeout_seconds`** (int, optional): Only raise if a prior call timed out.

### Returns
- Without `timestamp`: `{ timeZoneId, timeZoneName }` (each wrapped in `{value, description}`).
- With `timestamp`: adds `dstOffset` (sec), `rawOffset` (sec), `localDateTimeString`.
