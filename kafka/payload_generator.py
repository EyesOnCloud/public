import json
import random
import uuid
from datetime import datetime, timezone

# Realistic data pools — matching what production order systems use
PRODUCTS = [
    {"product_id": "PROD-1001", "name": "Wireless Headphones", "category": "electronics", "price": 149.99},
    {"product_id": "PROD-1002", "name": "Mechanical Keyboard", "category": "electronics", "price": 89.99},
    {"product_id": "PROD-1003", "name": "Standing Desk Mat", "category": "office", "price": 45.00},
    {"product_id": "PROD-1004", "name": "USB-C Cable 2m", "category": "accessories", "price": 12.99},
    {"product_id": "PROD-1005", "name": "Monitor Stand", "category": "office", "price": 199.99},
    {"product_id": "PROD-1006", "name": "Laptop Sleeve 15in", "category": "accessories", "price": 29.99},
    {"product_id": "PROD-1007", "name": "Noise Cancelling Earbuds", "category": "electronics", "price": 229.99},
    {"product_id": "PROD-1008", "name": "Desk Organizer", "category": "office", "price": 34.99},
]

PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "apple_pay", "google_pay"]
REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "ap-northeast-1"]
STATUSES = ["PLACED", "PLACED", "PLACED", "PLACED", "PAYMENT_PENDING"]  # weighted to PLACED

def generate_order_event():
    product = random.choice(PRODUCTS)
    qty = random.randint(1, 4)
    subtotal = round(product["price"] * qty, 2)
    tax = round(subtotal * 0.08, 2)
    shipping = round(random.uniform(0, 15.99), 2)
    total = round(subtotal + tax + shipping, 2)

    order = {
        "order_id": f"ORD-{uuid.uuid4().hex[:12].upper()}",
        "user_id": f"USR-{random.randint(10000, 99999)}",
        "session_id": str(uuid.uuid4()),
        "product_id": product["product_id"],
        "product_name": product["name"],
        "category": product["category"],
        "unit_price": product["price"],
        "quantity": qty,
        "subtotal": subtotal,
        "tax": tax,
        "shipping_fee": shipping,
        "total": total,
        "currency": "USD",
        "payment_method": random.choice(PAYMENT_METHODS),
        "status": random.choice(STATUSES),
        "region": random.choice(REGIONS),
        "placed_at": datetime.now(timezone.utc).isoformat(),
        "source": "web"
    }
    return order

def generate_payload_bytes():
    order = generate_order_event()
    return (
        order["order_id"].encode("utf-8"),
        json.dumps(order).encode("utf-8")
    )

if __name__ == "__main__":
    # Test: generate one payload and show its size
    key, value = generate_payload_bytes()
    print(f"Sample key: {key.decode()}")
    print(f"Sample value size: {len(value)} bytes")
    print(f"Sample value:\n{json.dumps(json.loads(value), indent=2)}")
