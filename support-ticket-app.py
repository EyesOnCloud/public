from flask import Flask, request, jsonify
import joblib
import numpy as np
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [API] %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

MODEL_PATH = "model/ticket_model.pkl"
REQUIRED_FIELDS = [
    "ticket_length",
    "customer_tier",
    "previous_incidents",
    "system_impact_score",
    "affected_users"
]

# Load model at startup — not per-request
logger.info(f"Loading model from {MODEL_PATH}...")
if not os.path.exists(MODEL_PATH):
    logger.error(f"Model file not found at {MODEL_PATH}. Was training run?")
    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

model = joblib.load(MODEL_PATH)
logger.info("Model loaded successfully. API ready.")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "model": "ticket_model",
        "version": "1.0",
        "required_fields": REQUIRED_FIELDS
    })


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)

    # Validate request body exists
    if not data:
        return jsonify({
            "error": "Request body is empty or not valid JSON",
            "required_fields": REQUIRED_FIELDS
        }), 400

    # Validate all required fields present
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        return jsonify({
            "error": f"Missing required fields: {missing}",
            "required_fields": REQUIRED_FIELDS
        }), 400

    # Validate field types are numeric
    for field in REQUIRED_FIELDS:
        if not isinstance(data[field], (int, float)):
            return jsonify({
                "error": f"Field '{field}' must be numeric, got: {type(data[field]).__name__}"
            }), 400

    # Validate no negative values
    non_negative = ["ticket_length", "affected_users",
                    "system_impact_score", "previous_incidents"]
    for field in non_negative:
        if data[field] < 0:
            return jsonify({
                "error": f"Field '{field}' cannot be negative, got: {data[field]}"
            }), 400

    # Build feature vector in training order
    features = np.array([[
        data["ticket_length"],
        data["customer_tier"],
        data["previous_incidents"],
        data["system_impact_score"],
        data["affected_users"]
    ]])

    prediction = model.predict(features)[0]
    probabilities = model.predict_proba(features)[0]

    label = "High Priority" if prediction == 1 else "Low Priority"
    confidence = round(float(probabilities[prediction]) * 100, 2)

    logger.info(
        f"Prediction: {label} | Confidence: {confidence}% | "
        f"Input: ticket_length={data['ticket_length']}, "
        f"customer_tier={data['customer_tier']}, "
        f"system_impact={data['system_impact_score']}, "
        f"affected_users={data['affected_users']}"
    )

    return jsonify({
        "prediction": label,
        "confidence_pct": confidence,
        "priority_code": int(prediction),
        "probabilities": {
            "low_priority": round(float(probabilities[0]) * 100, 2),
            "high_priority": round(float(probabilities[1]) * 100, 2)
        },
        "input_received": data
    })


@app.route("/predict/batch", methods=["POST"])
def predict_batch():
    data = request.get_json(silent=True)
    if not data or "tickets" not in data:
        return jsonify({
            "error": "Request body must contain a 'tickets' array"
        }), 400

    tickets = data["tickets"]
    if not isinstance(tickets, list) or len(tickets) == 0:
        return jsonify({"error": "'tickets' must be a non-empty array"}), 400

    results = []
    for i, ticket in enumerate(tickets):
        missing = [f for f in REQUIRED_FIELDS if f not in ticket]
        if missing:
            results.append({
                "index": i,
                "error": f"Missing fields: {missing}",
                "status": "failed"
            })
            continue

        features = np.array([[
            ticket["ticket_length"],
            ticket["customer_tier"],
            ticket["previous_incidents"],
            ticket["system_impact_score"],
            ticket["affected_users"]
        ]])

        pred = model.predict(features)[0]
        proba = model.predict_proba(features)[0]
        label = "High Priority" if pred == 1 else "Low Priority"

        results.append({
            "index": i,
            "prediction": label,
            "confidence_pct": round(float(proba[pred]) * 100, 2),
            "priority_code": int(pred),
            "status": "success"
        })

    return jsonify({
        "total": len(tickets),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "results": results
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
