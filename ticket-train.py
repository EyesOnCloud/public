import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [TRAIN] %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

DATASET_PATH = "support_tickets.csv"
MODEL_DIR = "model"
MODEL_PATH = os.path.join(MODEL_DIR, "ticket_model.pkl")
FEATURES = ["ticket_length", "customer_tier", "previous_incidents",
            "system_impact_score", "affected_users"]
TARGET = "priority"
NON_NEGATIVE_FIELDS = ["ticket_length", "affected_users",
                        "system_impact_score", "previous_incidents"]

# ── 1. Load ────────────────────────────────────────────────────────────────
logger.info(f"Loading dataset from {DATASET_PATH}")
df = pd.read_csv(DATASET_PATH)
logger.info(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")

# ── 2. Validate ────────────────────────────────────────────────────────────
logger.info("Running data validation...")
validation_passed = True

# Missing values
missing = df.isnull().sum()
if missing.any():
    logger.error(f"Missing values detected:\n{missing[missing > 0]}")
    validation_passed = False
else:
    logger.info("Missing values check: PASSED (0 missing)")

# Duplicates
dupes = df.duplicated().sum()
if dupes > 0:
    logger.error(f"Duplicate rows detected: {dupes}")
    validation_passed = False
else:
    logger.info(f"Duplicate rows check: PASSED (0 duplicates)")

# Negative values in fields that must be non-negative
for field in NON_NEGATIVE_FIELDS:
    neg_count = (df[field] < 0).sum()
    if neg_count > 0:
        logger.error(f"Negative values in '{field}': {neg_count} rows")
        validation_passed = False
    else:
        logger.info(f"Negative values check '{field}': PASSED")

# Class balance check
class_counts = df[TARGET].value_counts()
logger.info(f"Class distribution:\n{class_counts.to_string()}")
minority_pct = class_counts.min() / class_counts.sum() * 100
if minority_pct < 20:
    logger.warning(
        f"Class imbalance detected. Minority class is {minority_pct:.1f}% of data. "
        "Consider resampling or adjusting class weights."
    )

if not validation_passed:
    logger.error("Validation FAILED. Aborting training.")
    sys.exit(1)

logger.info("All validation checks PASSED. Proceeding to training.")

# ── 3. Prepare features ────────────────────────────────────────────────────
X = df[FEATURES]
y = df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
logger.info(f"Train size: {len(X_train)} | Test size: {len(X_test)}")

# ── 4. Train ───────────────────────────────────────────────────────────────
logger.info("Training RandomForestClassifier...")
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=6,
    min_samples_split=2,
    random_state=42
)
model.fit(X_train, y_train)
logger.info("Training complete.")

# ── 5. Evaluate ────────────────────────────────────────────────────────────
train_acc = accuracy_score(y_train, model.predict(X_train))
test_acc = accuracy_score(y_test, model.predict(X_test))

logger.info(f"Train Accuracy : {train_acc * 100:.2f}%")
logger.info(f"Test Accuracy  : {test_acc * 100:.2f}%")
logger.info(f"\nClassification Report (Test Set):\n"
            f"{classification_report(y_test, model.predict(X_test), target_names=['Low Priority','High Priority'])}")

# ── 6. Diagnose fit ────────────────────────────────────────────────────────
gap = train_acc - test_acc
if train_acc < 0.80:
    diagnosis = "UNDERFITTING — model is too simple; train accuracy itself is low."
elif gap > 0.15:
    diagnosis = (f"OVERFITTING — train accuracy ({train_acc*100:.1f}%) is significantly "
                 f"higher than test accuracy ({test_acc*100:.1f}%). "
                 f"Gap: {gap*100:.1f}%. Consider more data, pruning, or regularization.")
else:
    diagnosis = (f"GENERALIZING WELL — train ({train_acc*100:.1f}%) and "
                 f"test ({test_acc*100:.1f}%) accuracies are close. Gap: {gap*100:.1f}%.")

logger.info(f"Model Diagnosis: {diagnosis}")

# ── 7. Feature importance ──────────────────────────────────────────────────
importances = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
logger.info(f"Feature Importances:\n{importances.to_string()}")

# ── 8. Save ────────────────────────────────────────────────────────────────
os.makedirs(MODEL_DIR, exist_ok=True)
joblib.dump(model, MODEL_PATH)
logger.info(f"Model saved to {MODEL_PATH}")
