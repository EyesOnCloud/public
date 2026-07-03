"""
order-service-v2 Order Producer with Deliberate Poison Messages

Produces 10 orders in sequence:
  Orders 1, 3, 5, 7, 9: valid orders → payment-service processes normally
  Order 2:  missing customer_id → schema validation fails → DLQ
  Order 4:  amount = -500 → negative amount → DLQ
  Order 6:  card_last4 = 'ABCD' → invalid format → DLQ
  Order 8:  amount = 15000 → exceeds daily limit → DLQ
  Order 10: valid order → processes normally

This service is unchanged in its architecture from Lab 18:
it publishes to orders.placed and knows nothing about
payment-service, DLQ, or any downstream processing.
The poison messages are produced intentionally to demonstrate
that malformed data is a PRODUCER problem that the CONSUMER
must handle defensively.
"""

import json
import uuid
import sys
from datetime import datetime, timezone
from confluent_kafka import Producer
import config

C  = config.Colors
SC = config.SERVICE_COLORS['order-service']

producer = Producer({
    'bootstrap.servers': config.BOOTSTRAP_SERVERS,
    'enable.idempotence': 'true',
    'acks': 'all',
    'retries': '2147483647',
    'max.in.flight.requests.per.connection': '5',
    'compression.type': 'lz4',
    'linger.ms': '5',
    'client.id': 'order-service-v2-producer',
})

