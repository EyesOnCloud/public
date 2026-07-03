"""
inventory-service Saga Participant Step 2

Reacts to PAYMENT_PROCESSED events.
Checks stock and reserves inventory.

What inventory-service knows:
  INPUT:  payments.processed
  OUTPUT: inventory.reserved (success)
          inventory.failed (out of stock)

What inventory-service does NOT know:
  - order-service exists
  - payment-service exists
  - notification-service exists
  - How payment was processed

Stock simulation: SKUs in OUT_OF_STOCK_SKUS fail reservation.
All other SKUs succeed.
"""

import json
import uuid
import time
import signal
import sys
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer, KafkaError
import config

C  = config.Colors
SC = config.SERVICE_COLORS['inventory-service']

producer = Producer({
    'bootstrap.servers': config.BOOTSTRAP_SERVERS,
    'enable.idempotence': 'true',
    'acks': 'all',
    'retries': '2147483647',
    'max.in.flight.requests.per.connection': '5',
    'compression.type': 'lz4',
    'linger.ms': '5',
    'client.id': 'inventory-service-producer',
})

consumer = Consumer({
    'bootstrap.servers':    config.BOOTSTRAP_SERVERS,
    'group.id':             config.INVENTORY_SERVICE_GROUP,
    'auto.offset.reset':    'earliest',
    'enable.auto.commit':   'false',
    'max.poll.interval.ms': '30000',
    'session.timeout.ms':   '20000',
    'heartbeat.interval.ms':'6000',
    'client.id':            'inventory-service-consumer',
})

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def delivery_callback(err, msg):
    if err:
        print(f"{C.RED}  [DELIVERY FAILED] {err}{C.RESET}")

# Simulated inventory levels (in production: database query)
INVENTORY = {
    'SKU-LAPTOP-PRO':    {'stock': 45, 'warehouse': 'WH-SF-01'},
    'SKU-WORKSTATION':   {'stock': 12, 'warehouse': 'WH-TX-01'},
    'SKU-CHAIR-ERGO':    {'stock': 0,  'warehouse': 'WH-WA-01'},  # OUT OF STOCK
    'SKU-HEADSET-PRO':   {'stock': 89, 'warehouse': 'WH-IL-01'},
    'SKU-KEYBOARD-MECH': {'stock': 234,'warehouse': 'WH-MA-01'},
    'SKU-GPU-4090':      {'stock': 0,  'warehouse': 'WH-SF-01'},  # OUT OF STOCK
    'SKU-MONITOR-8K':    {'stock': 0,  'warehouse': 'WH-TX-01'},  # OUT OF STOCK
}

def check_and_reserve_inventory(items):
    """
    Check stock and reserve items.
    Returns: (success, reservation_result)

    In production: this would be a transactional database operation
    with SELECT FOR UPDATE to prevent double-reservation.
    """
    time.sleep(0.3)  # Simulate DB query latency

    failed_items = []
    reserved_items = []

    for item in items:
        sku = item.get('sku', '')
        qty = item.get('qty', 1)

        inv = INVENTORY.get(sku, {'stock': 999, 'warehouse': 'WH-DEFAULT'})

        if sku in config.OUT_OF_STOCK_SKUS or inv['stock'] == 0:
            failed_items.append({
                'sku':       sku,
                'name':      item.get('name'),
                'requested': qty,
                'available': 0,
                'reason':    'OUT_OF_STOCK',
            })
        else:
            reservation_id = f'RES-{uuid.uuid4().hex[:10].upper()}'
            reserved_items.append({
                'sku':            sku,
                'name':           item.get('name'),
                'qty_reserved':   qty,
                'warehouse':      inv['warehouse'],
                'reservation_id': reservation_id,
                'reserved_at':    now_iso(),
            })

    if failed_items:
        return False, {
            'failed_items':   failed_items,
            'reserved_items': reserved_items,  # partial reservations (if any)
            'failure_reason': 'INVENTORY_UNAVAILABLE',
        }

    return True, {
        'reserved_items': reserved_items,
        'reservation_confirmed_at': now_iso(),
        'fulfillment_estimate': '2-3 business days',
    }

