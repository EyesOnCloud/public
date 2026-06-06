import numpy as np
import pandas as pd
import joblib
import os
import json
import time
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score

# ── PATHS ─────────────────────────────────────────
RAW_DATA    = "/app/data/house_raw.csv"
PROCESSED   = "/app/outputs/processed/house_clean.csv"
MODEL_PATH  = "/app/outputs/models/house_model.pkl"
METRICS     = "/app/outputs/models/metrics.json"
LOG_PATH    = "/app/outputs/logs/training.log"

# ── LOGGER ────────────────────────────────────────
os.makedirs("/app/outputs/processed", exist_ok=True)
os.makedirs("/app/outputs/models",    exist_ok=True)
os.makedirs("/app/outputs/logs",      exist_ok=True)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")

# ─────────────────────────────────────────────────
# STAGE 1 — LOAD RAW DATA
# ─────────────────────────────────────────────────
print("=" * 55)
print("   HOUSE PRICE MODEL")
print("=" * 55)

log("STAGE 1: Loading raw data")
df = pd.read_csv(RAW_DATA)
log(f"  Loaded {len(df)} rows, {df.shape[1]} columns")
log(f"  Columns: {list(df.columns)}")

# ─────────────────────────────────────────────────
# STAGE 2 — PREPROCESSING
# ─────────────────────────────────────────────────
log("STAGE 2: Preprocessing")

# Check missing values
missing = df.isnull().sum().sum()
log(f"  Missing values found: {missing}")

# Encode categorical columns
le_location  = LabelEncoder()
le_condition = LabelEncoder()
df["location_enc"]  = le_location.fit_transform(df["location"])
df["condition_enc"] = le_condition.fit_transform(df["condition"])

log(f"  Locations encoded : {list(le_location.classes_)}")
log(f"  Conditions encoded: {list(le_condition.classes_)}")

# Add engineered features
df["price_per_sqft"] = df["price"] / df["sqft"]
df["room_total"]     = df["bedrooms"] + df["bathrooms"]
log("  Feature engineering done: price_per_sqft, room_total")

# Save processed data
df.to_csv(PROCESSED, index=False)
log(f"  Processed data saved → {PROCESSED}")

print(f"\nProcessed Dataset Sample:")
print(df[["id","bedrooms","sqft","location","condition","price"]].to_string(index=False))

# ─────────────────────────────────────────────────
# STAGE 3 — TRAIN MODEL
# ─────────────────────────────────────────────────
log("STAGE 3: Training model")

features = ["bedrooms","bathrooms","sqft","age_years",
            "location_enc","condition_enc","room_total"]
X = df[features]
y = df["price"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
log(f"  Train size: {len(X_train)}  Test size: {len(X_test)}")

start = time.time()
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
duration = round(time.time() - start, 2)
log(f"  Training completed in {duration}s")

# ─────────────────────────────────────────────────
# STAGE 4 — EVALUATE
# ─────────────────────────────────────────────────
log("STAGE 4: Evaluating model")

preds = model.predict(X_test)
mae   = mean_absolute_error(y_test, preds)
r2    = r2_score(y_test, preds)

log(f"  R² Score : {r2:.4f}")
log(f"  MAE      : ₹{mae:,.0f}")

print(f"\n{'='*55}")
print(f"   RESULTS")
print(f"{'='*55}")
print(f"\nR² Score  : {r2:.4f}  (1.0 = perfect)")
print(f"Avg Error : ₹{mae:,.0f}")

print(f"\nActual vs Predicted:")
print(f"   {'House':<8} {'Actual':>14} {'Predicted':>14} {'Diff':>12}")
print(f"   {'-'*8} {'-'*14} {'-'*14} {'-'*12}")
for i, (actual, pred) in enumerate(zip(y_test, preds)):
    house_id = df.iloc[y_test.index[i]]["id"]
    diff     = pred - actual
    sign     = "+" if diff > 0 else ""
    print(f"   {house_id:<8} ₹{actual:>12,.0f} ₹{pred:>12,.0f} {sign}₹{diff:>9,.0f}")

# ─────────────────────────────────────────────────
# STAGE 5 — SAVE MODEL ARTIFACT
# ─────────────────────────────────────────────────
log("STAGE 5: Saving model artifact")

joblib.dump(model, MODEL_PATH)
model_size = os.path.getsize(MODEL_PATH)
log(f"  Model saved → {MODEL_PATH}")
log(f"  Model size  : {model_size / 1024:.1f} KB")

# Save metrics as JSON
metrics = {
    "trained_at"    : datetime.now().isoformat(),
    "r2_score"      : round(r2, 4),
    "mae"           : round(mae, 2),
    "train_samples" : len(X_train),
    "test_samples"  : len(X_test),
    "features"      : features,
    "training_time" : duration
}
with open(METRICS, "w") as f:
    json.dump(metrics, f, indent=2)
log(f"  Metrics saved → {METRICS}")

# ─────────────────────────────────────────────────
# STAGE 6 — FEATURE IMPORTANCE
# ─────────────────────────────────────────────────
print(f"\nFeature Importance:")
importances = pd.Series(
    model.feature_importances_, index=features
).sort_values(ascending=False)

for feat, score in importances.items():
    bar = "█" * int(score * 60)
    print(f"   {feat:<15} {bar}  {score:.3f}")

# ─────────────────────────────────────────────────
# STAGE 7 — PREDICT NEW HOUSE
# ─────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"   PREDICT A NEW HOUSE")
print(f"{'='*55}")

new_house = pd.DataFrame([{
    "bedrooms"      : 3,
    "bathrooms"     : 2,
    "sqft"          : 1400,
    "age_years"     : 5,
    "location_enc"  : le_location.transform(["Mumbai"])[0],
    "condition_enc" : le_condition.transform(["good"])[0],
    "room_total"    : 5
}])

predicted_price = model.predict(new_house)[0]
print(f"\n   3 BHK | 1400 sqft | Mumbai | Good condition")
print(f"   Estimated Price : ₹{predicted_price:,.0f}")
log(f"  New house prediction: ₹{predicted_price:,.0f}")

log("PIPELINE COMPLETE")
print(f"\n{'='*55}")
print(f"   ALL OUTPUTS SAVED")
print(f"{'='*55}")
print(f"   Processed data → outputs/processed/house_clean.csv")
print(f"   Trained model  → outputs/models/house_model.pkl")
print(f"   Metrics JSON   → outputs/models/metrics.json")
print(f"   Training log   → outputs/logs/training.log")
