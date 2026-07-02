import json
import time
import os
from confluent_kafka import Consumer

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-commitsync',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,      # Critical — no background commits
    'session.timeout.ms': 10000,
    'max.poll.interval.ms': '30000',
})

consumer.subscribe(['orders-commit-lab'])

print("COMMITSYNC CONSUMER STARTED")
print("enable.auto.commit=false — offsets committed manually after each message")
print("Sequence: POLL -> PROCESS -> COMMIT -> repeat")
print("=" * 65)

processed = 0
committed_offset = None
simulated_db = {}

try:
    while True:
        msg = consumer.poll(timeout=2.0)

        if msg is None:
            if processed > 0:
                print(f"No new messages. Total processed: {processed}")
                break
            continue

        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        order = json.loads(msg.value().decode())
        order_id = order['order_id']

        print(f"\nPOLLED:     partition={msg.partition()} "
              f"offset={msg.offset()} "
              f"order={order_id} "
              f"amount=${order['amount']}")

        # --- PROCESS ---
        # Crash here = offset not committed = reprocess on restart (safe)
        print(f"  [PROCESSING] Writing to DB...", flush=True)
        time.sleep(0.3)

        simulated_db[order_id] = {
            'order_id': order_id,
            'amount': order['amount'],
            'processed_at': time.time()
        }
        print(f"  [PROCESSED]  order={order_id} written to DB")

        # --- COMMIT ---
        # asynchronous=False = commitSync
        # Blocks until broker writes offset to __consumer_offsets
        # Exception here = offset not committed = reprocess on restart (safe)
        # Both failure modes are safe — at-least-once guaranteed
        try:
            consumer.commit(asynchronous=False)
            committed_offset = msg.offset() + 1
            print(f"  [COMMITTED]  offset={msg.offset()} committed. "
                  f"Next read from offset {committed_offset}")
        except Exception as commit_err:
            print(f"  [COMMIT FAILED] {commit_err}")
            print(f"  Offset not committed — will reprocess on restart")
            raise

        processed += 1

        if processed >= 10:
            print(f"\nReached 10 messages. Stopping for inspection.")
            break

except KeyboardInterrupt:
    print(f"\nInterrupted.")
except Exception as e:
    print(f"\nError: {e}")
finally:
    consumer.close()
    print(f"\n{'='*65}")
    print(f"Consumer closed cleanly.")
    print(f"Messages processed this run : {processed}")
    print(f"Last committed offset       : {committed_offset}")
    print(f"Orders in simulated DB      : {len(simulated_db)}")
