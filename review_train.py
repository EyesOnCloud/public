import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

print("=" * 55)
print("   SENTIMENT ANALYSIS — TRAINING")
print("=" * 55)

# ── PRODUCT REVIEW TRAINING DATA ──────────────────
reviews = [
    # POSITIVE — label 1
    ("This product is absolutely amazing highly recommend it",           1),
    ("Excellent quality fast delivery very happy with purchase",         1),
    ("Best product I have ever bought works perfectly",                  1),
    ("Outstanding quality exceeded my expectations will buy again",      1),
    ("Superb product great value for money totally satisfied",           1),
    ("Love this product it works exactly as described perfect",          1),
    ("Fantastic quality and great packaging arrived on time",            1),
    ("Very happy with this purchase great quality product",              1),
    ("Brilliant product does exactly what it says five stars",           1),
    ("Highly recommended amazing product great customer service",        1),
    ("Perfect product fast shipping excellent build quality",            1),
    ("Great value product works flawlessly very satisfied customer",     1),
    ("Wonderful product loved it will definitely order again soon",      1),
    ("Top quality item arrived quickly packaging was excellent",         1),
    ("Impressive product very well made durable and looks great",        1),
    ("Delighted with this purchase everything was as described",         1),
    ("Superb item arrived in perfect condition exactly as shown",        1),
    ("Excellent purchase very happy recommended to all my friends",      1),
    ("Great product sturdy well built performs exactly as expected",     1),
    ("Love it perfect size works great highly recommend buying",         1),
    # NEGATIVE — label 0
    ("Terrible product broke after one day complete waste of money",     0),
    ("Very disappointed quality is awful nothing like description",      0),
    ("Worst purchase ever complete garbage do not buy this",             0),
    ("Poor quality product stopped working after two days",              0),
    ("Horrible experience product arrived damaged not as described",     0),
    ("Waste of money product is cheap and poorly made avoid",            0),
    ("Very bad quality returned it immediately total disappointment",    0),
    ("Do not buy this product it is completely useless junk",            0),
    ("Awful product broke immediately cheap material very bad",          0),
    ("Terrible quality nothing like the photos complete scam",           0),
    ("Disappointed product feels cheap and flimsy not worth it",         0),
    ("Bad product stopped working after first use very poor quality",    0),
    ("Rubbish product does not work as advertised waste of money",       0),
    ("Very unhappy with this product poor build quality avoid it",       0),
    ("Horrible product arrived broken customer service was useless",     0),
    ("Cheap and nasty product looks nothing like pictures avoid",        0),
    ("Total waste of money product arrived damaged and unusable",        0),
    ("Dreadful quality product feels like it will break any moment",     0),
    ("Not worth the money very poor quality would not recommend",        0),
    ("Absolute rubbish broke on first day complete waste avoid",         0),
]

# Augment
augmented = []
for text, label in reviews:
    augmented.append((text, label))
    augmented.append((text.lower(), label))

df = pd.DataFrame(augmented, columns=["text", "label"])
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

print(f"Training samples  : {len(df)}")
print(f"Positive reviews  : {df['label'].sum()}")
print(f"Negative reviews  : {(df['label']==0).sum()}")

X_train, X_test, y_train, y_test = train_test_split(
    df["text"], df["label"],
    test_size=0.2, random_state=42, stratify=df["label"]
)

pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=3000,
        stop_words="english"
    )),
    ("clf", LogisticRegression(max_iter=1000, random_state=42))
])

pipeline.fit(X_train, y_train)
preds    = pipeline.predict(X_test)
accuracy = accuracy_score(y_test, preds)

print(f"\nAccuracy : {accuracy * 100:.2f}%")
print(classification_report(y_test, preds,
      target_names=["Negative", "Positive"]))

# Sanity check
tests = [
    "This product is absolutely amazing love it",
    "Terrible product broke after one day avoid",
    "Good quality fast delivery happy with purchase",
    "Worst purchase ever complete waste of money",
]
print("Sanity check:")
for t in tests:
    pred  = pipeline.predict([t])[0]
    proba = pipeline.predict_proba([t])[0]
    label = "POS" if pred == 1 else "NEG"
    print(f"  [{label}] {max(proba)*100:.0f}%  {t[:50]}")

joblib.dump(pipeline, "/app/model/sentiment_model.pkl")
print("\nModel saved to /app/model/sentiment_model.pkl")
