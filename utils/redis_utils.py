import redis
import sys
from systemd import journal

def db_connect(dbhost, dbnum):
    try:
        redis_db = redis.StrictRedis(host=dbhost, port=6379, db=str(dbnum), charset="utf-8", decode_responses=True)
        redis_db.ping()
        return redis_db
    except Exception as e:
        error = f"Can't connect to RedisDB host: {dbhost} ({e})"
        journal.send(error)
        sys.exit(error)