def publish_inventory_result(order_id, saga_id, success,
                              order_data, inventory_result):
    if success:
        topic      = config.INVENTORY_RESERVED_TOPIC
        event_type = 'INVENTORY_RESERVED'
    else:
        topic      = config.INVENTORY_FAILED_TOPIC
        event_type = 'INVENTORY_FAILED'

    event = {
        'event_id':   str(uuid.uuid4()),
        'event_type': event_type,
        'order_id':   order_id,
        'saga_id':    saga_id,
        'event_time': now_iso(),
        'data': {
            **order_data,
            'inventory': inventory_result,
        },
    }

    producer.produce(
        topic=topic,
        key=order_id.encode('utf-8'),
        value=json.dumps(event).encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()
    return event

def process_payment_processed(msg):
    try:
        event      = json.loads(msg.value().decode('utf-8'))
        order_id   = event.get('order_id')
        saga_id    = event.get('saga_id', order_id)
        order_data = event.get('data', {})
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"{C.RED}  [PARSE ERROR] {e}{C.RESET}")
        return

    items = order_data.get('items', [])

    print(f"\n{SC}{C.BOLD}{'─'*60}{C.RESET}")
    print(f"{SC}{C.BOLD}[RECEIVED] PAYMENT_PROCESSED{C.RESET}")
    print(f"  order_id:  {order_id}")
    print(f"  saga_id:   {saga_id}")
    print(f"  customer:  {order_data.get('customer_name')}")
    print(f"  items:     {len(items)} item(s)")
    for item in items:
        sku = item.get('sku', 'UNKNOWN')
        inv = INVENTORY.get(sku, {})
        stock_info = f"stock={inv.get('stock', 'unknown')}"
        print(f"    - {item.get('name')} ({sku}) qty={item.get('qty')} [{stock_info}]")

    print(f"\n{SC}Checking inventory...{C.RESET}")

    success, inv_result = check_and_reserve_inventory(items)

    if success:
        print(f"{C.GREEN}{C.BOLD}  INVENTORY RESERVED{C.RESET}")
        for res in inv_result.get('reserved_items', []):
            print(f"  {res['sku']} → reservation_id={res['reservation_id']} "
                  f"warehouse={res['warehouse']}")
        print(f"\n{SC}Publishing INVENTORY_RESERVED to "
              f"{config.INVENTORY_RESERVED_TOPIC}{C.RESET}")
    else:
        print(f"{C.RED}{C.BOLD}  INVENTORY UNAVAILABLE{C.RESET}")
        for fi in inv_result.get('failed_items', []):
            print(f"  {fi['sku']}: {fi['reason']} (available={fi['available']})")
        print(f"\n{SC}Publishing INVENTORY_FAILED to "
              f"{config.INVENTORY_FAILED_TOPIC}{C.RESET}")

    result_event = publish_inventory_result(
        order_id, saga_id, success, order_data, inv_result
    )

    outcome = "inventory.reserved" if success else "inventory.failed"
    print(f"{C.GREEN if success else C.RED}"
          f"  [PUBLISHED] event_id={result_event['event_id'][:16]}... "
          f"→ {outcome}"
          f"{C.RESET}")
    print(f"\n{C.YELLOW}inventory-service role complete for {order_id}. "
          f"notification-service will continue.{C.RESET}")

def main():
    shutdown = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown
        shutdown = True
        print(f"\n{C.YELLOW}inventory-service shutting down...{C.RESET}")

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    consumer.subscribe([config.PAYMENTS_PROCESSED_TOPIC])

    print(f"\n{SC}{C.BOLD}inventory-service starting...{C.RESET}")
    print(f"Cluster:        {config.BOOTSTRAP_SERVERS}")
    print(f"Consumer group: {config.INVENTORY_SERVICE_GROUP}")
    print(f"Consuming from: {config.PAYMENTS_PROCESSED_TOPIC}")
    print(f"Producing to:   {config.INVENTORY_RESERVED_TOPIC}")
    print(f"             OR {config.INVENTORY_FAILED_TOPIC}")
    print(f"\n{C.YELLOW}Inventory rules:")
    print(f"  Out of stock SKUs: {config.OUT_OF_STOCK_SKUS}")
    print(f"  All other SKUs: IN STOCK{C.RESET}")
    print(f"\n{SC}Waiting for payment confirmations...{C.RESET}")

    messages_processed = 0

    try:
        while not shutdown:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"{C.RED}Consumer error: {msg.error()}{C.RESET}")
                continue

            process_payment_processed(msg)
            consumer.commit(asynchronous=False)
            messages_processed += 1

    except Exception as e:
        print(f"{C.RED}inventory-service error: {e}{C.RESET}")
        raise
    finally:
        consumer.close()
        print(f"\n{C.YELLOW}inventory-service stopped. "
              f"Processed {messages_processed} payments.{C.RESET}")

if __name__ == '__main__':
    main()
