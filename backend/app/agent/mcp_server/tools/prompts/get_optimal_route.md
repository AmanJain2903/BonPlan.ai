# get_optimal_route

## Purpose
Calculates the most efficient sequence to visit a list of destinations starting and ending at a specific origin (the Travelling Salesperson Problem) based on straight-line Haversine distances.

## When to use
Use this tool to plan multi-stop itineraries where the visit order matters and needs to be optimized for the shortest overall travel distance. Note that this is based on straight-line distances, not actual road routes.

## Arguments
- `origin` (Location): The start and end location object.
  - Example: `{"addressOrName": "New York"}` or `{"addressOrName": "JFK Airport", "lat": 40.6413, "lng": -73.7781}`
- `destinations` (List[Location]): The list of locations to visit in between.
  - Example: `[{"addressOrName": "Boston"}, {"addressOrName": "Philadelphia"}]`

## Returns
- **Success**: A dictionary containing `optimalSequence` (an ordered list of locations), `totalDistanceKm`, `totalDistanceMiles`, `sequenceSummary`, and an `explanation`.
- **Error**: A dictionary containing an `error` key.
