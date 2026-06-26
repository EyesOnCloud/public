import json
import time
import os
from confluent_kafka import Consumer

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-crash-sim',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'false',
})

consumer.subscribe(['orders-commit-lab'])

print("CRASH SIMULATION CONSUMER")
print("Crashes AFTER processing message #3 but BEFORE commitSync")
print("Offset for message #3 will NOT be committed")
print("Restart will reprocess message #3 — at-least-once in action")
print("=" * 55)

processed = 0

try:
    while True:
        msg = consumer.poll(timeout=5.0)
        if msg is None:
            break
        if msg.error():
            continue

        order = json.loads(msg.value().decode())

        print(f"\nPOLLED:    offset={msg.offset()} order={order['order_id']}")
        print(f"  [PROCESSING] DB write...", flush=True)
        time.sleep(0.2)
        print(f"  [PROCESSED]  order={order['order_id']} written to DB")

        if processed == 2:   # 0-indexed — this is the 3rd message
            print(f"\n  *** SIMULATED CRASH (SIGKILL / OOM) ***")
            print(f"  order={order['order_id']} at offset={msg.offset()} IS in DB")
            print(f"  commitSync was NOT called — offset={msg.offset()} NOT committed")
            print(f"  Broker still thinks last committed = offset {msg.offset() - 1 + 1}")
            print(f"  Restart will reprocess from offset {msg.offset()}")
            os._exit(1)   # Hard kill — no finally, no consumer.close()
                          # Simulates kernel OOM kill or SIGKILL

        consumer.commit(asynchronous=False)
        print(f"  [COMMITTED]  offset={msg.offset()}")
        processed += 1

finally:
    pass
