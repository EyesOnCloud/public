import json
import time
from confluent_kafka import Consumer, KafkaError

# Auto-commit with very short interval to make the
# loss scenario reproducible in the lab
consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-autocommit',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'true',
    'auto.commit.interval.ms': '2000',  # 2 seconds for lab visibility
})

consumer.subscribe(['orders-commit-lab'])

print("AUTO-COMMIT CONSUMER STARTED")
print("auto.commit.interval.ms=2000 — offset commits every 2 seconds")
print("Simulating slow processing (1.5s per message)")
print("Kill with Ctrl+C after a few messages to see data loss scenario")
print("=" * 60)

processed = 0
try:
    while True:
        msg = consumer.poll(timeout=5.0)
        if msg is None:
            print("No messages. Exiting.")
            break
        if msg.error():
            continue

        order = json.loads(msg.value().decode())

        print(f"POLLED:  offset={msg.offset()} "
              f"order={order['order_id']} "
              f"amount=${order['amount']}")

        # Simulate slow processing — database write takes 1.5 seconds
        # Auto-commit fires at 2s intervals
        # After ~1 commit cycle: offsets are committed while
        # some messages in the polled batch are still being processed
        print(f"  Processing... (1.5s simulated DB write)", flush=True)
        time.sleep(1.5)

        print(f"  PROCESSED: order={order['order_id']} "
              f"written to DB")
        processed += 1

except KeyboardInterrupt:
    print(f"\nKilled after processing {processed} messages.")
    print("Check committed offset vs actual processed count.")
    print("Run: kafka-consumer-groups.sh to see committed position.")
finally:
    # Do NOT call consumer.close() here intentionally
    # to simulate abrupt crash (no clean shutdown commit)
    print("Consumer terminated without clean close.")
