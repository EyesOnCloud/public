import json
import time
import threading
from confluent_kafka import Consumer, KafkaError

commit_stats = {'attempted': 0, 'succeeded': 0, 'failed': 0, 'errors': []}
stats_lock = threading.Lock()

def on_commit(err, partitions):
    with stats_lock:
        # _NO_OFFSET = librdkafka internal skip, not a broker error
        # Nothing to commit at that moment — not a failure
        # Suppress it — it pollutes output and confuses engineers
        if err is not None and err.code() == KafkaError._NO_OFFSET:
            return

        commit_stats['attempted'] += 1
        if err is not None:
            commit_stats['failed'] += 1
            commit_stats['errors'].append(str(err))
            print(f"\n  [COMMIT ASYNC FAILED] {err}")
            print(f"  Real broker error — offset uncommitted")
            print(f"  Consumer already advanced — restart reprocesses from last good offset"
        else:
            commit_stats['succeeded'] += 1
            for p in partitions:
                print(f"  [COMMIT ASYNC OK] "
                      f"partition={p.partition} "
                      f"offset={p.offset}", flush=True)

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-commitasync',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'false',
    'on_commit': on_commit,
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
            continue

        order = json.loads(msg.value().decode())

        print(f"\nPOLLED:       offset={msg.offset()} "
              f"order={order['order_id']} "
              f"amount=${order['amount']}")
        time.sleep(0.1)
        print(f"  [PROCESSED]   order={order['order_id']} written to DB")

        consumer.commit(asynchronous=True)
        print(f"  [COMMIT SENT] async commit dispatched — broker not yet confirmed")

        processed += 1
        if processed >= 10:
            print(f"\nReached 10 messages.")
            break

except KeyboardInterrupt:
    print("\nInterrupted.")
finally:
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
