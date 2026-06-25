import time
import sys
sys.path.insert(0, '/root')

from confluent_kafka import Producer
from payload_generator import generate_payload_bytes

TOPIC = 'orders-throughput-demo'
MESSAGE_COUNT = 10_000

delivered = 0
failed = 0

def delivery_callback(err, msg):
    global delivered, failed
    if err is not None:
        failed += 1
    else:
        delivered += 1

config = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'throughput-lab-batching',
    'acks': '1',
    'linger.ms': 50,         # Wait up to 50ms to fill a batch
    'batch.size': 65536,     # 64KB batch size (up from 16KB default)
    'batch.num.messages': 10000,  # Max messages per batch
    'compression.type': 'none',
}

print("=" * 60)
print("TUNED PRODUCER - Batching Optimized")
print(f"  acks=1 | linger.ms=50 | batch.size=65536 | compression=none")
print(f"  Sending {MESSAGE_COUNT:,} messages to {TOPIC}")
print("=" * 60)

producer = Producer(config)
start_time = time.time()

for i in range(MESSAGE_COUNT):
    key, value = generate_payload_bytes()
    if i % 1000 == 0:
        producer.poll(0)
    producer.produce(
        topic=TOPIC,
        key=key,
        value=value,
        callback=delivery_callback
    )

producer.flush()
end_time = time.time()

elapsed = end_time - start_time
throughput = MESSAGE_COUNT / elapsed

print(f"\nResults:")
print(f"  Total time:      {elapsed:.3f} seconds")
print(f"  Throughput:      {throughput:,.0f} messages/second")
print(f"  Delivered:       {delivered:,}")
print(f"  Failed:          {failed:,}")
print(f"  vs Baseline:     compare with your baseline number")
