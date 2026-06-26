import json
import time
import threading
from confluent_kafka import Consumer

# Thread-safe commit tracking
commit_stats = {
    'attempted': 0,
    'succeeded': 0,
    'failed': 0,
    'errors': []
}
stats_lock = threading.Lock()

def on_commit(err, partitions):
    """
    Fires asynchronously when broker responds to commit request.
    By the time this executes, consumer has already moved on
    to processing later offsets.

    partitions: list of TopicPartition objects with committed offsets
    err: None on success, KafkaError on failure
    """
    with stats_lock:
        commit_stats['attempted'] += 1
        if err is not None:
            commit_stats['failed'] += 1
            commit_stats['errors'].append(str(err))
            print(f"\n  [COMMIT ASYNC FAILED] {err}")
            print(f"  Uncommitted offsets — consumer already advanced past this point")
            print(f"  On restart: reprocess from last successful committed offset")
        else:
            commit_stats['succeeded'] += 1
            for p in partitions:
                print(f"  [COMMIT ASYNC OK] "
                      f"topic={p.topic} "
                      f"partition={p.partition} "
                      f"offset={p.offset}", flush=True)

# on_commit registered in config — correct confluent-kafka-python pattern
consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-commitasync',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'false',
    'on_commit': on_commit,             # callback registered here, NOT in commit() call
})

consumer.subscribe(['orders-commit-lab'])

print("COMMITASYNC CONSUMER STARTED")
print("enable.auto.commit=false — manual async commit after each message")
print("Commit callback fires later — consumer does not block")
print("Watch: COMMIT SENT prints before COMMIT ASYNC OK")
print("=" * 60)

processed = 0
start_time = time.time()

try:
    while True:
        msg = consumer.poll(timeout=2.0)

        if msg is None:
            if processed > 0:
                print("No new messages.")
                break
            continue

        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        order = json.loads(msg.value().decode())

        print(f"\nPOLLED:       offset={msg.offset()} "
              f"order={order['order_id']} "
              f"amount=${order['amount']}")

        # Simulate processing
        time.sleep(0.1)
        print(f"  [PROCESSED]   order={order['order_id']} written to DB")

        # commitAsync — returns immediately
        # Callback (on_commit) fires when broker responds
        # Consumer does NOT block here
        consumer.commit(asynchronous=True)
        print(f"  [COMMIT SENT] async commit dispatched — broker not yet confirmed")

        processed += 1

        if processed >= 10:
            print(f"\nReached 10 messages.")
            break

    # Critical: flush pending async commits before shutdown
    # Without this, last N commits may never receive broker ack
    # consumer.close() calls commitSync internally for pending offsets
    print("\nFlushing pending async commits via consumer.close()...")

except KeyboardInterrupt:
    print("\nInterrupted.")
except Exception as e:
    print(f"\nError: {e}")
finally:
    # consumer.close() triggers final commitSync for any unacknowledged
    # async commits — this is the recommended shutdown pattern
    consumer.close()

elapsed = time.time() - start_time
print(f"\n{'='*60}")
print(f"Processed         : {processed}")
print(f"Total time        : {elapsed:.2f}s")
print(f"Commit attempts   : {commit_stats['attempted']}")
print(f"Commit successes  : {commit_stats['succeeded']}")
print(f"Commit failures   : {commit_stats['failed']}")
if commit_stats['errors']:
    print(f"Errors            : {commit_stats['errors']}")
