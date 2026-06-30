#!/usr/bin/env python3
"""
Payment Consumer Service
Deserializes Avro payment events from topic: payments
Schema fetched automatically from Schema Registry using embedded schema ID.

Environment variables:
  BOOTSTRAP_SERVERS   (default: kafka-1:9092,kafka-2:9092,kafka-3:9092)
  SCHEMA_REGISTRY_URL (default: http://kafka-3:8081)
"""

import os
import signal
import sys
from datetime import datetime, timezone

from confluent_kafka import DeserializingConsumer, KafkaError, KafkaException
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer

BOOTSTRAP_SERVERS   = os.environ.get("BOOTSTRAP_SERVERS",   "192.168.100.21:9092,192.168.100.22:9092,192.168.100.23:9092")
SCHEMA_REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://192.168.100.21:8081")
TOPIC               = "payments"
GROUP_ID            = "payment-processor-group"

running = True


def signal_handler(sig, frame):
    global running
    print("\n[STOP] Signal received. Draining...")
    running = False


signal.signal(signal.SIGINT,  signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def dict_to_payment(data: dict, ctx):
    """
    Deserialization context callback.
    Returns dict as-is — caller works with plain dict.
    """
    return data


def format_payment(payment: dict) -> str:
    ts = datetime.fromtimestamp(
        payment["timestamp_ms"] / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S UTC")

    return (
        f"  Payment ID  : {payment['payment_id']}\n"
        f"  Order ID    : {payment['order_id']}\n"
        f"  Customer    : {payment['customer_id']}\n"
        f"  Amount      : {payment['amount']:.2f} {payment['currency']}\n"
        f"  Method      : {payment['payment_method']}\n"
        f"  Status      : {payment['status']}\n"
        f"  Merchant    : {payment['merchant_id']}\n"
        f"  Region      : {payment['region']}\n"
        f"  Timestamp   : {ts}\n"
        f"  Metadata    : {payment.get('metadata', {})}\n"
    )


def main():
    print(f"[CONFIG] Bootstrap      : {BOOTSTRAP_SERVERS}")
    print(f"[CONFIG] Schema Registry: {SCHEMA_REGISTRY_URL}")

    schema_registry_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})

    avro_deserializer = AvroDeserializer(
        schema_registry_client,
    )

    consumer = DeserializingConsumer({
        "bootstrap.servers":    BOOTSTRAP_SERVERS,
        "group.id":             GROUP_ID,
        "auto.offset.reset":    "earliest",
        "enable.auto.commit":   False,
        "key.deserializer":     StringDeserializer("utf_8"),
        "value.deserializer":   avro_deserializer,
        "session.timeout.ms":   30000,
        "heartbeat.interval.ms":10000,
        "max.poll.interval.ms": 300000,
    })

    consumer.subscribe([TOPIC])
    print(f"[START] Subscribed to '{TOPIC}' | group: {GROUP_ID}\n")

    empty_polls = 0

    try:
        while running:
            msg = consumer.poll(timeout=2.0)

            if msg is None:
                empty_polls += 1
                if empty_polls == 3:
                    print("[WAIT] Waiting for messages...")
                continue

            empty_polls = 0

            if msg.error():
                if msg.error().code() == KafkaError.PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            payment = msg.value()
            print(f"\n[MSG] partition={msg.partition()} offset={msg.offset()}")
            print(format_payment(payment))

            try:
                consumer.commit(message=msg, asynchronous=False)
            except KafkaException as e:
                if e.args[0].code() == KafkaError._NO_OFFSET:
                    pass
                else:
                    raise

    except KafkaException as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        consumer.close()
        print("[DONE] Consumer closed cleanly.")


if __name__ == "__main__":
    main()
