# backend/app/api/seo.py

from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select

from app.core.config import settings
from app.database.database import Session
from app.database.models.tripsTable import Trip, PlanStatus
from app.database.models.tripItinerariesTable import TripItinerary
from app.logging import get_api_logger

logger = get_api_logger("api.seo")

router = APIRouter()

_INDEXABLE = [PlanStatus.GENERATED, PlanStatus.CURRENT, PlanStatus.COMPLETED]


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /trip/\n"
        "Disallow: /api/\n"
        "Disallow: /admin\n"
        "Disallow: /account\n"
        "Disallow: /plan/\n"
        "Disallow: /draft-plan\n"
        "Disallow: /login\n"
        "Disallow: /register\n"
        "Disallow: /auth/\n"
        "\n"
        f"Sitemap: {settings.BACKEND_URL}/sitemap.xml\n"
    )
    return PlainTextResponse(content=content)


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    static_urls = [
        {"loc": settings.FRONTEND_URL, "changefreq": "weekly", "priority": "1.0"},
    ]

    trip_urls = []
    try:
        async with Session() as db:
            rows = (await db.execute(
                select(
                    Trip.id,
                    Trip.updated_at,
                    TripItinerary.updated_at.label("itin_updated_at"),
                )
                .join(TripItinerary, TripItinerary.trip_id == Trip.id, isouter=True)
                .where(Trip.is_public.is_(True), Trip.status.in_(_INDEXABLE))
            )).all()

            for row in rows:
                lastmod = row.itin_updated_at or row.updated_at or datetime.utcnow()
                trip_urls.append({
                    "loc": f"{settings.FRONTEND_URL}/trip/{row.id}",
                    "lastmod": lastmod.strftime("%Y-%m-%d"),
                    "changefreq": "monthly",
                    "priority": "0.8",
                })
    except Exception:
        logger.exception("sitemap_xml DB error")

    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in static_urls + trip_urls:
        xml_parts.append("  <url>")
        xml_parts.append(f"    <loc>{url['loc']}</loc>")
        if "lastmod" in url:
            xml_parts.append(f"    <lastmod>{url['lastmod']}</lastmod>")
        xml_parts.append(f"    <changefreq>{url['changefreq']}</changefreq>")
        xml_parts.append(f"    <priority>{url['priority']}</priority>")
        xml_parts.append("  </url>")
    xml_parts.append("</urlset>")

    return Response(content="\n".join(xml_parts), media_type="application/xml")
