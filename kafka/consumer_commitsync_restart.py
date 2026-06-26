import json
import time
from confluent_kafka import Consumer

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-crash-sim',   # Same group — resumes from committed position
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'false',
})

consumer.subscribe(['orders-commit-lab'])

print("RESTARTED CONSUMER — group=order-processor-crash-sim")
print("Last committed offset = 2")
print("Expecting first message to be offset=2 — the pre-crash duplicate")
print("=" * 60)

processed = 0

try:
    while True:
        msg = consumer.poll(timeout=5.0)
        if msg is None:
            if processed > 0:
                break
            continue
        if msg.error():
            continue

        order = json.loads(msg.value().decode())

        if processed == 0:
            print(f"\nFIRST MESSAGE AFTER RESTART:")
            print(f"  offset={msg.offset()} order={order['order_id']}")
            print(f"  *** THIS MESSAGE WAS ALREADY PROCESSED BEFORE CRASH ***")
            print(f"  It exists in DB from previous run.")
            print(f"  This is AT-LEAST-ONCE — duplicate delivery, not data loss.")
            print(f"  Idempotent processing logic must handle this duplicate.")
        else:
            print(f"  offset={msg.offset()} order={order['order_id']} (new)")

        time.sleep(0.1)
        consumer.commit(asynchronous=False)
        processed += 1

        if processed >= 5:
            print(f"\nStopping after 5 messages.")
            break

finally:
    consumer.close()

print(f"\nProcessed {processed} messages after restart.")
print(f"Offset=2 was duplicate. Offsets 3+ were new.")
