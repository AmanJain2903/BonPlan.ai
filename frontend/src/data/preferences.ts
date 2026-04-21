import {
    Plane, Bus, Car, Bike, Footprints, Globe,
    Clock, Compass, Utensils, Building2, MapPin, Accessibility, Heart, StickyNote,
    type LucideIcon,
} from 'lucide-react';

/* ──────────────────────── Types ──────────────────────── */
export type TravelPreferences = {
    travel_to_destination: string;
    travel_around_destination: string;
};

export type OtherPreferences = {
    pet_friendly: boolean;
    child_friendly: boolean;
    toddler_friendly: boolean;
    smoking_allowed: boolean;
    alcohol_allowed: boolean;
    ev_charging_available: boolean;
    additional_notes: string;
};

export type TripPreferences = {
    dietary_restrictions: string[];
    accessibility_preferences: string;
    travel_preferences: TravelPreferences;
    schedule_rhythm: string;
    activity_interests: string[];
    accommodation_style: string;
    dining_style: string;
    other_preferences: OtherPreferences;
};

/* ──────────────────────── Constants ──────────────────────── */
export const ACTIVITY_INTERESTS = [
    // --- The Classics ---
    { value: 'nature_and_hiking', label: 'Nature & Hiking' },
    { value: 'art_and_museums', label: 'Art & Museums' },
    { value: 'history_and_culture', label: 'History & Culture' },
    { value: 'shopping', label: 'Shopping' },

    // --- Food & Beverage ---
    { value: 'food_tourism', label: 'Food & Culinary Tours' },
    { value: 'wine_and_breweries', label: 'Wine Tastings & Breweries' },
    { value: 'cooking_classes', label: 'Cooking Classes & Workshops' },
    { value: 'coffee_shop_hopping', label: 'Coffee Shop Hopping' },

    // --- Active & Outdoors ---
    { value: 'fitness_and_wellness', label: 'Fitness & Wellness' },
    { value: 'extreme_adventure_sports', label: 'Extreme Adventure Sports' },
    { value: 'water_sports_and_beaches', label: 'Water Sports & Beaches' },
    { value: 'winter_sports', label: 'Winter Sports & Skiing' },
    { value: 'wildlife_and_safari', label: 'Wildlife & Safari' },

    // --- Entertainment & Nightlife ---
    { value: 'nightlife', label: 'Nightlife & Clubbing' },
    { value: 'live_music_and_concerts', label: 'Live Music & Concerts' },
    { value: 'theater_and_performing_arts', label: 'Theater & Performing Arts' },
    { value: 'local_festivals', label: 'Local Festivals & Events' },

    // --- Niche & Specialty ---
    { value: 'architecture_and_design', label: 'Architecture & Design' },
    { value: 'photography_spots', label: 'Photography & Scenic Spots' },
    { value: 'spa_and_relaxation', label: 'Spa & Relaxation' },
    { value: 'religious_and_spiritual', label: 'Religious & Spiritual Sites' },
    { value: 'theme_parks_and_amusements', label: 'Theme Parks & Amusements' },
    { value: 'pop_culture_locations', label: 'Film & Pop Culture Locations' }
];

export const ACCOMMODATION_STYLES = [
    { value: 'hotel', label: 'Hotel' },
    { value: 'hostel', label: 'Hostel' },
    { value: 'lodge', label: 'Lodge' },
    { value: 'any', label: 'Any' },
];

export const DINING_STYLES = [
    { value: 'fast_casual_and_street_food', label: 'Fast Casual & Street Food' },
    { value: 'mid_range_sit_down', label: 'Mid-Range Sit-Down' },
    { value: 'upscale_fine_dining', label: 'Upscale Fine Dining' },
    { value: 'groceries_and_cooking', label: 'Groceries & Cooking' },
    { value: 'any', label: 'Any' },
];

