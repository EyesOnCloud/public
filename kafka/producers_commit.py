import json
import uuid
import random
from confluent_kafka import Producer

producer = Producer({'bootstrap.servers': 'localhost:9092'})

statuses = ['PLACED', 'PLACED', 'PLACED', 'PAYMENT_PENDING', 'PLACED']
methods = ['credit_card', 'debit_card', 'paypal', 'apple_pay']
products = [
    ('PROD-1001', 'Wireless Headphones', 149.99),
    ('PROD-1002', 'Mechanical Keyboard', 89.99),
    ('PROD-1003', 'USB-C Hub', 49.99),
    ('PROD-1004', 'Monitor Stand', 199.99),
    ('PROD-1005', 'Laptop Stand', 79.99),
]

for i in range(50):
    prod = random.choice(products)
    qty = random.randint(1, 3)
    amount = round(prod[2] * qty, 2)
    order = {
        'order_id': f'ORD-{str(uuid.uuid4().hex[:8]).upper()}',
        'sequence': i,   # sequence number so we can track processing order
        'customer_id': f'CUST-{random.randint(1000, 9999)}',
        'product_id': prod[0],
        'product_name': prod[1],
        'quantity': qty,
        'amount': amount,
        'payment_method': random.choice(methods),
        'status': random.choice(statuses),
        'placed_at': f'2026-07-01T{10 + i//6:02d}:{(i*2)%60:02d}:00Z'
    }
    producer.produce(
        topic='orders-commit-lab',
        key=order['order_id'].encode(),
        value=json.dumps(order).encode()
    )

producer.flush()
print("50 order events produced to orders-commit-lab")
