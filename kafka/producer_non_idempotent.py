import json
import time
import uuid
from confluent_kafka import Producer

TOPIC = 'payments-non-idempotent'

def delivery_callback(err, msg):
    if err is not None:
        print(f"  DELIVERY FAILED: {err}")
    else:
        print(f"  Delivered: offset={msg.offset()} "
              f"partition={msg.partition()} "
              f"key={msg.key().decode()}")

config = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'payments-producer-non-idempotent',
    'acks': '1',
    'enable.idempotence': 'false',
    # retries=0 here because we are manually simulating the retry
    # to make the duplicate visible and explicit
    'retries': '0',
}

producer = Producer(config)

print("=" * 65)
print("NON-IDEMPOTENT PRODUCER - Simulating network retry duplicates")
print("=" * 65)

# Generate realistic payment events
payments = [
    {
        "payment_id": "PAY-" + uuid.uuid4().hex[:8].upper(),
        "order_id": "ORD-10101",
        "customer_id": "CUST-5501",
        "amount": 249.99,
        "currency": "USD",
        "method": "credit_card",
        "card_last4": "4242",
        "status": "AUTHORIZED",
        "processor_ref": "STRIPE-" + uuid.uuid4().hex[:12].upper(),
        "timestamp": "2024-07-01T14:00:00Z"
    },
    {
        "payment_id": "PAY-" + uuid.uuid4().hex[:8].upper(),
        "order_id": "ORD-10102",
        "customer_id": "CUST-6612",
        "amount": 89.50,
        "currency": "USD",
        "method": "paypal",
        "card_last4": None,
        "status": "AUTHORIZED",
        "processor_ref": "PP-" + uuid.uuid4().hex[:12].upper(),
        "timestamp": "2024-07-01T14:01:00Z"
    },
    {
        "payment_id": "PAY-" + uuid.uuid4().hex[:8].upper(),
        "order_id": "ORD-10103",
        "customer_id": "CUST-7723",
        "amount": 1200.00,
        "currency": "USD",
        "method": "credit_card",
        "card_last4": "9999",
        "status": "AUTHORIZED",
        "processor_ref": "STRIPE-" + uuid.uuid4().hex[:12].upper(),
        "timestamp": "2024-07-01T14:02:00Z"
    },
]

print("\nStep 1: Producing payment events normally...")
for payment in payments:
    key = payment["payment_id"].encode('utf-8')
    value = json.dumps(payment).encode('utf-8')
    producer.produce(topic=TOPIC, key=key, value=value,
                     callback=delivery_callback)
    producer.poll(0)

producer.flush()
print(f"\n  {len(payments)} payment events produced successfully.")

print("\nStep 2: Simulating network retry - re-producing the SAME messages...")
print("  (This simulates what happens when ack is lost and producer retries)")
print()

# Simulate retry: produce the identical messages again
# In real retry scenarios, the producer re-sends the exact same
# message bytes including the same key and value content
for payment in payments:
    key = payment["payment_id"].encode('utf-8')
    value = json.dumps(payment).encode('utf-8')
    print(f"  RETRY: {payment['payment_id']} "
          f"amount={payment['amount']} "
          f"order={payment['order_id']}")
    producer.produce(topic=TOPIC, key=key, value=value,
                     callback=delivery_callback)
    producer.poll(0)

producer.flush()
print(f"\n  {len(payments)} messages re-produced (simulated retries).")
print(f"\nTotal messages in topic: {len(payments) * 2} "
      f"(should be {len(payments)} — we have DUPLICATES)")
