import json
from confluent_kafka import Consumer, KafkaError

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor-v1-defensive',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True
})

consumer.subscribe(['orders-message-anatomy'])

def normalize_order(order, schema_version):
    """
    Normalizes order payload to internal canonical format
    regardless of producer schema version.
    Returns normalized dict or raises ValueError for unknown schema.
    """
    if schema_version == '1.0' or schema_version is None:
        return {
            'order_id': order.get('order_id'),
            'customer_email': order.get('customer_email'),
            'total_amount': float(order.get('total', 0)),
            'currency': order.get('currency', 'USD'),
            'city': order.get('shipping_address', {}).get('city'),
            'state': order.get('shipping_address', {}).get('state'),
            'status': order.get('status'),
            'schema_version': '1.0'
        }
    elif schema_version == '2.0':
        raw_total = order.get('total', '0 USD')
        # Handle "97.19 USD" format from v2 producer
        total_parts = raw_total.split()
        total_amount = float(total_parts[0]) if total_parts else 0.0
        currency = total_parts[1] if len(total_parts) > 1 else 'USD'
        return {
            'order_id': order.get('order_id'),
            'customer_email': order.get('contact_email'),  # renamed field
            'total_amount': total_amount,
            'currency': currency,
            'city': None,  # field removed in v2 — log warning
            'state': None,
            'status': order.get('status'),
            'schema_version': '2.0',
            '_warning': 'shipping_address not available in schema v2'
        }
    else:
        raise ValueError(f"Unknown schema version: {schema_version}")

print("Defensive consumer started.\n")
try:
    while True:
        msg = consumer.poll(timeout=5.0)
        if msg is None:
            print("No messages. Exiting.")
            break
        if msg.error():
            continue

        key = msg.key().decode('utf-8') if msg.key() else None
        headers = {k: v.decode('utf-8') for k, v in msg.headers()} \
                  if msg.headers() else {}
        schema_version = headers.get('schema-version')

        try:
            raw_order = json.loads(msg.value().decode('utf-8'))
            normalized = normalize_order(raw_order, schema_version)

            print(f"order_id: {normalized['order_id']}  "
                  f"schema_v: {normalized['schema_version']}  "
                  f"email: {normalized['customer_email']}  "
                  f"total: {normalized['total_amount']} {normalized['currency']}")
            if '_warning' in normalized:
                print(f"  WARNING: {normalized['_warning']}")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Processing failed for key={key}: {e}")
            # In production: produce to dead letter topic here

finally:
    consumer.close()
