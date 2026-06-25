import time
import sys
sys.path.insert(0, '/root')

from confluent_kafka import Producer
from payload_generator import generate_payload_bytes

TOPIC = 'orders-throughput-demo'
MESSAGE_COUNT = 10_000

# Track delivery outcomes
delivered = 0
failed = 0

def delivery_callback(err, msg):
    global delivered, failed
    if err is not None:
        failed += 1
        print(f"DELIVERY FAILED: {err}", flush=True)
    else:
        delivered += 1

# Baseline config — confluent-kafka defaults
# linger.ms default: 5ms
# batch.size default: 16384 bytes (16KB)
# compression.type default: none
# acks default: -1 (all) for confluent-kafka
# Note: we explicitly set acks=1 for baseline to isolate batching/compression
config = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'throughput-lab-baseline',
    'acks': '1',
    'linger.ms': 0,          # No artificial batching delay
    'batch.size': 16384,     # 16KB - confluent-kafka default
    'compression.type': 'none',
}

print("=" * 60)
print("BASELINE PRODUCER — Default Settings")
print(f"  acks=1 | linger.ms=0 | batch.size=16384 | compression=none")
print(f"  Sending {MESSAGE_COUNT:,} messages to {TOPIC}")
print("=" * 60)

producer = Producer(config)

start_time = time.time()

for i in range(MESSAGE_COUNT):
    key, value = generate_payload_bytes()

    # poll(0) triggers delivery callbacks without blocking
    # Called every 1000 messages to drain the callback queue
    if i % 1000 == 0:
        producer.poll(0)

    producer.produce(
        topic=TOPIC,
        key=key,
        value=value,
        callback=delivery_callback
    )

# flush() blocks until all buffered messages are delivered
# and all delivery callbacks are fired
flush_start = time.time()
producer.flush()
end_time = time.time()

elapsed = end_time - start_time
flush_time = end_time - flush_start
throughput = MESSAGE_COUNT / elapsed

print(f"\nResults:")
print(f"  Total time:      {elapsed:.3f} seconds")
print(f"  Flush time:      {flush_time:.3f} seconds")
print(f"  Throughput:      {throughput:,.0f} messages/second")
print(f"  Delivered:       {delivered:,}")
print(f"  Failed:          {failed:,}")
print(f"  Loss rate:       {(failed/MESSAGE_COUNT)*100:.4f}%")
