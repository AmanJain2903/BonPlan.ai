# get_optimal_route

## Purpose
Calculates the most efficient sequence to visit a list of destinations starting and ending at a specific origin (the Travelling Salesperson Problem) based on straight-line Haversine distances.

## When to use
Use this tool to plan multi-stop itineraries where the visit order matters and needs to be optimized for the shortest overall travel distance. Note that this is based on straight-line distances, not actual road routes. 
You must always call this tool whenever the user has multiple destinations to visit as this will give you the best chronological order to visit those destinations. You can also call this tool if you need to figure out the most efficient sequence of travel between multiple places you are planning in the itinerary.

## Arguments
- `origin` (Location): The start and end location object.
  - Example: `{"addressOrName": "New York"}` or `{"addressOrName": "JFK Airport", "lat": 40.6413, "lng": -73.7781}`
- `destinations` (List[Location]): The list of locations to visit in between.
  - Example: `[{"addressOrName": "Boston"}, {"addressOrName": "Philadelphia"}]`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 10 seconds.
  - Example: `15`

## Returns
- **Success**: A dictionary containing `optimalSequence` (an ordered list of locations) and `totalDistanceMiles`.
- **Error**: A dictionary containing an `error` key.
