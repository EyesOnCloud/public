import os
import json
import hashlib
import joblib
import redis
import psycopg2
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime

# ── LOAD MODEL ────────────────────────────────────
print("Loading sentiment model...")
model = joblib.load("/app/model/sentiment_model.pkl")
print("Model loaded.")

# ── CONNECT REDIS ─────────────────────────────────
print("Connecting to Redis...")
cache = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)
cache.ping()
print("Redis connected.")

# ── CONNECT POSTGRES ──────────────────────────────
print("Connecting to PostgreSQL...")
def get_db():
    return psycopg2.connect(
        host     = os.getenv("POSTGRES_HOST", "postgres"),
        port     = int(os.getenv("POSTGRES_PORT", 5432)),
        dbname   = os.getenv("POSTGRES_DB",   "reviewsdb"),
        user     = os.getenv("POSTGRES_USER", "admin"),
        password = os.getenv("POSTGRES_PASSWORD", "secret123")
    )

# Create table if not exists
conn = get_db()
cur  = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id          SERIAL PRIMARY KEY,
        review_text TEXT NOT NULL,
        sentiment   VARCHAR(10),
        positive_pct FLOAT,
        negative_pct FLOAT,
        source      VARCHAR(20),
        created_at  TIMESTAMP DEFAULT NOW()
    )
""")
conn.commit()
cur.close()
conn.close()
print("PostgreSQL connected. Table ready.")

# ── APP ───────────────────────────────────────────
app = FastAPI(
    title="Sentiment Analysis API",
    description="Product review sentiment — API + Redis + PostgreSQL",
    version="1.0.0"
)

# ── SCHEMAS ───────────────────────────────────────
class ReviewRequest(BaseModel):
    review: str
    product_id: str = "unknown"

class BatchRequest(BaseModel):
    reviews: list[ReviewRequest]

# ── HELPER ────────────────────────────────────────
def analyze(text: str) -> dict:
    pred  = model.predict([text])[0]
    proba = model.predict_proba([text])[0]
    pos   = round(float(proba[1]) * 100, 1)
    neg   = round(float(proba[0]) * 100, 1)

    if pos >= 80:
        verdict = " Very Positive"
    elif pos >= 60:
        verdict = " Mostly Positive"
    elif pos >= 40:
        verdict = " Neutral / Mixed"
    elif pos >= 20:
        verdict = " Mostly Negative"
    else:
        verdict = " Very Negative"

    return {
        "sentiment"    : "POSITIVE" if pred == 1 else "NEGATIVE",
        "positive_pct" : pos,
        "negative_pct" : neg,
        "verdict"      : verdict
    }

# ── ROUTES ────────────────────────────────────────
@app.get("/")
def root():
    return {
        "api"      : "Sentiment Analysis API",
        "services" : ["FastAPI", "Redis", "PostgreSQL"],
        "docs"     : "/docs"
    }

@app.get("/health")
def health():
    # Check all 3 services
    services = {}

    try:
        cache.ping()
        services["redis"] = "healthy"
    except:
        services["redis"] = "unreachable"

    try:
        conn = get_db()
        conn.close()
        services["postgres"] = "healthy"
    except:
        services["postgres"] = "unreachable"

    services["api"] = "healthy"
    return {
        "status"   : "healthy",
        "services" : services,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/analyze")
def analyze_review(req: ReviewRequest):
    # ── Step 1: Check Redis cache first ───────────
    cache_key = f"review:{hashlib.md5(req.review.encode()).hexdigest()}"
    cached    = cache.get(cache_key)

    if cached:
        result         = json.loads(cached)
        result["source"] = "cache"
        result["cache_hit"] = True
        return result

    # ── Step 2: Run ML model ───────────────────────
    result = analyze(req.review)

    # ── Step 3: Save to PostgreSQL ─────────────────
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO reviews
                (review_text, sentiment, positive_pct, negative_pct, source)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            req.review,
            result["sentiment"],
            result["positive_pct"],
            result["negative_pct"],
            "api"
        ))
        row_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        result["review_id"] = row_id
    except Exception as e:
        result["db_error"] = str(e)

    # ── Step 4: Cache in Redis (10 min TTL) ────────
    cache.setex(cache_key, 600, json.dumps(result))

    result["source"]    = "model"
    result["cache_hit"] = False
    result["timestamp"] = datetime.now().isoformat()
    return result


@app.post("/analyze/batch")
def analyze_batch(req: BatchRequest):
    results = []
    for item in req.reviews:
        r = analyze_review(item)
        r["review"] = item.review[:60]
        results.append(r)

    pos = sum(1 for r in results if r["sentiment"] == "POSITIVE")
    neg = len(results) - pos
    return {
        "total"    : len(results),
        "positive" : pos,
        "negative" : neg,
        "summary"  : f"{pos} positive, {neg} negative out of {len(results)} reviews",
        "results"  : results
    }


@app.get("/history")
def get_history(limit: int = 10):
    """Fetch last N reviews from PostgreSQL"""
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, review_text, sentiment,
                   positive_pct, created_at
            FROM reviews
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return {
            "total_fetched": len(rows),
            "reviews": [
                {
                    "id"          : r[0],
                    "review"      : r[1][:80],
                    "sentiment"   : r[2],
                    "positive_pct": r[3],
                    "created_at"  : str(r[4])
                }
                for r in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
def get_stats():
    """Aggregated stats from PostgreSQL + Redis info"""
    try:
        conn = get_db()
        cur  = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM reviews")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM reviews WHERE sentiment='POSITIVE'")
        pos = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM reviews WHERE sentiment='NEGATIVE'")
        neg = cur.fetchone()[0]

        cur.execute("SELECT AVG(positive_pct) FROM reviews")
        avg_pos = round(float(cur.fetchone()[0] or 0), 1)

        cur.close()
        conn.close()

        redis_keys = cache.dbsize()

        return {
            "database": {
                "total_reviews"   : total,
                "positive"        : pos,
                "negative"        : neg,
                "avg_positive_pct": avg_pos
            },
            "cache": {
                "cached_results": redis_keys
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache/clear")
def clear_cache():
    cache.flushdb()
    return {"message": "Cache cleared", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
