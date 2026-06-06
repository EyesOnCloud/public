import joblib
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

print("Loading spam classifier...")
model = joblib.load("/app/model/spam_model.pkl")
print("Model loaded. API ready.")

app = FastAPI(
    title="Spam Email Classifier API",
    description="Detects spam emails using ML — like Gmail does",
    version="1.0.0"
)

class EmailRequest(BaseModel):
    subject : str
    body    : str = ""

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "subject": "Win a FREE iPhone click here now!!!",
                "body"   : "Congratulations you have been selected"
            }]
        }
    }

class BatchRequest(BaseModel):
    emails: list[EmailRequest]

def classify(subject: str, body: str):
    text        = f"{subject} {body}".strip()
    prediction  = model.predict([text])[0]
    proba       = model.predict_proba([text])[0]
    spam_score  = round(float(proba[1]) * 100, 1)
    ham_score   = round(float(proba[0]) * 100, 1)

    if spam_score >= 85:
        verdict = "Definite Spam — block it"
    elif spam_score >= 60:
        verdict = "Likely Spam — move to junk"
    elif spam_score >= 40:
        verdict = "Suspicious — review manually"
    else:
        verdict = "Looks Legitimate"

    return {
        "result"       : "SPAM" if prediction == 1 else "HAM",
        "spam_score"   : spam_score,
        "ham_score"    : ham_score,
        "verdict"      : verdict,
        "timestamp"    : datetime.now().isoformat()
    }

@app.get("/")
def root():
    return {
        "api"      : "Spam Email Classifier",
        "status"   : "running",
        "docs"     : "/docs",
        "endpoints": ["/classify", "/classify/batch", "/health"]
    }

@app.get("/health")
def health():
    return {"status": "healthy", "model": "TF-IDF + Naive Bayes"}

@app.post("/classify")
def classify_email(email: EmailRequest):
    return classify(email.subject, email.body)

@app.post("/classify/batch")
def classify_batch(req: BatchRequest):
    results = []
    for email in req.emails:
        r = classify(email.subject, email.body)
        r["subject"] = email.subject[:60]
        results.append(r)

    spam_count = sum(1 for r in results if r["result"] == "SPAM")
    return {
        "total"      : len(results),
        "spam_count" : spam_count,
        "ham_count"  : len(results) - spam_count,
        "results"    : results
    }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
