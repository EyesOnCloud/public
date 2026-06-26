import json
import uuid
import random
import time
from confluent_kafka import Producer

TOPIC = 'orders-group-demo'
MESSAGE_COUNT = 100
BOOTSTRAP_SERVERS = '192.168.100.21:9092,192.168.100.22:9092,192.168.100.23:9092'

def delivery_callback(err, msg):
    if err:
        print(f"Delivery failed: {err}")

producer = Producer({
    'bootstrap.servers': BOOTSTRAP_SERVERS,
    'enable.idempotence': 'true',
    'acks': 'all',
    'linger.ms': '5',
})

ACCOUNT_IDS = [f'ACC-{i:04d}' for i in range(1, 11)]
PRODUCTS = [
    ('PROD-A', 'Laptop', 1299.99),
    ('PROD-B', 'Monitor', 449.99),
    ('PROD-C', 'Keyboard', 89.99),
    ('PROD-D', 'Mouse', 49.99),
    ('PROD-E', 'Headset', 199.99),
]

print(f"Producing {MESSAGE_COUNT} keyed orders to {TOPIC}")
print(f"Bootstrap: {BOOTSTRAP_SERVERS}")
print(f"key=account_id — same account always routes to same partition")
print()

for i in range(MESSAGE_COUNT):
    account_id = ACCOUNT_IDS[i % len(ACCOUNT_IDS)]
    product = random.choice(PRODUCTS)
    qty = random.randint(1, 3)

    order = {
        'order_id': f'ORD-{uuid.uuid4().hex[:8].upper()}',
        'account_id': account_id,
        'sequence': i,
        'product_id': product[0],
        'product_name': product[1],
        'quantity': qty,
        'amount': round(product[2] * qty, 2),
        'status': 'PLACED',
        'placed_at': f'2024-07-01T{10 + i // 60:02d}:{i % 60:02d}:00Z'
    }

    producer.produce(
        topic=TOPIC,
        key=account_id.encode('utf-8'),
        value=json.dumps(order).encode('utf-8'),
        callback=delivery_callback
    )

    if i % 10 == 0:
        producer.poll(0)

producer.flush()
print(f"\n{MESSAGE_COUNT} messages produced.")
print(f"murmur2(account_id) % 4 = deterministic partition per account.")
print(f"All orders per account on same partition = ordering guaranteed.")
