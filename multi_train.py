import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import Pipeline

print("=" * 55)
print("   SPAM CLASSIFIER — TRAINING STAGE")
print("=" * 55)

# ── REAL WORLD STYLE TRAINING DATA ───────────────
emails = [
    # SPAM
    ("Win a FREE iPhone now! Click here immediately!!!",              1),
    ("Congratulations you have been selected for $10000 prize",       1),
    ("URGENT: Your account will be suspended click here now",         1),
    ("Buy cheap Viagra online no prescription needed",                1),
    ("Make money fast working from home $5000 per week guaranteed",   1),
    ("You are our lucky winner claim your prize now FREE",            1),
    ("Hot singles in your area are waiting for you click now",        1),
    ("LIMITED OFFER: 90% discount expires tonight act now",           1),
    ("Earn $500 daily from home no experience required",              1),
    ("Your PayPal account has been compromised verify immediately",   1),
    ("FREE medication delivered to your door no prescription",        1),
    ("Investment opportunity guaranteed 300% returns click here",     1),
    ("You won lottery claim $1 million wire transfer details needed", 1),
    ("CLICK NOW exclusive deal for you only expires in 1 hour",       1),
    ("Lose 30 pounds in 30 days miracle pill free trial",             1),
    ("Your credit card approved $50000 limit apply now",              1),
    ("Meet beautiful women tonight free registration",                1),
    ("Urgent account verification required or account deleted",       1),
    ("Work from home $200 per hour no skills required guaranteed",    1),
    ("Claim your free gift card worth $500 limited time offer",       1),
    ("Nigerian prince needs your help transfer $10 million",          1),
    ("You have unclaimed inheritance contact us immediately",         1),
    ("FREE casino chips 1000 bonus spins register now",               1),
    ("Lowest mortgage rates guaranteed apply in 60 seconds",         1),
    ("Your computer has virus call this number immediately",          1),
    # HAM (not spam)
    ("Hey can we reschedule our meeting to 3pm tomorrow?",            0),
    ("Please find the attached quarterly report for your review",     0),
    ("Thanks for dinner last night it was really lovely",             0),
    ("The project deadline has been moved to next Friday",            0),
    ("Can you please review my pull request when you get a chance",   0),
    ("Reminder your dentist appointment is on Thursday at 10am",      0),
    ("The team lunch is confirmed for Wednesday at the usual place",  0),
    ("Your order has been shipped and will arrive in 2 days",         0),
    ("Please submit your timesheet by end of day Friday",             0),
    ("Happy birthday! Hope you have a wonderful day today",           0),
    ("The client meeting has been moved to conference room B",        0),
    ("Can you send me the latest version of the presentation",        0),
    ("Your leave request has been approved enjoy your vacation",      0),
    ("The monthly report is due next Monday please prepare it",       0),
    ("Just checking in how is the new project going so far",          0),
    ("We need to discuss the budget for next quarter please call",    0),
    ("Your flight booking confirmation is attached in this email",    0),
    ("The server maintenance is scheduled for Sunday 2am to 4am",    0),
    ("Please welcome John who is joining our team on Monday",         0),
    ("Your subscription has been renewed thank you for continuing",   0),
    ("The standup meeting is moved from 9am to 10am tomorrow",        0),
    ("Can we get on a quick call to discuss the proposal details",    0),
    ("Your package was delivered and left at the front door today",   0),
    ("The conference registration is now open early bird discount",   0),
    ("Please review and sign the attached contract by Thursday",      0),
]

# Augment dataset — repeat with slight variations
augmented = []
for text, label in emails:
    augmented.append((text, label))
    augmented.append((text.lower(), label))
    augmented.append((text.upper() if label == 1 else text, label))

df = pd.DataFrame(augmented, columns=["text", "label"])
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

print(f"\nDataset size : {len(df)} emails")
print(f"Spam         : {df['label'].sum()}")
print(f"Ham          : {(df['label']==0).sum()}")

# ── TRAIN ─────────────────────────────────────────
X = df["text"]
y = df["label"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Pipeline: TF-IDF vectorizer + Naive Bayes
# This is the industry standard for text classification
pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(
        ngram_range=(1, 2),   # unigrams and bigrams
        max_features=5000,
        stop_words="english"
    )),
    ("clf", MultinomialNB(alpha=0.1))
])

pipeline.fit(X_train, y_train)

preds    = pipeline.predict(X_test)
accuracy = accuracy_score(y_test, preds)

print(f"\n{'='*55}")
print(f"   RESULTS")
print(f"{'='*55}")
print(f"Accuracy : {accuracy * 100:.2f}%")
print(f"\n{classification_report(y_test, preds, target_names=['Ham','Spam'])}")

# ── QUICK SANITY CHECK ────────────────────────────
tests = [
    "Win a FREE iPhone click here now!!!",
    "Can we meet tomorrow at 3pm to discuss the project",
    "URGENT your account suspended verify immediately",
    "Please review the attached report before the meeting",
]
print("Sanity check:")
for t in tests:
    pred  = pipeline.predict([t])[0]
    proba = pipeline.predict_proba([t])[0]
    label = "SPAM" if pred == 1 else "HAM "
    conf  = max(proba) * 100
    print(f"  [{label}] {conf:.0f}%  {t[:55]}")

# ── SAVE ──────────────────────────────────────────
joblib.dump(pipeline, "/app/model/spam_model.pkl")
print(f"\nModel saved to /app/model/spam_model.pkl")
print(f"Model size : {__import__('os').path.getsize('/app/model/spam_model.pkl') / 1024:.1f} KB")
