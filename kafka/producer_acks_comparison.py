import time
import sys
sys.path.insert(0, '/root')

from confluent_kafka import Producer
from payload_generator import generate_payload_bytes

TOPIC = 'orders-throughput-lab'
MESSAGE_COUNT = 10_000

def run_producer_with_acks(acks_value, label, description):
    delivered = 0
    failed = 0
    # For acks=0 the callback fires immediately without
    # broker confirmation — track separately
    callback_fired = 0

    def delivery_callback(err, msg):
        nonlocal delivered, failed, callback_fired
        callback_fired += 1
        if err is not None:
            failed += 1
        else:
            delivered += 1

    config = {
        'bootstrap.servers': 'localhost:9092',
        'client.id': f'throughput-lab-acks-{str(acks_value).replace("-","all")}',
        'acks': str(acks_value),
        'linger.ms': 50,
        'batch.size': 65536,
        'batch.num.messages': 10000,
        'compression.type': 'lz4',
        # Required for acks=all with idempotence (best practice)
        # Only set when acks=all
        **({'enable.idempotence': 'true'} if acks_value == -1 else {}),
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
    print(f"  Description: {description}")
    print(f"  Total time:   {elapsed:.3f}s")
    print(f"  Throughput:   {throughput:,.0f} msg/s")
    print(f"  Delivered:    {delivered:,}")
    print(f"  Failed:       {failed:,}")
    print(f"  Callbacks:    {callback_fired:,}")
    return throughput

print("=" * 60)
print("ACKS LEVEL COMPARISON")
print(f"Sending {MESSAGE_COUNT:,} messages | lz4 | linger.ms=50 | batch=64KB")
print("=" * 60)

results = {}

results['acks=0'] = run_producer_with_acks(
    0,
    "ACKS=0 — Fire and Forget",
    "No acknowledgment. Max throughput. Zero durability guarantee."
)

results['acks=1'] = run_producer_with_acks(
    1,
    "ACKS=1 - Leader Acknowledgment",
    "Leader writes to log, responds. Followers may lag. Moderate durability."
)

results['acks=all'] = run_producer_with_acks(
    -1,
    "ACKS=ALL - Full ISR Acknowledgment",
    "All ISR members confirm. Max durability. Lower throughput."
)

print("\n" + "=" * 60)
print("SUMMARY - acks impact on throughput")
print("=" * 60)
baseline = results['acks=1']
for label, tput in results.items():
    delta = ((tput - baseline) / baseline) * 100
    sign = "+" if delta >= 0 else ""
    print(f"  {label:12s}: {tput:>10,.0f} msg/s   ({sign}{delta:.1f}% vs acks=1)")

print("\nDurability decision guide:")
print("  acks=0   → metrics, telemetry, best-effort streams")
print("  acks=1   → logs, analytics, non-critical pipelines")
print("  acks=all → payments, financial events, audit trails")
