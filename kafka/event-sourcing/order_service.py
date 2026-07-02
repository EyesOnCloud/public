"""
order-service — Command Handler and Event Publisher

This service is the WRITE SIDE of the event sourcing architecture.
It accepts order lifecycle commands and publishes immutable events
to the orders.events Kafka topic.

Design principles:
- Never stores current order state
- Never reads from Kafka
- Each command produces exactly one event
- Events are immutable after publication
- Corrections are new events, never modifications

Interactive menu — operator selects which event to publish.
In production: this would be triggered by API calls, not a menu.
The menu exists to give lab participants full control over
which events fire and in what sequence.
"""

import json
import uuid
import sys
from datetime import datetime, timezone
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import config

# Producer setup────────────────────────────────────────────
producer = Producer({
    'bootstrap.servers': config.BOOTSTRAP_SERVERS,
    'enable.idempotence': 'true',
    'acks': 'all',
    'retries': '2147483647',
    'max.in.flight.requests.per.connection': '5',
    'compression.type': 'lz4',
    'linger.ms': '5',
})

def delivery_callback(err, msg):
    if err is not None:
        print(f"{config.Colors.RED}  [DELIVERY FAILED] {err}{config.Colors.RESET}")
    else:
        print(
            f"{config.Colors.GREEN}  [COMMITTED] "
            f"partition={msg.partition()} "
            f"offset={msg.offset()} "
            f"key={msg.key().decode()}"
            f"{config.Colors.RESET}"
        )

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def publish_event(order_id, event_type, payload):
    """
    Publish one immutable order event to Kafka.

    Every event has:
      event_id    — globally unique, used to reference this event
                    in CORRECTION events
      order_id    — the aggregate root ID (also the partition key)
      event_type  — what happened (not what to do)
      event_time  — when it happened (producer clock)
      payload     — event-type specific business data

    The event is named in past tense (ORDER_CREATED, not CREATE_ORDER)
    because it describes something that already happened.
    Commands are imperatives. Events are facts.
    """
    event = {
        'event_id':   str(uuid.uuid4()),
        'order_id':   order_id,
        'event_type': event_type,
        'event_time': now_iso(),
        'payload':    payload,
    }

    event_json = json.dumps(event, indent=None)

    producer.produce(
        topic=config.ORDERS_EVENTS_TOPIC,
        key=order_id.encode('utf-8'),
        value=event_json.encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()

    print(
        f"\n{config.Colors.CYAN}"
        f"  [PUBLISHED] {event_type}"
        f"{config.Colors.RESET}"
    )
    print(f"  order_id:   {order_id}")
    print(f"  event_id:   {event['event_id']}")
    print(f"  event_time: {event['event_time']}")
    for k, v in payload.items():
        print(f"  {k}: {v}")

    return event['event_id']

# Order lifecycle command functions ─────────────────────────

def cmd_create_order(order_id, customer_id, items, total_amount, currency='USD'):
    return publish_event(order_id, 'ORDER_CREATED', {
        'customer_id':    customer_id,
        'items':          items,
        'total_amount':   total_amount,
        'currency':       currency,
        'sales_channel':  'WEB',
        'shipping_address': {
            'street': '123 Main St',
            'city':   'New York',
            'state':  'NY',
            'zip':    '10001',
        },
    })

def cmd_receive_payment(order_id, payment_method, transaction_ref, amount):
    return publish_event(order_id, 'PAYMENT_RECEIVED', {
        'payment_method':  payment_method,
        'transaction_ref': transaction_ref,
        'amount_received': amount,
        'payment_gateway': 'STRIPE',
        'verified_at':     now_iso(),
    })

def cmd_pick_items(order_id, warehouse_id, picker_id, items_confirmed):
    return publish_event(order_id, 'ITEMS_PICKED', {
        'warehouse_id':    warehouse_id,
        'picker_id':       picker_id,
        'items_confirmed': items_confirmed,
        'picked_at':       now_iso(),
    })

def cmd_ship_order(order_id, carrier, tracking_number, estimated_delivery):
    return publish_event(order_id, 'SHIPPED', {
        'carrier':            carrier,
        'tracking_number':    tracking_number,
        'estimated_delivery': estimated_delivery,
        'shipped_from':       'WH-NYC-01',
        'shipped_at':         now_iso(),
    })

def cmd_deliver_order(order_id, delivered_to, proof_of_delivery):
    return publish_event(order_id, 'DELIVERED', {
        'delivered_to':       delivered_to,
        'proof_of_delivery':  proof_of_delivery,
        'delivered_at':       now_iso(),
        'delivery_signature': 'SIGNED',
    })

def cmd_cancel_order(order_id, cancelled_by, reason, refund_amount):
    return publish_event(order_id, 'CANCELLED', {
        'cancelled_by':   cancelled_by,
        'reason':         reason,
        'refund_amount':  refund_amount,
        'refund_method':  'ORIGINAL_PAYMENT',
        'cancelled_at':   now_iso(),
    })

def cmd_delivery_failed(order_id, carrier, tracking_number, failure_reason, attempt_number):
    return publish_event(order_id, 'DELIVERY_FAILED', {
        'carrier':          carrier,
        'tracking_number':  tracking_number,
        'failure_reason':   failure_reason,
        'attempt_number':   attempt_number,
        'failed_at':        now_iso(),
        'next_attempt':     'WILL_RETRY',
    })

def cmd_delivery_retry(order_id, carrier, tracking_number, retry_date, attempt_number):
    return publish_event(order_id, 'DELIVERY_RETRY', {
        'carrier':          carrier,
        'tracking_number':  tracking_number,
        'retry_date':       retry_date,
        'attempt_number':   attempt_number,
        'retried_at':       now_iso(),
    })

def cmd_correction(order_id, corrects_event_id, correction_type,
                   correction_data, authorized_by, reason):
    return publish_event(order_id, 'CORRECTION', {
        'corrects_event_id': corrects_event_id,
        'correction_type':   correction_type,
        'correction_data':   correction_data,
        'authorized_by':     authorized_by,
        'reason':            reason,
        'correction_time':   now_iso(),
    })

# Interactive menu ──────────────────────────────────────────

def print_menu():
    print(f"\n{config.Colors.BOLD}{'='*60}{config.Colors.RESET}")
    print(f"{config.Colors.BOLD}  ORDER SERVICE — Event Publisher{config.Colors.RESET}")
    print(f"{config.Colors.BOLD}{'='*60}{config.Colors.RESET}")
    print(f"  Cluster: {config.BOOTSTRAP_SERVERS}")
    print(f"  Topic:   {config.ORDERS_EVENTS_TOPIC}")
    print(f"{'─'*60}")
    print(f"  SCENARIO SEQUENCES:")
    print(f"  1. ORD-1001 — ORDER_CREATED")
    print(f"  2. ORD-1001 — PAYMENT_RECEIVED")
    print(f"  3. ORD-1001 — ITEMS_PICKED")
    print(f"  4. ORD-1001 — SHIPPED")
    print(f"  5. ORD-1001 — DELIVERED")
    print(f"  ─")
    print(f"  6. ORD-1002 — ORDER_CREATED")
    print(f"  7. ORD-1002 — PAYMENT_RECEIVED")
    print(f"  8. ORD-1002 — CANCELLED")
    print(f"  ─")
    print(f"  9. ORD-1003 — ORDER_CREATED")
    print(f" 10. ORD-1003 — PAYMENT_RECEIVED")
    print(f" 11. ORD-1003 — ITEMS_PICKED")
    print(f" 12. ORD-1003 — SHIPPED")
    print(f" 13. ORD-1003 — DELIVERY_FAILED (attempt 1)")
    print(f" 14. ORD-1003 — DELIVERY_RETRY (attempt 2)")
    print(f" 15. ORD-1003 — DELIVERED")
    print(f"  ─")
    print(f" 16. ORD-1003 — CORRECTION (wrong shipping address)")
    print(f"  ─")
    print(f"  q. Quit")
    print(f"{'─'*60}")

# Pre-built event payloads for demo

SCENARIOS = {
    '1': lambda: cmd_create_order(
        'ORD-1001', 'CUST-5501',
        items=[
            {'sku': 'LAPTOP-PRO-15', 'name': 'Laptop Pro 15"', 'qty': 1, 'price': 1299.99},
            {'sku': 'USB-HUB-7P',    'name': 'USB-C Hub 7-port', 'qty': 2, 'price': 49.99},
        ],
        total_amount=1399.97
    ),
    '2': lambda: cmd_receive_payment(
        'ORD-1001', 'CREDIT_CARD',
        f'TXN-{uuid.uuid4().hex[:10].upper()}', 1399.97
    ),
    '3': lambda: cmd_pick_items(
        'ORD-1001', 'WH-NYC-01', 'PICKER-442',
        items_confirmed=['LAPTOP-PRO-15', 'USB-HUB-7P', 'USB-HUB-7P']
    ),
    '4': lambda: cmd_ship_order(
        'ORD-1001', 'FEDEX',
        f'FX-{uuid.uuid4().hex[:12].upper()}', '2024-07-05'
    ),
    '5': lambda: cmd_deliver_order(
        'ORD-1001', 'JOHN DOE', f'POD-{uuid.uuid4().hex[:8].upper()}'
    ),
    '6': lambda: cmd_create_order(
        'ORD-1002', 'CUST-6612',
        items=[
            {'sku': 'MONITOR-27', 'name': 'Dell Monitor 27"', 'qty': 1, 'price': 649.99},
        ],
        total_amount=649.99
    ),
    '7': lambda: cmd_receive_payment(
        'ORD-1002', 'PAYPAL',
        f'PP-{uuid.uuid4().hex[:10].upper()}', 649.99
    ),
    '8': lambda: cmd_cancel_order(
        'ORD-1002', 'CUSTOMER',
        'CUSTOMER_REQUEST: Found better price elsewhere',
        refund_amount=649.99
    ),
    '9': lambda: cmd_create_order(
        'ORD-1003', 'CUST-7723',
        items=[
            {'sku': 'CHAIR-ERGO', 'name': 'Ergonomic Chair', 'qty': 1, 'price': 899.99},
        ],
        total_amount=899.99
    ),
    '10': lambda: cmd_receive_payment(
        'ORD-1003', 'DEBIT_CARD',
        f'TXN-{uuid.uuid4().hex[:10].upper()}', 899.99
    ),
    '11': lambda: cmd_pick_items(
        'ORD-1003', 'WH-NJ-02', 'PICKER-891',
        items_confirmed=['CHAIR-ERGO']
    ),
    '12': lambda: cmd_ship_order(
        'ORD-1003', 'UPS',
        'UPS-1Z9999W99999999999', '2024-07-06'
    ),
    '13': lambda: cmd_delivery_failed(
        'ORD-1003', 'UPS', 'UPS-1Z9999W99999999999',
        'WRONG_ADDRESS: Unit number missing from address',
        attempt_number=1
    ),
    '14': lambda: cmd_delivery_retry(
        'ORD-1003', 'UPS', 'UPS-1Z9999W99999999999',
        retry_date='2024-07-08', attempt_number=2
    ),
    '15': lambda: cmd_deliver_order(
        'ORD-1003', 'JANE SMITH', f'POD-{uuid.uuid4().hex[:8].upper()}'
    ),
}

# CORRECTION scenario needs the event_id from the SHIPPED event of ORD-1003
# copy this from the projector output
def scenario_16():
    print(f"\n{config.Colors.YELLOW}")
    print(f"  CORRECTION EVENT for ORD-1003")
    print(f"  The shipping address was missing the unit number.")
    print(f"  This caused the first delivery attempt to fail (scenario 13).")
    print(f"  We publish a CORRECTION event to document the address fix.")
    print(f"  The original SHIPPED event is NOT modified — it stays in the log.")
    print(f"{config.Colors.RESET}")
    corrects_id = input("  Enter the event_id of the SHIPPED event (ORD-1003, step 12): ").strip()
    if not corrects_id:
        corrects_id = 'UNKNOWN-COPY-FROM-PROJECTOR-OUTPUT'
    return cmd_correction(
        'ORD-1003',
        corrects_event_id=corrects_id,
        correction_type='ADDRESS_CORRECTION',
        correction_data={
            'original_address': {'street': '456 Oak Ave', 'city': 'Newark', 'state': 'NJ', 'zip': '07101'},
            'corrected_address': {'street': '456 Oak Ave', 'unit': 'APT 3B', 'city': 'Newark', 'state': 'NJ', 'zip': '07101'},
        },
        authorized_by='SUPPORT-AGENT-ID-00892',
        reason='Unit number missing caused delivery failure. '
               'Customer confirmed correct address via phone.'
    )

SCENARIOS['16'] = scenario_16

def main():
    print(f"\n{config.Colors.BOLD}order-service starting...{config.Colors.RESET}")
    print(f"Connecting to: {config.BOOTSTRAP_SERVERS}")
    print(f"Publishing to: {config.ORDERS_EVENTS_TOPIC}")

    while True:
        print_menu()
        choice = input(f"\n  Select scenario (1-16 or q): ").strip().lower()

        if choice == 'q':
            print(f"\n{config.Colors.YELLOW}order-service stopped.{config.Colors.RESET}")
            sys.exit(0)

        if choice in SCENARIOS:
            try:
                SCENARIOS[choice]()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                print(f"{config.Colors.RED}Error: {e}{config.Colors.RESET}")
        else:
            print(f"{config.Colors.RED}Invalid choice. Enter 1-16 or q.{config.Colors.RESET}")

if __name__ == '__main__':
    main()
