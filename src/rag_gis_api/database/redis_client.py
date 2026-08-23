from redis.asyncio import Redis

from rag_gis_api import REDIS_URL

redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
