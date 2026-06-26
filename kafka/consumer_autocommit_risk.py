import json
import time
from confluent_kafka import Consumer, KafkaError

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-autocommit',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'true',
    'auto.commit.interval.ms': '2000',
})

consumer.subscribe(['orders-commit-lab'])

print("AUTO-COMMIT CONSUMER STARTED")
print("Fetching in batches of 10. Processing 3s per message.")
print("Auto-commit fires at 2s — BEFORE batch finishes processing.")
print("Kill with Ctrl+C mid-batch to see committed-but-unprocessed offsets.")
print("=" * 60)

processed = 0
try:
    while True:
        messages = consumer.consume(num_messages=10, timeout=5.0)
        if not messages:
            print("No messages.")
            break

        print(f"\nBATCH POLLED: {len(messages)} messages")
        print(f"Offsets in this batch: {messages[0].offset()} → {messages[-1].offset()}")
        print("Auto-commit will fire at 2s mark — mid-batch")
        print("-" * 40)

        for msg in messages:
            if msg.error():
                continue
            order = json.loads(msg.value().decode())
            print(f"PROCESSING offset={msg.offset()} "
                  f"order={order['order_id']} amount=${order['amount']}")
            print(f"  Simulating 3s DB write...", flush=True)
            time.sleep(3)
            print(f"  DONE: offset={msg.offset()} written to DB")
            processed += 1

except KeyboardInterrupt:
    print(f"\n--- CRASH SIMULATED ---")
    print(f"Messages fully processed: {processed}")
    print(f"Check broker committed offset — it will be AHEAD of {processed}")
    print(f"Those skipped messages = permanent data loss for this group")
finally:
    print("Consumer terminated without clean close (no final commit)")
