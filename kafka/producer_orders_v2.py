import json
import time
from confluent_kafka import Producer

def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed: {err}")
    else:
        print(f"Delivered: key={msg.key().decode()} partition={msg.partition()} offset={msg.offset()}")

producer = Producer({
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'orders-producer-v2'
})

# Breaking schema changes — producer team deployed without consumer coordination
orders_v2 = [
    {
        "order_id": "ORD-20004",
        "customer_id": "CUST-7723",
        "contact_email": "charlie@example.com",  # RENAMED from customer_email
        "items": [
            {"sku": "SKU-400", "name": "Laptop Stand", "qty": 1, "unit_price": 89.99}
        ],
        "subtotal": 89.99,
        "tax": 7.20,
        "total": "97.19 USD",          # TYPE CHANGED from float to string
        "status": "PLACED",
        "placed_at": "2024-07-01T12:00:00Z",
        "ship_to_zip": "94105",         # REPLACED shipping_address object
        "discount_code": "SUMMER10"     # NEW FIELD added
    },
    {
        "order_id": "ORD-20005",
        "customer_id": "CUST-8834",
        "contact_email": "diana@example.com",
        "items": [
            {"sku": "SKU-500", "name": "Webcam", "qty": 1, "unit_price": 129.99}
        ],
        "subtotal": 129.99,
        "tax": 10.40,
        "total": "140.39 USD",
        "status": "PLACED",
        "placed_at": "2024-07-01T12:05:00Z",
        "ship_to_zip": "10001",
        "discount_code": None
    }
]

print("Producing v2 order events with breaking schema changes...")
for order in orders_v2:
    producer.produce(
        topic='orders-message-anatomy',
        key=order["order_id"].encode('utf-8'),
        value=json.dumps(order).encode('utf-8'),
        headers={
            'event-type': b'order_placed',
            'source-service': b'orders-producer-v2',
            'content-type': b'application/json',
            'schema-version': b'2.0'   # Version bumped but consumer never notified
        },
        callback=delivery_report
    )
    producer.poll(0)
    time.sleep(0.1)

producer.flush()
print("v2 messages delivered.")
