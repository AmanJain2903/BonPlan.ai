# get_optimal_route

Find the distance-optimal visit order for a list of destinations that start and end at a given origin (Travelling-Salesperson heuristic using Haversine straight-line distances — NOT road distance).

### When to use
- The user has more than one destination in the same trip and you need the best order to visit them. ALWAYS call this first when `hasMultipleDestinations` is true.
- You are chaining several activities/stops in a day and want a sensible sequence before querying actual road routes.

### Arguments
- **`origin`** (object, required): `{ addressOrName, lat?, lng? }`. Provide at least one of `addressOrName` or `lat`+`lng`.
- **`destinations`** (list[object], required): Same shape per item; at least two for the optimizer to reorder.
- **`timeout_seconds`** (int, optional): Only raise if a prior call timed out.

### Returns
`{ optimalSequence: [<ordered destinations>], totalDistanceMiles: float }`

### Notes
- The ordering is a hint — always confirm legs with `get_route` / `get_route_matrix` before emitting COMMUTE events.
