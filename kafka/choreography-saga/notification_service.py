"""
This service is the final step in ALL saga paths.
It subscribes to THREE topics and handles every outcome:
  - INVENTORY_RESERVED: send order confirmation to customer
  - INVENTORY_FAILED:   send inventory failure notification
  - PAYMENTS_FAILED:    send payment failure notification

What notification-service knows:
  INPUT:  inventory.reserved, inventory.failed, payments.failed
  OUTPUT: notifications.sent

What notification-service does NOT know:
  - order-service, payment-service, inventory-service exist
  - How the order was created or how payment was processed
  - It simply sends the appropriate notification based on what
    event it receives

This service subscribing to THREE topics is the key to
how all saga paths — success AND failure — converge
to customer notification without any central coordinator.

This is also the service killed in the lag demonstration (Order 4).
Killing it causes messages to accumulate in inventory.reserved
and payments.failed until the service restarts and catches up.
"""

import json
import uuid
import time
import signal
import sys
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer, KafkaError
import config

C  = config.Colors
SC = config.SERVICE_COLORS['notification-service']

producer = Producer({
    'bootstrap.servers': config.BOOTSTRAP_SERVERS,
    'enable.idempotence': 'true',
    'acks': 'all',
    'retries': '2147483647',
    'max.in.flight.requests.per.connection': '5',
    'compression.type': 'lz4',
    'linger.ms': '5',
    'client.id': 'notification-service-producer',
})

consumer = Consumer({
    'bootstrap.servers':    config.BOOTSTRAP_SERVERS,
    'group.id':             config.NOTIFICATION_SERVICE_GROUP,
    'auto.offset.reset':    'earliest',
    'enable.auto.commit':   'false',
    'max.poll.interval.ms': '30000',
    'session.timeout.ms':   '20000',
    'heartbeat.interval.ms':'6000',
    'client.id':            'notification-service-consumer',
})

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def delivery_callback(err, msg):
    if err:
        print(f"{C.RED}  [DELIVERY FAILED] {err}{C.RESET}")

def send_notification(notification_type, order_data, additional_data=None):
    """
    Simulate sending a customer notification.
    In production: call email service (SendGrid, SES),
    SMS service (Twilio), or push notification service.

    Returns: notification record
    """
    time.sleep(0.2)  # Simulate notification API latency

    customer_email = order_data.get('customer_email', 'unknown@example.com')
    customer_name  = order_data.get('customer_name', 'Customer')
    order_id       = order_data.get('order_id', 'UNKNOWN')
    amount         = order_data.get('total_amount', 0)

    templates = {
        'ORDER_CONFIRMED': {
            'subject': f'Your order {order_id} is confirmed!',
            'body':    (f'Hi {customer_name}, your order {order_id} '
                       f'for ${amount:.2f} has been confirmed and '
                       f'inventory reserved. Estimated delivery: 2-3 business days.'),
            'channel': 'EMAIL',
        },
        'PAYMENT_FAILED': {
            'subject': f'Payment issue with order {order_id}',
            'body':    (f'Hi {customer_name}, we could not process payment '
                       f'for your order {order_id} (${amount:.2f}). '
                       f'Please check your payment method.'),
            'channel': 'EMAIL',
        },
        'INVENTORY_UNAVAILABLE': {
            'subject': f'Item out of stock — order {order_id}',
            'body':    (f'Hi {customer_name}, unfortunately one or more items '
                       f'in your order {order_id} are out of stock. '
                       f'Your payment will be refunded within 3-5 business days.'),
            'channel': 'EMAIL',
        },
    }

    template   = templates.get(notification_type, templates['ORDER_CONFIRMED'])
    notif_id   = f'NOTIF-{uuid.uuid4().hex[:10].upper()}'

    # Simulate notification sent
    print(f"\n{SC}  Sending {template['channel']} notification...")
    print(f"  To:      {customer_email}")
    print(f"  Subject: {template['subject']}")
    print(f"  Body:    {template['body'][:80]}...")

    return {
        'notification_id':   notif_id,
        'notification_type': notification_type,
        'channel':           template['channel'],
        'recipient_email':   customer_email,
        'recipient_name':    customer_name,
        'subject':           template['subject'],
        'status':            'SENT',
        'sent_at':           now_iso(),
    }

