import json
import sys
import time
import signal
from confluent_kafka import Consumer, KafkaError


if len(sys.argv) < 2:
    print("Usage: python3 consumer_group_member.py <instance-name>")
    sys.exit(1)


INSTANCE_NAME = sys.argv[1]
GROUP_ID = 'order-processors'
TOPIC = 'orders-group-demo'


# All three brokers in bootstrap list
BOOTSTRAP_SERVERS = '192.168.100.21:9092,192.168.100.22:9092,192.168.100.23:9092'


shutdown_flag = False
messages_processed = False


def handle_shutdown(signum, frame):
    global shutdown_flag

    print(f"\n[{INSTANCE_NAME}] Shutdown signal. Finishing current poll.")
    shutdown_flag = True


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)



def on_assign(consumer, partitions):

    partition_nums = [p.partition for p in partitions]

    print(f"\n[{INSTANCE_NAME}] *** PARTITIONS ASSIGNED: {partition_nums} ***")
    print(f"[{INSTANCE_NAME}]     Owns {len(partitions)} partition(s)")


    # Show assigned partitions
    for p in partitions:

        print(f"[{INSTANCE_NAME}]     Partition {p.partition} "
              f"— reading from broker leader for this partition")


    sys.stdout.flush()



def on_revoke(consumer, partitions):

    global messages_processed


    partition_nums = [p.partition for p in partitions]


    print(f"\n[{INSTANCE_NAME}] *** PARTITIONS REVOKED: {partition_nums} ***")
    print(f"[{INSTANCE_NAME}]     Rebalance triggered — committing offsets before handoff")


    # Commit only if messages were actually consumed
    if messages_processed:

        try:
            consumer.commit(asynchronous=False)

            print(f"[{INSTANCE_NAME}]     Offsets committed successfully")


        except Exception as e:

            print(f"[{INSTANCE_NAME}]     Commit failed/skipped: {e}")


    else:

        print(f"[{INSTANCE_NAME}]     No offsets stored — skipping commit")


    sys.stdout.flush()



def on_lost(consumer, partitions):

    partition_nums = [p.partition for p in partitions]


    print(f"\n[{INSTANCE_NAME}] *** PARTITIONS LOST (unclean): {partition_nums} ***")
    print(f"[{INSTANCE_NAME}]     No commit — partitions lost, another consumer taking over")


    sys.stdout.flush()





consumer = Consumer({

    'bootstrap.servers': BOOTSTRAP_SERVERS,

    'group.id': GROUP_ID,

    'client.id': f'{GROUP_ID}-{INSTANCE_NAME}',

    'auto.offset.reset': 'earliest',

    'enable.auto.commit': 'false',

    'session.timeout.ms': '10000',

    'heartbeat.interval.ms': '3000',

    'max.poll.interval.ms': '30000',

    'partition.assignment.strategy': 'roundrobin'

})




consumer.subscribe(

    [TOPIC],

    on_assign=on_assign,

    on_revoke=on_revoke,

    on_lost=on_lost

)




print(f"[{INSTANCE_NAME}] Started | group={GROUP_ID} | topic={TOPIC}")

print(f"[{INSTANCE_NAME}] Bootstrap: {BOOTSTRAP_SERVERS}")

print(f"[{INSTANCE_NAME}] Waiting for partition assignment...")


sys.stdout.flush()



message_counts = {}



try:


    while not shutdown_flag:


        msg = consumer.poll(timeout=1.0)



        if msg is None:

            continue



        if msg.error():


            if msg.error().code() == KafkaError._PARTITION_EOF:

                continue


            print(f"[{INSTANCE_NAME}] Error: {msg.error()}")

            continue




        partition = msg.partition()

        offset = msg.offset()



        try:

            order = json.loads(
                msg.value().decode('utf-8')
            )


            order_id = order.get('order_id', 'UNKNOWN')

            account_id = order.get('account_id', 'UNKNOWN')

            amount = order.get('amount', 0)

            sequence = order.get('sequence', -1)



        except Exception:


            order_id = 'PARSE_ERROR'

            account_id = 'UNKNOWN'

            amount = 0

            sequence = -1





        message_counts[partition] = message_counts.get(partition, 0) + 1

        messages_processed = True




        print(

            f"[{INSTANCE_NAME}] P{partition}:O{offset:4d} | "

            f"order={order_id} | "

            f"account={account_id} | "

            f"amount=${amount:7.2f} | "

            f"seq={sequence:3d}",

            flush=True

        )



        time.sleep(0.05)



        consumer.commit(asynchronous=False)






finally:


    try:

        consumer.unsubscribe()

        consumer.close()


    except Exception:

        pass



    print(f"\n[{INSTANCE_NAME}] Closed cleanly.")

    print(f"[{INSTANCE_NAME}] Messages per partition: {message_counts}")

    sys.stdout.flush()
