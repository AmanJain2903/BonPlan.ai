from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid as _uuid

# --- ENUMS ---
class AccessibilityOption(str, Enum):
    STANDARD = "standard"
    WHEELCHAIR_ACCESSIBLE = "wheelchair_accessible"
    WHEELCHAIR_STRICT = "wheelchair_strict"
    STEP_FREE_PREFERRED = "step_free_preferred"

class TravelToOption(str, Enum):
    AIRPLANE = "airplane"
    TRAIN = "train"
    BUS = "bus"
    OWN_CAR = "own_car"
    RENTAL_CAR = "rental_car"
    CAB = "cab"
    MOTORCYCLE = "motorcycle"
    ANY = "any"

class TravelAroundOption(str, Enum):
    PUBLIC_TRANSPORT = "public_transport"
    OWN_CAR = "own_car"
    RENTAL_CAR = "rental_car"
    CAB = "cab"
    WALKING = "walking"
    CYCLING = "cycling"
    MOTORCYCLE = "motorcycle"
    ANY = "any"

class ScheduleRhythm(str, Enum):
    EARLY_BIRD = "early_bird"
    STANDARD = "standard"
    NIGHT_OWL = "night_owl"

class AccommodationStyle(str, Enum):
    HOTEL = "hotel"
    HOSTEL = "hostel"
    LODGE = "lodge"
    ANY = "any"

class DiningStyle(str, Enum):
    FAST_CASUAL_AND_STREET_FOOD = "fast_casual_and_street_food" 
    MID_RANGE_SIT_DOWN = "mid_range_sit_down"
    UPSCALE_FINE_DINING = "upscale_fine_dining"
    GROCERIES_AND_COOKING = "groceries_and_cooking"
    ANY = "any"

class TravelPreferences(BaseModel):
    travel_to_destination: TravelToOption = TravelToOption.ANY
    travel_around_destination: TravelAroundOption = TravelAroundOption.ANY

class OtherPreferences(BaseModel):
    pet_friendly: bool = False
    child_friendly: bool = False
    toddler_friendly: bool = False
    smoking_allowed: bool = False
    alcohol_allowed: bool = False
    ev_charging_available: bool = False
    additional_notes: Optional[str] = ""

class LockedRoutineFrequency(str, Enum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"
    SPECIFIC_DAYS = "specific_days"

class LockedRoutine(BaseModel):
    id: str = Field(default_factory=lambda: str(_uuid.uuid4()))
    name: str
    frequency: LockedRoutineFrequency = LockedRoutineFrequency.DAILY
    specific_days: Optional[List[int]] = None  # 0=Mon … 6=Sun
    start_time: str  # HH:MM 24h
    duration_minutes: int

# --- MASTER SCHEMA ---
class TripPreferencesSchema(BaseModel):
    dietary_restrictions: List[str] = Field(default_factory=list)
    accessibility_preferences: AccessibilityOption = AccessibilityOption.STANDARD
    travel_preferences: TravelPreferences = Field(default_factory=TravelPreferences)
    schedule_rhythm: ScheduleRhythm = ScheduleRhythm.STANDARD
    activity_interests: List[str] = Field(default_factory=list)
    accommodation_style: AccommodationStyle = AccommodationStyle.ANY
    dining_style: DiningStyle = DiningStyle.ANY
    other_preferences: OtherPreferences = Field(default_factory=OtherPreferences)
    locked_routines: List[LockedRoutine] = Field(default_factory=list)

    class Config:
        # Crucial for saving the actual string 'vegan' to the DB instead of the object
        use_enum_values = True