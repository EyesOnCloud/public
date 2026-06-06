import numpy as np
import pandas as pd
from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

# ── 1. LOAD REAL DATASET ──────────────────────────
# Real California housing data — 20,000+ actual houses
data = fetch_california_housing()
df   = pd.DataFrame(data.data, columns=data.feature_names)
df["price"] = data.target * 100000  # convert to dollars

print("=" * 55)
print("        HOUSE PRICE PREDICTOR")
print("        (California Housing Dataset)")
print("=" * 55)
print(f"\nTotal houses in dataset : {len(df):,}")
print(f"Features used           : {list(df.columns[:-1])}")

print(f"\nSample houses:")
print(df[["MedInc","HouseAge","AveRooms","AveBedrms","price"]].head(6).to_string(index=False))

print(f"\nPrice range:")
print(f"   Cheapest : ${df['price'].min():>12,.0f}")
print(f"   Average  : ${df['price'].mean():>12,.0f}")
print(f"   Most exp : ${df['price'].max():>12,.0f}")

# ── 2. FEATURES & TARGET ──────────────────────────
X = df.drop("price", axis=1)
y = df["price"]

# ── 3. SPLIT ──────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"\nTraining houses : {len(X_train):,}")
print(f"Testing houses  : {len(X_test):,}")

# ── 4. SCALE ──────────────────────────────────────
scaler  = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test  = scaler.transform(X_test)

# ── 5. TRAIN ──────────────────────────────────────
print("\n Training model on real housing data...")
model = RandomForestRegressor(
    n_estimators=100,
    random_state=42,
    n_jobs=-1        # use all CPU cores — faster
)
model.fit(X_train, y_train)
print("   Done.")

# ── 6. EVALUATE ───────────────────────────────────
preds = model.predict(X_test)
mae   = mean_absolute_error(y_test, preds)
r2    = r2_score(y_test, preds)

print("\n" + "=" * 55)
print("        MODEL RESULTS")
print("=" * 55)
print(f"\nR² Score (accuracy)    : {r2:.4f}  (1.0 = perfect)")
print(f"Avg prediction error   : ${mae:,.0f}")
print(f"   (model is off by ~${mae:,.0f} on average)")

# show 8 actual vs predicted side by side
print(f"\nSample Predictions vs Actual:")
print(f"   {'Actual Price':>15}  {'Predicted':>15}  {'Difference':>12}")
print(f"   {'-'*15}  {'-'*15}  {'-'*12}")
for actual, pred in zip(list(y_test[:8]), preds[:8]):
    diff = pred - actual
    sign = "+" if diff > 0 else ""
    print(f"   ${actual:>14,.0f}  ${pred:>14,.0f}  {sign}${diff:>10,.0f}")

# ── 7. FEATURE IMPORTANCE ─────────────────────────
print(f"\nWhat drives house prices the most:")
importances = pd.Series(
    model.feature_importances_,
    index=data.feature_names
).sort_values(ascending=False)

labels = {
    "MedInc"    : "Median income in area",
    "AveRooms"  : "Avg rooms per house",
    "HouseAge"  : "Age of the house",
    "Latitude"  : "Location (North/South)",
    "Longitude" : "Location (East/West)",
    "AveBedrms" : "Avg bedrooms",
    "Population": "Neighborhood population",
    "AveOccup"  : "Avg people per house",
}

for feat, score in importances.items():
    bar = "█" * int(score * 60)
    print(f"   {labels[feat]:<30} {bar}  {score:.3f}")

# ── 8. PREDICT YOUR OWN HOUSE ─────────────────────
print("\n" + "=" * 55)
print("   PREDICT PRICE FOR SPECIFIC HOUSES")
print("=" * 55)

# Feature order: MedInc, HouseAge, AveRooms, AveBedrms,
#                Population, AveOccup, Latitude, Longitude
houses = [
    {
        "label"      : "Small older house, low income area",
        "features"   : [2.5, 40, 4.0, 1.1, 800, 3.0, 34.05, -118.25],
    },
    {
        "label"      : "Modern spacious house, good area",
        "features"   : [6.5, 10, 7.0, 1.5, 500, 2.5, 37.77, -122.41],
    },
    {
        "label"      : "Luxury house, high income area",
        "features"   : [12.0, 5, 10.0, 2.0, 200, 2.0, 37.85, -122.25],
    },
]

for house in houses:
    raw     = np.array([house["features"]])
    scaled  = scaler.transform(raw)
    price   = model.predict(scaled)[0]
    print(f"\n   {house['label']}")
    print(f"      Estimated price : ${price:,.0f}")
