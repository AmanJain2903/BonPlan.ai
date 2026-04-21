from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal

travelToOptions = Literal["any", "airplane", "own_car", "rental_car", "cab", "motorcycle"]
travelAroundOptions = Literal["any", "public_transport", "own_car", "rental_car", "cab", "walking", "cycling", "motorcycle"]
accessibilityOptions = Literal['standard', 'wheelchair_accessible', 'wheelchair_strict', 'step_free_preferred']
scheduleRhythmOptions = Literal['early_bird', 'standard', 'night_owl']
accommodationStyleOptions = Literal['hotel', 'hostel', 'lodge', 'any']
diningStyleOptions = Literal['fast_casual_and_street_food', 'mid_range_sit_down', 'upscale_fine_dining', 'groceries_and_cooking', 'any']
paceOptions = Literal["Deep Relax", "Easygoing", "Balanced", "Active Explorer", "Action Packed"]
budgetOptions = Literal["Shoestring", "Moderate", "Comfortable", "Premium", "Luxury"]

class LocationInput(BaseModel):
    lat: float = Field(ge=-90, le=90, description="Latitude of the location")
    lng: float = Field(ge=-180, le=180, description="Longitude of the location")
    city: Optional[str] = Field(description="City name", default="")
    state: Optional[str] = Field(description="State name", default="")
    country: Optional[str] = Field(description="Country name", default="")

class DateInput(BaseModel):
    day: int = Field(ge=1, le=31, description="Day of the month in origin timezone")
    month: int = Field(ge=1, le=12, description="Month of the year in origin timezone")
    year: int = Field(description="Year in origin timezone")
    timezoneId: str = Field(description="Timezone ID of origin")
    utcTimestamp: int = Field(description="UTC timestamp for the date time")
    utcTimeString: str = Field(description="UTC time string for the date time")
    localTimeString: str = Field(description="Local time string in origin timezone")

class TravelPreferences(BaseModel):
    travel_to_destination: travelToOptions = Field(description="Preffered travel mode to from origin to destination (e.g. own car, rental car, flight)")
    travel_around_destination: travelAroundOptions = Field(description="Preffered travel mode to travel around destination (e.g. public transport, car, walking)")

class OtherPreferences(BaseModel):
    pet_friendly: bool = Field(description="Does the user prefer pet friendly accommodations and activities?")
    child_friendly: bool = Field(description="Does the user prefer child friendly accommodations and activities?")
    toddler_friendly: bool = Field(description="Does the user prefer toddler friendly accommodations and activities?")
    smoking_allowed: bool = Field(description="Does the user prefer smoking allowed accommodations and activities?")
    alcohol_allowed: bool = Field(description="Does the user prefer alcohol allowed accommodations and activities?")
    ev_charging_available: bool = Field(description="Does the user prefer EV charging available accommodations and activities?")
    additional_notes: str = Field(description="Additional notes for the trip given by the user")
    
class TripPreferencesInput(BaseModel):
    dietary_restrictions: List[str] = Field(description="List of dietary restrictions the user prefers")
    accessibility_preferences: accessibilityOptions = Field(description="Accessibility preferences the user prefers")
    travel_preferences: TravelPreferences = Field(description="Travel preferences the user prefers")
    schedule_rhythm: scheduleRhythmOptions = Field(description="Schedule rhythm the user prefers")
    activity_interests: List[str] = Field(description="List of activity interests the user prefers")
    accommodation_style: accommodationStyleOptions = Field(description="Accommodation style the user prefers")
    dining_style: diningStyleOptions = Field(description="Dining style the user prefers")
    other_preferences: OtherPreferences = Field(description="Other preferences the user prefers")

class TripInput(BaseModel):
    hasMultipleDestinations: bool = Field(description="Whether the trip has multiple destinations (more than 1) or not")
    origin: LocationInput = Field(description="The starting location of the trip")
    destinations: List[LocationInput] = Field(description="List of destinations to visit during the trip. Has single destination if hasMultipleDestinations is false")
    start_date: DateInput = Field(description="Start date of the trip object")
    end_date: DateInput = Field(description="End date of the trip object")
    pace: paceOptions = Field(description="Pace of the trip (e.g. relaxed, medium, fast)")
    budget: budgetOptions = Field(description="Budget scaling for the trip (e.g. budget, moderate, luxury)")
    adults: int = Field(description="Number of adult travelers (12+ years old)")
    children: int = Field(description="Number of children travelers (0-11 years old)")
    preferences: TripPreferencesInput = Field(description="User's preferences for the specified trip")
    textualContext: Optional[str] = Field(description="Textual context for the trip to plan", default="")