def delivery_callback(err, msg):
    if err:
        print(f"{C.RED}  [DELIVERY FAILED] {err}{C.RESET}")
    else:
        print(
            f"{C.GREEN}  [COMMITTED] "
            f"topic={msg.topic()} "
            f"partition={msg.partition()} "
            f"offset={msg.offset()} "
            f"key={msg.key().decode() if msg.key() else 'none'}"
            f"{C.RESET}"
        )

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def publish(order_id, payload):
    """Publish order to orders.placed. Accepts any payload — including malformed ones."""
    event = {
        'event_id':   str(uuid.uuid4()),
        'event_type': 'ORDER_PLACED',
        'order_id':   order_id,
        'saga_id':    order_id,
        'event_time': now_iso(),
        'data':       payload,
    }
    producer.produce(
        topic=config.ORDERS_PLACED_TOPIC,
        key=order_id.encode('utf-8'),
        value=json.dumps(event).encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()
    return event

# Lab scenario order definitions ───────────────────────────

def valid_order(order_id, customer_name, email, amount, card_last4, sku, item_name):
    return {
        'order_id':       order_id,
        'customer_id':    f'CUST-{uuid.uuid4().hex[:6].upper()}',
        'customer_name':  customer_name,
        'customer_email': email,
        'items': [{
            'sku':        sku,
            'name':       item_name,
            'qty':        1,
            'unit_price': amount,
        }],
        'total_amount': amount,
        'currency':     'USD',
        'payment': {
            'method':     'CREDIT_CARD',
            'card_last4': card_last4,
            'card_brand': 'VISA',
        },
        'shipping_address': {
            'street': '100 Commerce St',
            'city':   'New York',
            'state':  'NY',
            'zip':    '10001',
        },
    }

LAB_SCENARIOS = {
    '1': {
        'label':       'Order 1 — VALID | $150 | Card 4242',
        'category':    'VALID',
        'description': 'Valid order → payment succeeds → processes normally',
        'order_id':    'ORD-LAB19-001',
        'payload':     valid_order('ORD-LAB19-001', 'Alice Chen', 'alice@example.com',
                                   150.00, '4242', 'SKU-LAPTOP', 'Laptop Pro 15"'),
    },
    '2': {
        'label':       'Order 2 — POISON | Missing customer_id field',
        'category':    'POISON',
        'description': 'customer_id field completely absent → schema validation fails → DLQ',
        'order_id':    'ORD-LAB19-002',
        'payload': {
            # customer_id MISSING — required field absent
            'order_id':       'ORD-LAB19-002',
            'customer_name':  'Bob Missing',
            'customer_email': 'bob@example.com',
            'items': [{'sku': 'SKU-MOUSE', 'name': 'Wireless Mouse', 'qty': 1, 'unit_price': 45.00}],
            'total_amount': 45.00,
            'currency':     'USD',
            'payment': {'method': 'CREDIT_CARD', 'card_last4': '4242', 'card_brand': 'VISA'},
            'shipping_address': {'street': '200 Oak Ave', 'city': 'Austin', 'state': 'TX', 'zip': '78701'},
        },
    },
    '3': {
        'label':       'Order 3 — VALID | $299 | Card 4242',
        'category':    'VALID',
        'description': 'Valid order → payment succeeds → processes normally',
        'order_id':    'ORD-LAB19-003',
        'payload':     valid_order('ORD-LAB19-003', 'Carol Davis', 'carol@example.com',
                                   299.00, '4242', 'SKU-HEADSET', 'Noise Cancelling Headset'),
    },
    '4': {
        'label':       'Order 4 — POISON | Negative amount (-$500)',
        'category':    'POISON',
        'description': 'amount = -500 → negative amount business rule → DLQ',
        'order_id':    'ORD-LAB19-004',
        'payload': {
            'order_id':       'ORD-LAB19-004',
            'customer_id':    'CUST-NEGATIVE',
            'customer_name':  'Dave Negative',
            'customer_email': 'dave@example.com',
            'items': [{'sku': 'SKU-CHAIR', 'name': 'Office Chair', 'qty': 1, 'unit_price': -500.00}],
            'total_amount': -500.00,  # NEGATIVE AMOUNT — business rule violation
            'currency':     'USD',
            'payment': {'method': 'CREDIT_CARD', 'card_last4': '4242', 'card_brand': 'VISA'},
            'shipping_address': {'street': '300 Pine Rd', 'city': 'Seattle', 'state': 'WA', 'zip': '98101'},
        },
    },
    '5': {
        'label':       'Order 5 — VALID | $89 | Card 4242',
        'category':    'VALID',
        'description': 'Valid order → payment succeeds → processes normally',
        'order_id':    'ORD-LAB19-005',
        'payload':     valid_order('ORD-LAB19-005', 'Emma Rodriguez', 'emma@example.com',
                                   89.00, '4242', 'SKU-KEYBOARD', 'Mechanical Keyboard'),
    },
    '6': {
        'label':       'Order 6 — POISON | Invalid card format (card_last4 = "ABCD")',
        'category':    'POISON',
        'description': 'card_last4 contains letters → format validation fails → DLQ',
        'order_id':    'ORD-LAB19-006',
        'payload': {
            'order_id':       'ORD-LAB19-006',
            'customer_id':    'CUST-BADCARD',
            'customer_name':  'Frank Badcard',
            'customer_email': 'frank@example.com',
            'items': [{'sku': 'SKU-MONITOR', 'name': 'Dell Monitor 27"', 'qty': 1, 'unit_price': 449.00}],
            'total_amount': 449.00,
            'currency':     'USD',
            'payment': {
                'method':     'CREDIT_CARD',
                'card_last4': 'ABCD',  # INVALID FORMAT — must be 4 digits
                'card_brand': 'VISA',
            },
            'shipping_address': {'street': '400 Elm St', 'city': 'Chicago', 'state': 'IL', 'zip': '60601'},
        },
    },
    '7': {
        'label':       'Order 7 — VALID | $175 | Card 4242',
        'category':    'VALID',
        'description': 'Valid order → payment succeeds → processes normally',
        'order_id':    'ORD-LAB19-007',
        'payload':     valid_order('ORD-LAB19-007', 'Grace Kim', 'grace@example.com',
                                   175.00, '4242', 'SKU-WEBCAM', 'HD Webcam 4K'),
    },
    '8': {
        'label':       'Order 8 — POISON | Exceeds daily limit ($15,000)',
        'category':    'POISON',
        'description': 'amount > $10,000 daily limit → policy violation → DLQ',
        'order_id':    'ORD-LAB19-008',
        'payload': {
            'order_id':       'ORD-LAB19-008',
            'customer_id':    'CUST-HIGHLIMIT',
            'customer_name':  'Henry Highspend',
            'customer_email': 'henry@example.com',
            'items': [{'sku': 'SKU-SERVER', 'name': 'Dell PowerEdge Server', 'qty': 1, 'unit_price': 15000.00}],
            'total_amount': 15000.00,  # EXCEEDS $10,000 DAILY LIMIT
            'currency':     'USD',
            'payment': {'method': 'CREDIT_CARD', 'card_last4': '4242', 'card_brand': 'AMEX'},
            'shipping_address': {'street': '500 Maple Dr', 'city': 'Boston', 'state': 'MA', 'zip': '02101'},
        },
    },
    '9': {
        'label':       'Order 9 — VALID | $550 | Card 4242',
        'category':    'VALID',
        'description': 'Valid order → payment succeeds → processes normally',
        'order_id':    'ORD-LAB19-009',
        'payload':     valid_order('ORD-LAB19-009', 'Isabella Park', 'isabella@example.com',
                                   550.00, '4242', 'SKU-TABLET', 'iPad Pro 12.9"'),
    },
    '10': {
        'label':       'Order 10 — VALID | $225 | Card 4242',
        'category':    'VALID',
        'description': 'Valid order → payment succeeds → processes normally',
        'order_id':    'ORD-LAB19-010',
        'payload':     valid_order('ORD-LAB19-010', 'James Wilson', 'james@example.com',
                                   225.00, '4242', 'SKU-DOCKING', 'USB-C Docking Station'),
    },
}

def print_menu():
    print(f"\n{C.BOLD}{SC}{'='*65}{C.RESET}")
    print(f"{C.BOLD}{SC}  ORDER SERVICE v2 — DLQ Lab Producer{C.RESET}")
    print(f"{C.BOLD}{SC}  Topic: {config.ORDERS_PLACED_TOPIC}{C.RESET}")
    print(f"{C.BOLD}{SC}{'='*65}{C.RESET}")

    for key, s in sorted(LAB_SCENARIOS.items(), key=lambda x: int(x[0])):
        cat_color = C.GREEN if s['category'] == 'VALID' else C.RED
        cat_label = f"{cat_color}[{s['category']:6s}]{C.RESET}"
        print(f"  {C.BOLD}{key:2s}.{C.RESET} {cat_label} {s['label']}")
        print(f"       {C.YELLOW}{s['description']}{C.RESET}")

    print(f"\n  {C.BOLD}a.{C.RESET} Produce ALL 10 orders in sequence (1 second delay between each)")
    print(f"  {C.BOLD}q.{C.RESET} Quit")
    print(f"{SC}{'─'*65}{C.RESET}")

def produce_order(choice):
    if choice not in LAB_SCENARIOS:
        print(f"{C.RED}Invalid choice.{C.RESET}")
        return

    s = LAB_SCENARIOS[choice]
    order_id = s['order_id']
    payload  = s['payload']
    cat      = s['category']
    cat_color = C.GREEN if cat == 'VALID' else C.RED

    print(f"\n{SC}{C.BOLD}Publishing Order {choice}: {order_id}{C.RESET}")
    print(f"  Category: {cat_color}{cat}{C.RESET}")
    print(f"  {s['description']}")

    if cat == 'POISON':
        print(f"\n  {C.RED}{C.BOLD}⚠  INTENTIONALLY MALFORMED — expect DLQ routing{C.RESET}")

    print(f"\n  Publishing to {config.ORDERS_PLACED_TOPIC}...")
    publish(order_id, payload)
    print(f"{SC}  Done. Watch Terminal B (payment-service-with-dlq).{C.RESET}")

def main():
    print(f"\n{SC}{C.BOLD}order-service-v2 starting...{C.RESET}")
    print(f"Cluster: {config.BOOTSTRAP_SERVERS}")
    print(f"\n{C.YELLOW}Orders 2, 4, 6, 8 are intentionally malformed.")
    print(f"They simulate real-world data quality problems")
    print(f"that payment-service must handle without blocking.{C.RESET}")

    import time

    while True:
        print_menu()
        choice = input(f"\n  Select (1-10, a=all, q=quit): ").strip().lower()

        if choice == 'q':
            sys.exit(0)
        elif choice == 'a':
            print(f"\n{C.BOLD}Producing all 10 orders with 1s delay between each...{C.RESET}")
            for i in range(1, 11):
                produce_order(str(i))
                if i < 10:
                    time.sleep(1.0)
            print(f"\n{C.GREEN}All 10 orders produced.{C.RESET}")
            print(f"Expected: 6 processed normally, 4 routed to DLQ.")
        elif choice in LAB_SCENARIOS:
            produce_order(choice)
        else:
            print(f"{C.RED}Invalid. Enter 1-10, a, or q.{C.RESET}")

if __name__ == '__main__':
    main()
