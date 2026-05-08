# database/models/__init__.py

"""
This file contains the models for the database.
"""

from app.database.models.usersTable import User
from app.database.models.tripsTable import Trip
from app.database.models.tripMembersTable import TripMember
from app.database.models.apiCacheTable import ApiCache
from app.database.models.tripItinerariesTable import TripItinerary
from app.database.models.placePhotoCache import PlacePhotoCache
from app.database.models.rateLimitConfigs import RateLimitConfigs
from app.database.models.rateLimitUsage import RateLimitUsage
from app.database.models.tripCollabQATable import TripCollabQA
from app.database.models.tripItinerarySnapshotsTable import TripItinerarySnapshot
from app.database.models.faqTable import FAQ
from app.database.models.supportTicketsTable import SupportTicket
from app.database.models.emailSubscriptionsTable import EmailSubscription
from app.database.models.tripEmailNotificationsTable import TripEmailNotification
from app.database.models.rateLimitAlertSettingsTable import RateLimitAlertSettings
from app.database.models.rateLimitAlertEventsTable import RateLimitAlertEvent
