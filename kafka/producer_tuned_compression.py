import time
import sys
sys.path.insert(0, '/root')

from confluent_kafka import Producer
from payload_generator import generate_payload_bytes

TOPIC = 'orders-throughput-demo'
MESSAGE_COUNT = 10_000

def run_producer(compression_type, label):
    delivered = 0
    failed = 0

    def delivery_callback(err, msg):
        nonlocal delivered, failed
        if err is not None:
            failed += 1
        else:
            delivered += 1

    config = {
        'bootstrap.servers': 'localhost:9092',
        'client.id': f'throughput-lab-{compression_type}',
        'acks': '1',
        'linger.ms': 50,
        'batch.size': 65536,
        'batch.num.messages': 10000,
        'compression.type': compression_type,
    }

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
    elapsed = time.time() - start_time
    throughput = MESSAGE_COUNT / elapsed

    print(f"\n{label}")
    print(f"  compression={compression_type} | linger.ms=50 | batch.size=65536")
    print(f"  Total time:  {elapsed:.3f}s")
    print(f"  Throughput:  {throughput:,.0f} msg/s")
    print(f"  Delivered:   {delivered:,} | Failed: {failed:,}")
    return throughput

print("=" * 60)
print("COMPRESSION COMPARISON")
print(f"Sending {MESSAGE_COUNT:,} messages per codec")
print("=" * 60)

results = {}
for codec, label in [
    ('none',   'NO COMPRESSION (batching only)'),
    ('lz4',    'LZ4 COMPRESSION'),
    ('snappy', 'SNAPPY COMPRESSION'),
    ('gzip',   'GZIP COMPRESSION'),
    ('zstd',   'ZSTD COMPRESSION'),
]:
    results[codec] = run_producer(codec, label)

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
baseline = results['none']
for codec, tput in results.items():
    delta = ((tput - baseline) / baseline) * 100
    sign = "+" if delta >= 0 else ""
    print(f"  {codec:8s}: {tput:>10,.0f} msg/s   ({sign}{delta:.1f}% vs no compression)")
