#!/usr/bin/env python3
"""
Order Producer Service
Simulates e-commerce order events → publishes to raw-orders topic.
Bootstrap servers read from env var BOOTSTRAP_SERVERS (default: lab cluster).
"""

import json
import os
import random
import time
import uuid
from datetime import datetime

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

BOOTSTRAP_SERVERS = os.environ.get(
    "BOOTSTRAP_SERVERS", "192.168.100.21:9092,192.168.100.22:9092,192.168.100.23:9092"
)
TOPIC = "raw-orders"

PRODUCTS = [
    {"id": "P001", "name": "Laptop",        "price": 1200.00, "category": "electronics"},
    {"id": "P002", "name": "Headphones",    "price": 150.00,  "category": "electronics"},
    {"id": "P003", "name": "Desk Chair",    "price": 350.00,  "category": "furniture"},
    {"id": "P004", "name": "Monitor",       "price": 400.00,  "category": "electronics"},
    {"id": "P005", "name": "Keyboard",      "price": 80.00,   "category": "electronics"},
    {"id": "P006", "name": "Notebook",      "price": 5.00,    "category": "stationery"},
    {"id": "P007", "name": "Webcam",        "price": 90.00,   "category": "electronics"},
    {"id": "P008", "name": "Standing Desk", "price": 600.00,  "category": "furniture"},
]

CUSTOMERS = [f"CUST_{str(i).zfill(4)}" for i in range(1, 21)]
REGIONS   = ["us-east", "us-west", "eu-central", "ap-south", "ap-east"]
STATUSES  = ["placed", "confirmed", "processing", "shipped", "delivered", "cancelled"]


def delivery_report(err, msg):
    if err is not None:
        print(f"[ERROR] Delivery failed: {err}")
    else:
        print(
            f"[OK] order_id={json.loads(msg.value())['order_id']} "
            f"partition={msg.partition()} offset={msg.offset()}"
        )


def create_topic_if_not_exists():
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})
    existing = admin.list_topics(timeout=10).topics
    if TOPIC not in existing:
        new_topic = NewTopic(TOPIC, num_partitions=3, replication_factor=3)
        futures = admin.create_topics([new_topic])
        for t, f in futures.items():
            try:
                f.result()
                print(f"[INFO] Topic '{t}' created.")
            except Exception as e:
                print(f"[WARN] Topic already exists or creation error: {e}")
    else:
        print(f"[INFO] Topic '{TOPIC}' already exists. Skipping creation.")


def generate_order():
    product  = random.choice(PRODUCTS)
    quantity = random.randint(1, 5)
    return {
        "order_id":     str(uuid.uuid4()),
        "customer_id":  random.choice(CUSTOMERS),
        "product_id":   product["id"],
        "product_name": product["name"],
        "category":     product["category"],
        "quantity":     quantity,
        "unit_price":   product["price"],
        "total_amount": round(product["price"] * quantity, 2),
        "status":       random.choices(
                            STATUSES,
                            weights=[30, 25, 20, 15, 5, 5],
                            k=1
                        )[0],
        "region":       random.choice(REGIONS),
        "timestamp":    datetime.utcnow().isoformat() + "Z",
    }


def main():
    print(f"[CONFIG] Bootstrap servers: {BOOTSTRAP_SERVERS}")
    create_topic_if_not_exists()

    producer = Producer({
        "bootstrap.servers":  BOOTSTRAP_SERVERS,
        "acks":               "all",
        "enable.idempotence": True,
        "compression.type":   "snappy",
        "linger.ms":          5,
        "batch.size":         16384,
    })

    print(f"[START] Publishing to '{TOPIC}'. Ctrl+C to stop.\n")
    try:
        while True:
            order    = generate_order()
            key      = order["customer_id"]
            value    = json.dumps(order)
            producer.produce(
                topic    = TOPIC,
                key      = key.encode("utf-8"),
                value    = value.encode("utf-8"),
                callback = delivery_report,
            )
            producer.poll(0)
            time.sleep(random.uniform(0.5, 2.0))
    except KeyboardInterrupt:
        print("\n[STOP] Flushing remaining messages...")
    finally:
        producer.flush(timeout=15)
        print("[DONE] Producer shut down cleanly.")


if __name__ == "__main__":
    main()