export const TRAVEL_TO_OPTIONS = [
    { value: 'any', label: 'Any', icon: Globe },
    { value: 'airplane', label: 'Airplane', icon: Plane },
    { value: 'own_car', label: 'Own Car', icon: Car },
    { value: 'rental_car', label: 'Rental Car', icon: Car },
    { value: 'cab', label: 'Cab', icon: Car },
    { value: 'motorcycle', label: 'Motorcycle', icon: Bike },
];

export const TRAVEL_AROUND_OPTIONS = [
    { value: 'any', label: 'Any', icon: Globe },
    { value: 'public_transport', label: 'Public Transit', icon: Bus },
    { value: 'walking', label: 'Walking', icon: Footprints },
    { value: 'cycling', label: 'Cycling', icon: Bike },
    { value: 'own_car', label: 'Own Car', icon: Car },
    { value: 'rental_car', label: 'Rental Car', icon: Car },
    { value: 'cab', label: 'Cab', icon: Car },
    { value: 'motorcycle', label: 'Motorcycle', icon: Bike },
];

export const POPULAR_DIETS = ['Vegetarian', 'Vegan', 'Gluten-Free', 'Lactose-Free', 'Nut-Free', 'Kosher', 'Halal', 'Pescetarian'];

export const ACCESSIBILITY_OPTIONS = [
    { value: 'standard', label: 'Standard', desc: 'No special accessibility requirements.' },
    { value: 'wheelchair_accessible', label: 'Wheelchair Accessible', desc: 'Prefer locations with wheelchair access.' },
    { value: 'wheelchair_strict', label: 'Wheelchair Strict', desc: 'Only choose fully wheelchair-accessible venues.' },
    { value: 'step_free_preferred', label: 'Step-Free Preferred', desc: 'Avoid stairs and stepped entrances where possible.' },
];

export const LIFESTYLE_TOGGLES: { key: keyof OtherPreferences; label: string }[] = [
    { key: 'pet_friendly', label: 'Pet Friendly' },
    { key: 'child_friendly', label: 'Child Friendly' },
    { key: 'toddler_friendly', label: 'Toddler Friendly' },
    { key: 'smoking_allowed', label: 'Smoking Allowed' },
    { key: 'alcohol_allowed', label: 'Alcohol Allowed' },
    { key: 'ev_charging_available', label: 'EV Charging' },
];


/* ──────────────────── Field Descriptions (icons + helper text) ──────────────────── */
export const FIELD_DESCRIPTIONS: Record<string, { icon: LucideIcon; desc: string }> = {
    schedule_rhythm: { icon: Clock, desc: 'Your natural energy cycle — determines when the AI starts and ends your day.' },
    activity_interests: { icon: Compass, desc: 'Core themes the AI will prioritise for sightseeing and experiences.' },
    travel_to: { icon: MapPin, desc: 'How you prefer to arrive at your destination.' },
    travel_around: { icon: MapPin, desc: 'How you prefer to move around once you\'re there.' },
    accommodation_style: { icon: Building2, desc: 'The type of basecamp the AI will search for.' },
    dining_style: { icon: Utensils, desc: 'How you prefer to eat — separate from dietary restrictions.' },
    dietary_restrictions: { icon: Utensils, desc: 'Strictly filters dining recommendations to match your needs.' },
    accessibility: { icon: Accessibility, desc: 'Mobility constraints for routing and venue selection.' },
    lifestyle: { icon: Heart, desc: 'Lifestyle toggles that influence which places the AI picks.' },
    additional_notes: { icon: StickyNote, desc: 'Catch-all notes for anything the AI should know about.' },
};

/* ──────────────────── Default preferences ──────────────────── */
export const DEFAULT_PREFERENCES: TripPreferences = {
    dietary_restrictions: [],
    accessibility_preferences: 'standard',
    travel_preferences: { travel_to_destination: 'any', travel_around_destination: 'any' },
    schedule_rhythm: 'standard',
    activity_interests: [],
    accommodation_style: 'any',
    dining_style: 'any',
    other_preferences: {
        pet_friendly: false,
        child_friendly: false,
        toddler_friendly: false,
        smoking_allowed: false,
        alcohol_allowed: false,
        ev_charging_available: false,
        additional_notes: '',
    },
};
