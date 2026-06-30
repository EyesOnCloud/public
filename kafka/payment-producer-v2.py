#!/usr/bin/env python3
"""
Payment Producer V2 Service
Publishes Avro payments using SCHEMA V2 (adds fraud_score field).
Runs ALONGSIDE producer.py (v1) on the same topic: payments
Demonstrates schema evolution — v1 and v2 producers coexist without breaking consumers.

Environment variables:
  BOOTSTRAP_SERVERS   (default: kafka-1:9092,kafka-2:9092,kafka-3:9092)
  SCHEMA_REGISTRY_URL (default: http://kafka-3:8081)
"""

import os
import random
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer

BOOTSTRAP_SERVERS   = os.environ.get("BOOTSTRAP_SERVERS",   "192.168.100.21:9092,192.168.100.22:9092,192.168.100.23:9092")
SCHEMA_REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://192.168.100.21:8081")
TOPIC               = "payments"

CUSTOMERS = [f"CUST_{str(i).zfill(4)}" for i in range(1, 21)]
MERCHANTS = [f"MERCH_{str(i).zfill(3)}" for i in range(1, 11)]
REGIONS   = ["us-east", "us-west", "eu-central", "ap-south", "ap-east"]
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD"]

PAYMENT_METHODS = ["CREDIT_CARD", "DEBIT_CARD", "BANK_TRANSFER", "DIGITAL_WALLET"]
STATUSES        = ["INITIATED", "PROCESSING", "COMPLETED", "FAILED", "REFUNDED"]
STATUS_WEIGHTS  = [20, 25, 40, 10, 5]

DEVICE_TYPES = ["mobile", "desktop", "tablet", "pos_terminal"]

# SCHEMA V2 — adds fraud_score field with default (BACKWARD compatible)
SCHEMA_V2_STR = """
{
  "type": "record",
  "name": "Payment",
  "namespace": "com.lab16.payments",
  "doc": "Payment transaction event for order processing - V2 adds fraud_score",
  "fields": [
    {"name": "payment_id", "type": "string"},
    {"name": "order_id", "type": "string"},
    {"name": "customer_id", "type": "string"},
    {"name": "amount", "type": "double"},
    {"name": "currency", "type": "string"},
    {"name": "payment_method", "type": {"type": "enum", "name": "PaymentMethod",
      "symbols": ["CREDIT_CARD", "DEBIT_CARD", "BANK_TRANSFER", "DIGITAL_WALLET"]}},
    {"name": "status", "type": {"type": "enum", "name": "PaymentStatus",
      "symbols": ["INITIATED", "PROCESSING", "COMPLETED", "FAILED", "REFUNDED"]}},
    {"name": "merchant_id", "type": "string"},
    {"name": "region", "type": "string"},
    {"name": "timestamp_ms", "type": "long"},
    {"name": "metadata", "type": {"type": "map", "values": "string"}, "default": {}},
    {"name": "fraud_score", "type": "double", "default": 0.0,
      "doc": "ML fraud score 0.0-1.0, default 0.0 for unscored"}
  ]
}
"""


def delivery_report(err, msg):
    if err is not None:
        print(f"[ERROR] Delivery failed: {err}")
    else:
        key = msg.key() if msg.key() else b""
        print(
            f"[OK-V2] payment_id={key.decode()} fraud_score=included "
            f"partition={msg.partition()} offset={msg.offset()}"
        )


def generate_payment_v2() -> dict:
    amount = round(random.uniform(5.00, 5000.00), 2)
    return {
        "payment_id":     str(uuid.uuid4()),
        "order_id":       str(uuid.uuid4()),
        "customer_id":    random.choice(CUSTOMERS),
        "amount":         amount,
        "currency":       random.choice(CURRENCIES),
        "payment_method": random.choice(PAYMENT_METHODS),
        "status":         random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0],
        "merchant_id":    random.choice(MERCHANTS),
        "region":         random.choice(REGIONS),
        "timestamp_ms":   int(datetime.now(timezone.utc).timestamp() * 1000),
        "metadata": {
            "device_type": random.choice(DEVICE_TYPES),
            "ip_hash":     uuid.uuid4().hex[:16],
            "sdk_version": "2.1.0",
        },
        "fraud_score": round(random.uniform(0.0, 1.0), 4),
    }


def payment_to_dict(payment: dict, ctx) -> dict:
    return payment


def main():
    print(f"[CONFIG] Bootstrap      : {BOOTSTRAP_SERVERS}")
    print(f"[CONFIG] Schema Registry: {SCHEMA_REGISTRY_URL}")
    print(f"[CONFIG] Schema version : V2 (includes fraud_score)")

    schema_registry_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})

    avro_serializer = AvroSerializer(
        schema_registry_client,
        SCHEMA_V2_STR,
        payment_to_dict,
    )

    producer = SerializingProducer({
        "bootstrap.servers":  BOOTSTRAP_SERVERS,
        "acks":               "all",
        "enable.idempotence": True,
        "compression.type":   "snappy",
        "linger.ms":          5,
        "key.serializer":     StringSerializer("utf_8"),
        "value.serializer":   avro_serializer,
    })

    print(f"[START] Publishing Avro V2 payments to '{TOPIC}'. Ctrl+C to stop.\n")

    try:
        while True:
            payment = generate_payment_v2()
            producer.produce(
                topic       = TOPIC,
                key         = payment["payment_id"],
                value       = payment,
                on_delivery = delivery_report,
            )
            producer.poll(0)
            time.sleep(random.uniform(0.5, 2.0))

    except KeyboardInterrupt:
        print("\n[STOP] Flushing...")
    finally:
        producer.flush(timeout=15)
        print("[DONE] Producer V2 shut down cleanly.")


if __name__ == "__main__":
    main()
