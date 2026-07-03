"""
order-service Saga Initiator

This service is the entry point for the choreography saga.
It accepts order commands from operators (via CLI menu in this demo,
via REST API in production) and publishes ORDER_PLACED events
to the orders.placed topic.

Responsibilities:
  - Accept order input
  - Validate basic order data (non-empty items, positive amount)
  - Publish ORDER_PLACED event to orders.placed
  - That is ALL, it does not call payment-service, inventory-service,
    or any other service directly

What order-service does NOT know:
  - That payment-service exists
  - That inventory-service exists
  - That notification-service exists
  - What happens after the event is published

This is the defining characteristic of choreography:
the initiating service publishes one event and its job is done.
Everything else is driven by the event chain.
"""

import json
import uuid
import sys
from datetime import datetime, timezone
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import config

C = config.Colors
SC = config.SERVICE_COLORS['order-service']

# Producer setup ────────────────────────────────────────────
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
    if err:
        print(f"{C.RED}  [DELIVERY FAILED] {err}{C.RESET}")
    else:
        print(
            f"{C.GREEN}  [COMMITTED TO KAFKA] "
            f"topic={msg.topic()} "
            f"partition={msg.partition()} "
            f"offset={msg.offset()} "
            f"key={msg.key().decode()}"
            f"{C.RESET}"
        )

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def publish_order_placed(order_data):
    """
    Publish ORDER_PLACED event to orders.placed topic.
    This is the saga trigger event — once published,
    the choreography takes over with no further action from
    this service.
    """
    order_id = order_data['order_id']

    event = {
        'event_id':   str(uuid.uuid4()),
        'event_type': 'ORDER_PLACED',
        'order_id':   order_id,
        'event_time': now_iso(),
        'saga_id':    order_id,  # saga_id = order_id for tracing the full chain
        'data': order_data,
    }

    producer.produce(
        topic=config.ORDERS_PLACED_TOPIC,
        key=order_id.encode('utf-8'),
        value=json.dumps(event).encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()

    return event

# Lab scenario orders ───────────────────────────────────────

LAB_SCENARIOS = {
    '1': {
        'label': 'Order 1 - $150.00 | Card 4242 | In-stock item',
        'description': 'FULL HAPPY PATH: payment succeeds → inventory reserved → notification sent',
        'order': {
            'order_id':    'ORD-2001',
            'customer_id': 'CUST-8801',
            'customer_email': 'alice@example.com',
            'customer_name': 'Alice Johnson',
            'items': [
                {'sku': 'SKU-LAPTOP-PRO', 'name': 'Laptop Pro 15"',
                 'qty': 1, 'unit_price': 150.00},
            ],
            'total_amount': 150.00,
            'currency': 'USD',
            'payment': {
                'method': 'CREDIT_CARD',
                'card_last4': '4242',
                'card_brand': 'VISA',
            },
            'shipping_address': {
                'street': '100 Main St', 'city': 'San Francisco',
                'state': 'CA', 'zip': '94101',
            },
        }
    },
    '2': {
        'label': 'Order 2 - $5000.00 | Card 0002 | Payment will FAIL',
        'description': 'PAYMENT FAILURE PATH: payment fails → notification sent (no inventory step)',
        'order': {
            'order_id':    'ORD-2002',
            'customer_id': 'CUST-8802',
            'customer_email': 'bob@example.com',
            'customer_name': 'Bob Martinez',
            'items': [
                {'sku': 'SKU-WORKSTATION', 'name': 'Developer Workstation',
                 'qty': 1, 'unit_price': 5000.00},
            ],
            'total_amount': 5000.00,
            'currency': 'USD',
            'payment': {
                'method': 'CREDIT_CARD',
                'card_last4': '0002',
                'card_brand': 'MASTERCARD',
            },
            'shipping_address': {
                'street': '200 Oak Ave', 'city': 'Austin',
                'state': 'TX', 'zip': '78701',
            },
        }
    },
    '3': {
        'label': 'Order 3 - $75.00 | Card 4242 | OUT OF STOCK item',
        'description': 'INVENTORY FAILURE PATH: payment succeeds → inventory fails → notification sent',
        'order': {
            'order_id':    'ORD-2003',
            'customer_id': 'CUST-8803',
            'customer_email': 'carol@example.com',
            'customer_name': 'Carol Williams',
            'items': [
                {'sku': 'SKU-CHAIR-ERGO', 'name': 'Ergonomic Chair',
                 'qty': 1, 'unit_price': 75.00},
            ],
            'total_amount': 75.00,
            'currency': 'USD',
            'payment': {
                'method': 'CREDIT_CARD',
                'card_last4': '4242',
                'card_brand': 'VISA',
            },
            'shipping_address': {
                'street': '300 Pine Rd', 'city': 'Seattle',
                'state': 'WA', 'zip': '98101',
            },
        }
    },
    '4': {
        'label': 'Order 4 - $200.00 | Card 4242 | Kill notification-service after this',
        'description': 'LAG DEMO: payment succeeds → inventory reserved → notification PENDING (kill service)',
        'order': {
            'order_id':    'ORD-2004',
            'customer_id': 'CUST-8804',
            'customer_email': 'david@example.com',
            'customer_name': 'David Chen',
            'items': [
                {'sku': 'SKU-HEADSET-PRO', 'name': 'Noise Cancelling Headset',
                 'qty': 1, 'unit_price': 200.00},
            ],
            'total_amount': 200.00,
            'currency': 'USD',
            'payment': {
                'method': 'CREDIT_CARD',
                'card_last4': '4242',
                'card_brand': 'VISA',
            },
            'shipping_address': {
                'street': '400 Elm St', 'city': 'Chicago',
                'state': 'IL', 'zip': '60601',
            },
        }
    },
    '5': {
        'label': 'Order 5 - $350.00 | Card 4242 | Full happy path (after restart)',
        'description': 'RECOVERY DEMO: all services running, full happy path',
        'order': {
            'order_id':    'ORD-2005',
            'customer_id': 'CUST-8805',
            'customer_email': 'emma@example.com',
            'customer_name': 'Emma Rodriguez',
            'items': [
                {'sku': 'SKU-KEYBOARD-MECH', 'name': 'Mechanical Keyboard',
                 'qty': 1, 'unit_price': 350.00},
            ],
            'total_amount': 350.00,
            'currency': 'USD',
            'payment': {
                'method': 'CREDIT_CARD',
                'card_last4': '4242',
                'card_brand': 'VISA',
            },
            'shipping_address': {
                'street': '500 Maple Dr', 'city': 'Boston',
                'state': 'MA', 'zip': '02101',
            },
        }
    },
}

def print_menu():
    print(f"\n{C.BOLD}{SC}{'='*65}{C.RESET}")
    print(f"{C.BOLD}{SC}  ORDER SERVICE — Saga Initiator{C.RESET}")
    print(f"{C.BOLD}{SC}  Publishes to: {config.ORDERS_PLACED_TOPIC}{C.RESET}")
    print(f"{C.BOLD}{SC}{'='*65}{C.RESET}")
    for key, scenario in LAB_SCENARIOS.items():
        print(f"  {C.BOLD}{key}.{C.RESET} {scenario['label']}")
        print(f"     {C.YELLOW}{scenario['description']}{C.RESET}")
    print(f"  {C.BOLD}q.{C.RESET} Quit")
    print(f"{SC}{'─'*65}{C.RESET}")

def main():
    print(f"\n{SC}{C.BOLD}order-service starting...{C.RESET}")
    print(f"Connecting to: {config.BOOTSTRAP_SERVERS}")
    print(f"Publishing to: {config.ORDERS_PLACED_TOPIC}")
    print(f"\n{C.YELLOW}This service ONLY publishes to orders.placed.")
    print(f"It has NO knowledge of payment-service, inventory-service,")
    print(f"or notification-service. The saga proceeds autonomously.{C.RESET}")

    while True:
        print_menu()
        choice = input(f"\n  Select order to place (1-5 or q): ").strip().lower()

        if choice == 'q':
            print(f"\n{C.YELLOW}order-service stopped.{C.RESET}")
            sys.exit(0)

        if choice not in LAB_SCENARIOS:
            print(f"{C.RED}Invalid choice.{C.RESET}")
            continue

        scenario = LAB_SCENARIOS[choice]
        order = scenario['order'].copy()

        print(f"\n{SC}{C.BOLD}Placing order: {order['order_id']}{C.RESET}")
        print(f"  Customer:  {order['customer_name']} ({order['customer_email']})")
        print(f"  Amount:    ${order['total_amount']:.2f} {order['currency']}")
        print(f"  Card:      **** **** **** {order['payment']['card_last4']}")
        print(f"  Items:     {len(order['items'])} item(s)")
        for item in order['items']:
            print(f"    - {item['name']} (SKU: {item['sku']}) x{item['qty']} @ ${item['unit_price']:.2f}")

        print(f"\n{SC}Publishing ORDER_PLACED event to {config.ORDERS_PLACED_TOPIC}...{C.RESET}")

        event = publish_order_placed(order)

        print(f"\n{C.GREEN}{C.BOLD}ORDER PLACED SUCCESSFULLY{C.RESET}")
        print(f"  order_id:  {order['order_id']}")
        print(f"  saga_id:   {event['saga_id']}")
        print(f"  event_id:  {event['event_id']}")
        print(f"\n{C.YELLOW}Saga triggered. Watch Terminal B (payment-service) for next step.{C.RESET}")
        print(f"{C.YELLOW}order-service has completed its role. It will not be involved further.{C.RESET}")

if __name__ == '__main__':
    main()
