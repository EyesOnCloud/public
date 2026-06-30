#!/usr/bin/env python3
"""
Payment Producer Service
Publishes Avro-serialized payment events to Kafka topic: payments
Schema registered and enforced via Confluent Schema Registry.

Environment variables:
  BOOTSTRAP_SERVERS   (default: kafka-1:9092,kafka-2:9092,kafka-3:9092)
  SCHEMA_REGISTRY_URL (default: http://kafka-1:8081)
"""

import json
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


def load_schema(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def delivery_report(err, msg):
    if err is not None:
        print(f"[ERROR] Delivery failed: {err}")
    else:
        key = msg.key() if msg.key() else b""
        print(
            f"[OK] payment_id={key.decode()} "
            f"partition={msg.partition()} offset={msg.offset()}"
        )


def generate_payment() -> dict:
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
    }


def payment_to_dict(payment: dict, ctx) -> dict:
    """
    Serialization context callback required by AvroSerializer.
    Returns the dict as-is — fields already match schema.
    """
    return payment


def main():
    print(f"[CONFIG] Bootstrap      : {BOOTSTRAP_SERVERS}")
    print(f"[CONFIG] Schema Registry: {SCHEMA_REGISTRY_URL}")

    schema_str = load_schema("payment.avsc")

    schema_registry_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})

    avro_serializer = AvroSerializer(
        schema_registry_client,
        schema_str,
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

    print(f"[START] Publishing Avro payments to '{TOPIC}'. Ctrl+C to stop.\n")

    try:
        while True:
            payment = generate_payment()
            producer.produce(
                topic    = TOPIC,
                key      = payment["payment_id"],
                value    = payment,
                on_delivery = delivery_report,
            )
            producer.poll(0)
            time.sleep(random.uniform(0.5, 2.0))

    except KeyboardInterrupt:
        print("\n[STOP] Flushing...")
    finally:
        producer.flush(timeout=15)
        print("[DONE] Producer shut down cleanly.")


if __name__ == "__main__":
    main()
