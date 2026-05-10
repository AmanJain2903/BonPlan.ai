import boto3
import psycopg2
from app.core.config import settings

# 1. Setup R2 Client
s3 = boto3.client(
    service_name="s3",
    endpoint_url=settings.CLOUDFLARE_R2_ENDPOINT_URL,
    aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
    region_name="auto",
)

# 2. Connect to Postgres
# Strip the '+asyncpg' prefix
conn = psycopg2.connect(settings.DATABASE_URL)
cur = conn.cursor()

# 3. Fetch Blobs
cur.execute("SELECT id, image_data FROM place_photo_cache")
rows = cur.fetchall()

for row_id, blob in rows:
    file_key = f"photo_cache/{row_id}.jpg"
    
    # Upload to R2
    s3.put_object(Bucket=settings.CLOUDFLARE_R2__PHOTO_CACHE_BUCKET_NAME, Key=file_key, Body=bytes(blob), ContentType="image/jpeg")
    
    # Update DB with the new reference
    r2_url = f"{settings.CLOUDFLARE_R2_PHOTO_CACHE_BASE_URL}/{file_key}"
    cur.execute("UPDATE place_photo_cache SET r2_url = %s WHERE id = %s", (r2_url, row_id))

conn.commit()


