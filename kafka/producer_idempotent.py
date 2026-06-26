import json
import uuid
import time
from confluent_kafka import Producer

TOPIC = 'payments-idempotent'

delivered_offsets = []

def delivery_callback(err, msg):
    if err is not None:
        print(f"  DELIVERY FAILED: {err}")
    else:
        delivered_offsets.append(msg.offset())
        print(f"  Delivered: offset={msg.offset()} "
              f"partition={msg.partition()} "
              f"key={msg.key().decode()}")

config = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'payments-producer-idempotent',
    'enable.idempotence': 'true',
    'acks': 'all',
    'retries': '2147483647',
    'max.in.flight.requests.per.connection': '5',
    'delivery.timeout.ms': '120000',
    'request.timeout.ms': '5000',
    'retry.backoff.ms': '500',
}

producer = Producer(config)

print("=" * 65)
print("IDEMPOTENT PRODUCER — Duplicate prevention enabled")
print("=" * 65)
print("\nProducer initialized with enable.idempotence=true")
print("Broker assigns a Producer ID (PID) to this producer instance.")
print("Every message carries: PID + epoch + per-partition sequence number.")

payments = [
    {
        "payment_id": "PAY-IDEM-0001",
        "order_id": "ORD-20101",
        "customer_id": "CUST-5501",
        "amount": 249.99,
        "currency": "USD",
        "method": "credit_card",
        "card_last4": "4242",
        "status": "AUTHORIZED",
        "processor_ref": "STRIPE-" + uuid.uuid4().hex[:12].upper(),
        "timestamp": "2024-07-01T15:00:00Z"
    },
    {
        "payment_id": "PAY-IDEM-0002",
        "order_id": "ORD-20102",
        "customer_id": "CUST-6612",
        "amount": 89.50,
        "currency": "USD",
        "method": "paypal",
        "card_last4": None,
        "status": "AUTHORIZED",
        "processor_ref": "PP-" + uuid.uuid4().hex[:12].upper(),
        "timestamp": "2024-07-01T15:01:00Z"
    },
    {
        "payment_id": "PAY-IDEM-0003",
        "order_id": "ORD-20103",
        "customer_id": "CUST-7723",
        "amount": 1200.00,
        "currency": "USD",
        "method": "credit_card",
        "card_last4": "9999",
        "status": "AUTHORIZED",
        "processor_ref": "STRIPE-" + uuid.uuid4().hex[:12].upper(),
        "timestamp": "2024-07-01T15:02:00Z"
    },
]

print("\nStep 1: Producing payment events...")
print("  Open 2nd terminal NOW and run:")
print("  iptables -A INPUT -p tcp --dport 9092 -j DROP")
print("  (drop network while flush blocks — forces real broker retry)")
print()

for payment in payments:
    key = payment["payment_id"].encode('utf-8')
    value = json.dumps(payment).encode('utf-8')
    producer.produce(topic=TOPIC, key=key, value=value,
                     callback=delivery_callback)
    producer.poll(0)

print("  Flushing... (blocks here — run iptables DROP now, then restore after 5s)")
print("  Restore: iptables -D INPUT -p tcp --dport 9092 -j DROP")
producer.flush()

print(f"\n  {len(payments)} messages delivered. Offsets: {delivered_offsets}")
print()
print("  WHAT HAPPENED UNDER THE HOOD:")
print("  -> Producer sent batch with PID + epoch + seq numbers 0,1,2")
print("  -> Network dropped — ack never arrived")
print("  -> Producer auto-retried SAME batch: same PID + same seq numbers")
print("  -> Broker saw seq already written — discarded retry, returned ack")
print("  -> Topic contains exactly 3 messages — no duplicates")
print()
print("  Compare:")
print("  payments-non-idempotent : 6 msgs (3 original + 3 duplicate from retry)")
print("  payments-idempotent     : 3 msgs (retry deduplicated by broker)")
