import json
from confluent_kafka import Consumer, KafkaError

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-v1',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True
})

consumer.subscribe(['orders-message-anatomy'])

print("Consumer v1 started. Waiting for messages...")
print("Schema expectation: order_id, customer_id, customer_email, items, subtotal, tax, total, currency, status, placed_at, shipping_address\n")

processed = 0
try:
    while True:
        msg = consumer.poll(timeout=5.0)

        if msg is None:
            print("No messages for 5 seconds. Exiting.")
            break

        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(f"Consumer error: {msg.error()}")
                break

        # Deserialize key and value
        key = msg.key().decode('utf-8') if msg.key() else None
        raw_value = msg.value().decode('utf-8')

        try:
            order = json.loads(raw_value)
        except json.JSONDecodeError as e:
            print(f"JSON parse failed for key={key}: {e}")
            print(f"Raw value: {raw_value[:100]}")
            continue

        # Read headers
        headers = {k: v.decode('utf-8') for k, v in msg.headers()} \
                  if msg.headers() else {}

        print(f"--- Message ---")
        print(f"  Partition: {msg.partition()}  Offset: {msg.offset()}")
        print(f"  Key: {key}")
        print(f"  Headers: {headers}")
        print(f"  order_id: {order.get('order_id')}")
        print(f"  customer_email: {order.get('customer_email')}")
        print(f"  total: {order.get('total')} {order.get('currency')}")
        print(f"  status: {order.get('status')}")
        print(f"  items count: {len(order.get('items', []))}")
        print(f"  ship_to: {order.get('shipping_address', {}).get('city')}, "
              f"{order.get('shipping_address', {}).get('state')}")
        print()
        processed += 1

finally:
    consumer.close()
    print(f"Consumer closed. Processed {processed} messages.")
