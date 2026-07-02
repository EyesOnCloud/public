"""
audit-cli: Independent Raw Event Log Reader

This service reads the same orders.events topic as the projector
but with a completely independent consumer group.

It does NOT build projections.
It does NOT compute current state.
It simply prints every event exactly as it was published —
the raw, immutable audit trail.

This demonstrates that multiple independent consumers
can read the same Kafka topic for completely different purposes:
  - order-state-projector: builds current-state read model
  - audit-cli: prints compliance audit trail
  - (future) analytics-service: aggregates metrics
  - (future) search-indexer: indexes orders in Elasticsearch
All reading the same events. None affecting the others.

Consumer group: audit-reader-v1
  Independent offset from order-projector-v1.
  Resetting one group's offset does not affect the other.
"""

import json
import sys
import signal
from datetime import datetime, timezone
from confluent_kafka import Consumer, KafkaError
import config

def format_payload(payload, indent=6):
    """Format payload dict for readable output."""
    lines = []
    for k, v in payload.items():
        if isinstance(v, dict):
            lines.append(f"{' '*indent}{k}:")
            for ik, iv in v.items():
                lines.append(f"{' '*(indent+2)}{ik}: {iv}")
        elif isinstance(v, list):
            lines.append(f"{' '*indent}{k}: [{len(v)} items]")
            for item in v[:3]:  # show first 3 items
                if isinstance(item, dict):
                    summary = ', '.join(f"{k}={v}" for k,v in list(item.items())[:3])
                    lines.append(f"{' '*(indent+2)}- {summary}")
        else:
            lines.append(f"{' '*indent}{k}: {v}")
    return '\n'.join(lines)

def main():
    print(f"\n{config.Colors.BOLD}audit-cli starting...{config.Colors.RESET}")
    print(f"Cluster:       {config.BOOTSTRAP_SERVERS}")
    print(f"Topic:         {config.ORDERS_EVENTS_TOPIC}")
    print(f"Consumer group:{config.AUDIT_GROUP_ID}")
    print(f"Purpose:       Raw event log — compliance audit trail")
    print(f"{'─'*65}")
    print(f"This consumer is INDEPENDENT from order-state-projector.")
    print(f"Same topic. Different consumer group. Different purpose.")
    print(f"{'─'*65}\n")

    consumer = Consumer({
        'bootstrap.servers':  config.BOOTSTRAP_SERVERS,
        'group.id':           config.AUDIT_GROUP_ID,
        'auto.offset.reset':  'earliest',
        'enable.auto.commit': 'true',
        'auto.commit.interval.ms': '5000',
    })

    consumer.subscribe([config.ORDERS_EVENTS_TOPIC])

    shutdown = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, handle_shutdown)

    event_count = 0

    try:
        while not shutdown:
            msg = consumer.poll(timeout=2.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"{config.Colors.RED}Error: {msg.error()}{config.Colors.RESET}")
                continue

            try:
                event = json.loads(msg.value().decode('utf-8'))
            except json.JSONDecodeError:
                print(f"[PARSE ERROR] P{msg.partition()}:O{msg.offset()}")
                continue

            event_count += 1
            event_type = event.get('event_type', 'UNKNOWN')
            order_id   = event.get('order_id', 'UNKNOWN')
            event_id   = event.get('event_id', 'UNKNOWN')
            event_time = event.get('event_time', 'UNKNOWN')
            payload    = event.get('payload', {})

            # Color by event type for visual scanning
            type_colors = {
                'ORDER_CREATED':    config.Colors.WHITE,
                'PAYMENT_RECEIVED': config.Colors.CYAN,
                'ITEMS_PICKED':     config.Colors.CYAN,
                'SHIPPED':          config.Colors.BLUE,
                'DELIVERED':        config.Colors.GREEN,
                'CANCELLED':        config.Colors.RED,
                'DELIVERY_FAILED':  config.Colors.RED,
                'DELIVERY_RETRY':   config.Colors.YELLOW,
                'CORRECTION':       config.Colors.MAGENTA,
            }
            color = type_colors.get(event_type, config.Colors.WHITE)

            print(f"\n{'─'*65}")
            print(
                f"  {config.Colors.BOLD}[AUDIT #{event_count:03d}]{config.Colors.RESET} "
                f"P{msg.partition()}:O{msg.offset()} | "
                f"{color}{event_type}{config.Colors.RESET}"
            )
            print(f"  order_id:   {config.Colors.BOLD}{order_id}{config.Colors.RESET}")
            print(f"  event_id:   {event_id}")
            print(f"  event_time: {event_time}")
            print(f"  payload:")
            print(format_payload(payload))

    except Exception as e:
        print(f"{config.Colors.RED}audit-cli error: {e}{config.Colors.RESET}")
        raise
    finally:
        consumer.close()
        print(f"\n{config.Colors.YELLOW}audit-cli stopped.{config.Colors.RESET}")
        print(f"Total events read: {event_count}")

if __name__ == '__main__':
    main()
