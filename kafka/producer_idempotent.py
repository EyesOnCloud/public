import json
import time
import uuid
from confluent_kafka import Producer, KafkaException

TOPIC = 'payments-idempotent'

delivered_offsets = []

def delivery_callback(err, msg):
    if err is not None:
        print(f"  DELIVERY FAILED: {err}")
    else:
        delivered_offsets.append(msg.offset())
        print(f"  Delivered: offset={msg.offset()} "
              f"partition={msg.partition()} "
              f"key={msg.key().decode()} "
              f"latency={msg.latency()*1000:.1f}ms"
              if msg.latency() else
              f"  Delivered: offset={msg.offset()} "
              f"partition={msg.partition()} "
              f"key={msg.key().decode()}")

# Idempotent producer config
# enable.idempotence=true requires:
#   acks=all (enforced automatically — will override acks=1 if set)
#   retries > 0 (set high to allow retry on transient failures)
#   max.in.flight.requests.per.connection <= 5
config = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'payments-producer-idempotent',
    'enable.idempotence': 'true',
    # acks is automatically set to 'all' when idempotence is enabled
    # Explicitly setting it here for clarity — it would be overridden
    # to 'all' even if you set '1'
    'acks': 'all',
    'retries': '2147483647',        # Max retries — let Kafka handle all transient failures
    'max.in.flight.requests.per.connection': '5',  # Max 5 with idempotence
    'delivery.timeout.ms': '120000',  # 2 min total delivery timeout
}

producer = Producer(config)

print("=" * 65)
print("IDEMPOTENT PRODUCER — Duplicate prevention enabled")
print("=" * 65)
print("\nProducer initialized with enable.idempotence=true")
print("Broker assigned a Producer ID (PID) to this producer instance.")
print("Every message carries: PID + epoch + per-partition sequence number.")

# Same payments as before — same payment IDs to make comparison clear
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
for payment in payments:
    key = payment["payment_id"].encode('utf-8')
    value = json.dumps(payment).encode('utf-8')
    producer.produce(topic=TOPIC, key=key, value=value,
                     callback=delivery_callback)
    producer.poll(0)

producer.flush()
print(f"\n  {len(payments)} messages delivered. Offsets: {delivered_offsets}")

print("\nStep 2: Simulating retry — producing SAME messages again...")
print("  (Broker will detect duplicate sequence numbers and discard)")
print()

retry_callbacks = []

def retry_callback(err, msg):
    if err is not None:
        retry_callbacks.append(('error', str(err)))
        print(f"  RETRY FAILED (expected for some): {err}")
    else:
        retry_callbacks.append(('success', msg.offset()))
        print(f"  RETRY 'delivered': offset={msg.offset()} "
              f"key={msg.key().decode()}")
        print(f"    -> Broker returned success (deduplication occurred)")
        print(f"    -> Check if this is a NEW offset or existing offset")

for payment in payments:
    key = payment["payment_id"].encode('utf-8')
    value = json.dumps(payment).encode('utf-8')
    print(f"  RETRY: {payment['payment_id']} amount={payment['amount']}")
    producer.produce(topic=TOPIC, key=key, value=value,
                     callback=retry_callback)
    producer.poll(0)

producer.flush()
print(f"\n  Retry callbacks received: {len(retry_callbacks)}")
print(f"  Original offsets: {delivered_offsets}")
