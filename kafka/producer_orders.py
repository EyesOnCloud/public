import json
import time
from confluent_kafka import Producer

def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed for {msg.key()}: {err}")
    else:
        print(f"Delivered: key={msg.key().decode()} "
              f"partition={msg.partition()} "
              f"offset={msg.offset()}")

producer = Producer({
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'orders-producer-v1'
})

# Simulate a realistic order event stream
orders = [
    {
        "order_id": "ORD-20001",
        "customer_id": "CUST-5501",
        "customer_email": "john@example.com",
        "items": [
            {"sku": "SKU-100", "name": "Wireless Keyboard", "qty": 1, "unit_price": 79.99},
            {"sku": "SKU-101", "name": "Mouse Pad", "qty": 2, "unit_price": 12.99}
        ],
        "subtotal": 105.97,
        "tax": 8.48,
        "total": 114.45,
        "currency": "USD",
        "status": "PLACED",
        "placed_at": "2024-07-01T11:00:00Z",
        "shipping_address": {
            "street": "123 Main St",
            "city": "Austin",
            "state": "TX",
            "zip": "78701"
        }
    },
    {
        "order_id": "ORD-20002",
        "customer_id": "CUST-6612",
        "customer_email": "alex@example.com",
        "items": [
            {"sku": "SKU-200", "name": "USB-C Hub", "qty": 1, "unit_price": 49.99}
        ],
        "subtotal": 49.99,
        "tax": 4.00,
        "total": 53.99,
        "currency": "USD",
        "status": "PLACED",
        "placed_at": "2024-07-01T11:02:00Z",
        "shipping_address": {
            "street": "456 Oak Ave",
            "city": "Seattle",
            "state": "WA",
            "zip": "98101"
        }
    },
    {
        "order_id": "ORD-20003",
        "customer_id": "CUST-5501",
        "customer_email": "fedrick@example.com",
        "items": [
            {"sku": "SKU-300", "name": "Monitor Stand", "qty": 1, "unit_price": 199.99}
        ],
        "subtotal": 199.99,
        "tax": 16.00,
        "total": 215.99,
        "currency": "USD",
        "status": "PLACED",
        "placed_at": "2024-07-01T11:05:00Z",
        "shipping_address": {
            "street": "123 Main St",
            "city": "Austin",
            "state": "TX",
            "zip": "78701"
        }
    }
]

print("Producing order events...")
for order in orders:
    key = order["order_id"]
    value = json.dumps(order)  # dict -> JSON string -> bytes via UTF-8

    producer.produce(
        topic='orders-message-anatomy',
        key=key.encode('utf-8'),
        value=value.encode('utf-8'),
        headers={
            'event-type': b'order_placed',
            'source-service': b'orders-producer-v1',
            'content-type': b'application/json',
            'schema-version': b'1.0'
        },
        callback=delivery_report
    )
    producer.poll(0)  # trigger delivery callbacks without blocking
    time.sleep(0.1)

# Flush ensures all buffered messages are sent before script exits
producer.flush()
print("All messages delivered.")