def publish_notification_sent(order_id, saga_id, order_data, notification):
    event = {
        'event_id':   str(uuid.uuid4()),
        'event_type': 'NOTIFICATION_SENT',
        'order_id':   order_id,
        'saga_id':    saga_id,
        'event_time': now_iso(),
        'data': {
            **order_data,
            'notification': notification,
        },
    }

    producer.produce(
        topic=config.NOTIFICATIONS_SENT_TOPIC,
        key=order_id.encode('utf-8'),
        value=json.dumps(event).encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()
    return event

def process_message(msg):
    """Process one message from any subscribed topic."""
    topic = msg.topic()

    try:
        event      = json.loads(msg.value().decode('utf-8'))
        event_type = event.get('event_type', 'UNKNOWN')
        order_id   = event.get('order_id', 'UNKNOWN')
        saga_id    = event.get('saga_id', order_id)
        data       = event.get('data', {})
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"{C.RED}  [PARSE ERROR] {e}{C.RESET}")
        return

    print(f"\n{SC}{C.BOLD}{'─'*60}{C.RESET}")
    print(f"{SC}{C.BOLD}[RECEIVED] {event_type}{C.RESET}")
    print(f"  from_topic: {topic}")
    print(f"  order_id:   {order_id}")
    print(f"  saga_id:    {saga_id}")
    print(f"  customer:   {data.get('customer_name')} "
          f"({data.get('customer_email')})")

    # Determine notification type based on which topic the event came from
    if topic == config.INVENTORY_RESERVED_TOPIC:
        # Happy path — order confirmed
        notification_type = 'ORDER_CONFIRMED'
        reserved = data.get('inventory', {}).get('reserved_items', [])
        print(f"  {C.GREEN}Path: HAPPY PATH — order confirmed{C.RESET}")
        print(f"  Reserved items: {len(reserved)}")
        for res in reserved:
            print(f"    {res.get('sku')} → {res.get('reservation_id')} "
                  f"({res.get('warehouse')})")

    elif topic == config.PAYMENTS_FAILED_TOPIC:
        # Payment failure path
        notification_type = 'PAYMENT_FAILED'
        payment = data.get('payment', {})
        print(f"  {C.RED}Path: PAYMENT FAILURE{C.RESET}")
        print(f"  Reason: {payment.get('failure_reason')}")
        print(f"  Message: {payment.get('gateway_message')}")

    elif topic == config.INVENTORY_FAILED_TOPIC:
        # Inventory failure path
        notification_type = 'INVENTORY_UNAVAILABLE'
        failed_items = data.get('inventory', {}).get('failed_items', [])
        print(f"  {C.RED}Path: INVENTORY FAILURE{C.RESET}")
        for fi in failed_items:
            print(f"  Out of stock: {fi.get('sku')} — {fi.get('reason')}")

    else:
        print(f"{C.YELLOW}  Unknown topic: {topic}{C.RESET}")
        return

    print(f"\n{SC}Sending {notification_type} notification...{C.RESET}")

    notification = send_notification(notification_type, data)

    result_event = publish_notification_sent(
        order_id, saga_id, data, notification
    )

    print(f"\n{C.GREEN}{C.BOLD}  NOTIFICATION SENT{C.RESET}")
    print(f"  notification_id: {notification['notification_id']}")
    print(f"  channel:         {notification['channel']}")
    print(f"  status:          {notification['status']}")
    print(f"  [PUBLISHED] NOTIFICATION_SENT → {config.NOTIFICATIONS_SENT_TOPIC}")
    print(f"\n{C.GREEN}{C.BOLD}SAGA COMPLETE for {order_id}{C.RESET}")
    print(f"  Full flow: orders.placed → [payment] → [inventory] → notifications.sent")

def main():
    shutdown = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown
        shutdown = True
        print(f"\n{C.YELLOW}notification-service shutting down...{C.RESET}")

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Subscribe to ALL three terminal topics
    # This is how notification-service handles ALL saga outcomes
    # without knowing about any upstream service
    consumer.subscribe([
        config.INVENTORY_RESERVED_TOPIC,  # success path
        config.PAYMENTS_FAILED_TOPIC,     # payment failure path
        config.INVENTORY_FAILED_TOPIC,    # inventory failure path
    ])

    print(f"\n{SC}{C.BOLD}notification-service starting...{C.RESET}")
    print(f"Cluster:        {config.BOOTSTRAP_SERVERS}")
    print(f"Consumer group: {config.NOTIFICATION_SERVICE_GROUP}")
    print(f"\nSubscribed to THREE topics (handles ALL saga outcomes):")
    print(f"  {C.GREEN}{config.INVENTORY_RESERVED_TOPIC}{C.RESET} → ORDER_CONFIRMED notification")
    print(f"  {C.RED}{config.PAYMENTS_FAILED_TOPIC}{C.RESET}     → PAYMENT_FAILED notification")
    print(f"  {C.RED}{config.INVENTORY_FAILED_TOPIC}{C.RESET}    → INVENTORY_UNAVAILABLE notification")
    print(f"\nProducing to: {config.NOTIFICATIONS_SENT_TOPIC}")
    print(f"\n{C.YELLOW}NOTE: Kill this service (Ctrl+C) after Order 4 is processed")
    print(f"to observe lag accumulation. Restart to see catch-up.{C.RESET}")
    print(f"\n{SC}Waiting for saga outcomes...{C.RESET}")

    messages_processed = 0

    try:
        while not shutdown:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"{C.RED}Consumer error: {msg.error()}{C.RESET}")
                continue

            process_message(msg)
            consumer.commit(asynchronous=False)
            messages_processed += 1

    except Exception as e:
        print(f"{C.RED}notification-service error: {e}{C.RESET}")
        raise
    finally:
        consumer.close()
        print(f"\n{C.YELLOW}notification-service stopped. "
              f"Processed {messages_processed} events.{C.RESET}")

if __name__ == '__main__':
    main()
