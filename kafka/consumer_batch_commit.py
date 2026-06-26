import json
import time
from confluent_kafka import Consumer

COMMIT_EVERY_N = 10

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-batch-commit',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'false',
})

consumer.subscribe(['orders-commit-lab'])

print("BATCH COMMIT CONSUMER")
print(f"Commits every {COMMIT_EVERY_N} messages.")
print(f"Crash between commits = reprocess up to {COMMIT_EVERY_N} messages.")
print("=" * 55)

processed = 0
last_committed_offset = None
batch_start_offset = None

try:
    while True:
        msg = consumer.poll(timeout=3.0)

        if msg is None:
            if processed > 0:
                # Final commit — covers any messages processed since last batch commit
                # Critical: without this, last (processed % N) messages
                # are uncommitted when consumer exits cleanly
                consumer.commit(asynchronous=False)
                print(f"\n[FINAL COMMIT] Flushed remaining uncommitted messages.")
            break

        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        order = json.loads(msg.value().decode())

        # Track where this batch started
        if processed % COMMIT_EVERY_N == 0:
            batch_start_offset = msg.offset()

        print(f"  offset={msg.offset():3d} | "
              f"order={order['order_id']} | "
              f"amount=${order['amount']}", flush=True)

        time.sleep(0.05)
        processed += 1

        # Commit every COMMIT_EVERY_N messages
        if processed % COMMIT_EVERY_N == 0:
            consumer.commit(asynchronous=False)
            last_committed_offset = msg.offset()
            print(f"\n  >>> BATCH COMMITTED offsets {batch_start_offset}–{msg.offset()} "
                  f"({COMMIT_EVERY_N} messages) <<<")
            print(f"  Next read will start from offset {msg.offset() + 1}")
            print(f"  Crash NOW would cause 0 reprocessing (just committed)\n")

        if processed >= 30:
            consumer.commit(asynchronous=False)
            last_committed_offset = msg.offset()
            print(f"\n[FINAL COMMIT] offset={msg.offset()}. Stopping.")
            break

finally:
    consumer.close()

print(f"\nProcessed              : {processed}")
print(f"Last committed offset  : {last_committed_offset}")
print(f"Worst-case reprocessing: up to {COMMIT_EVERY_N} messages")
