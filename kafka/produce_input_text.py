import time
from confluent_kafka import Producer

p = Producer({
    'bootstrap.servers': '192.168.100.21:9092,192.168.100.22:9092,192.168.100.23:9092'
})

sentences = [
    "kafka enables real-time stream processing at enterprise scale",
    "payment fraud detection requires low latency kafka consumers",
    "distributed systems use kafka for reliable event streaming",
    "kafka partitions provide ordered message delivery guarantees",
    "stream processing topologies transform and aggregate events",
]

i = 0

print("[PRODUCER] Starting continuous stream...\n")

while True:
    sentence = sentences[i % len(sentences)]

    p.produce(
        'input-text',
        value=sentence.encode('utf-8')
    )

    # trigger delivery callbacks + internal flush
    p.poll(0)

    print(f"Produced: {sentence}")

    i += 1

    time.sleep(1)
