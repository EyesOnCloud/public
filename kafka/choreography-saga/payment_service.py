"""
payment-service Saga Participant Step 1

This service is the first downstream participant in the saga.
It reacts to ORDER_PLACED events and processes payment.

What payment-service knows:
  INPUT:  orders.placed topic
  OUTPUT: payments.processed topic (success)
          payments.failed topic (failure)

What payment-service does NOT know:
  - How the order was created (order-service)
  - What happens after payment (inventory-service)
  - How the customer is notified (notification-service)
  - Whether inventory-service even exists

Payment simulation rules (controlled via config.py):
  Card last4 in DECLINED_CARD_SUFFIXES -> PAYMENT_FAILED
  Amount > HIGH_VALUE_THRESHOLD -> PAYMENT_FAILED (simplified)
  All other cards -> PAYMENT_PROCESSED
"""

import json
import uuid
import time
import signal
import sys
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer, KafkaError
import config

C = config.Colors
SC = config.SERVICE_COLORS['payment-service']

# Producer and Consumer setup ───────────────────────────────
producer = Producer({
    'bootstrap.servers': config.BOOTSTRAP_SERVERS,
    'enable.idempotence': 'true',
    'acks': 'all',
    'retries': '2147483647',
    'max.in.flight.requests.per.connection': '5',
    'compression.type': 'lz4',
    'linger.ms': '5',
    'client.id': 'payment-service-producer',
})

consumer = Consumer({
    'bootstrap.servers':    config.BOOTSTRAP_SERVERS,
    'group.id':             config.PAYMENT_SERVICE_GROUP,
    'auto.offset.reset':    'earliest',
    'enable.auto.commit':   'false',
    'max.poll.interval.ms': '30000',
    'session.timeout.ms':   '20000',
    'heartbeat.interval.ms':'6000',
    'client.id':            'payment-service-consumer',
})

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def delivery_callback(err, msg):
    if err:
        print(f"{C.RED}  [DELIVERY FAILED] {err}{C.RESET}")

def simulate_payment(order_data):
    """
    Simulate payment processing.
    In production: call payment gateway API (Stripe, Adyen, etc.)
    Here: rule-based simulation for predictable lab behavior.

    Returns: (success: bool, result: dict)
    """
    card_last4   = order_data.get('payment', {}).get('card_last4', '0000')
    total_amount = float(order_data.get('total_amount', 0))

    # Simulate processing delay (payment gateway latency)
    time.sleep(0.5)

    # Rule 1: Declined cards
    if card_last4 in config.DECLINED_CARD_SUFFIXES:
        return False, {
            'failure_reason': 'CARD_DECLINED',
            'failure_code':   'INSUFFICIENT_FUNDS',
            'gateway_message': f'Card ending {card_last4} was declined by issuing bank',
            'decline_code':   'do_not_honor',
        }

    # Rule 2: High value orders above threshold
    if total_amount > config.HIGH_VALUE_THRESHOLD:
        return False, {
            'failure_reason': 'HIGH_VALUE_REVIEW',
            'failure_code':   'AMOUNT_EXCEEDS_LIMIT',
            'gateway_message': f'Transaction amount ${total_amount:.2f} exceeds single-transaction limit',
            'decline_code':   'transaction_not_allowed',
        }

    # Rule 3: Payment succeeds
    transaction_ref = f'TXN-{uuid.uuid4().hex[:12].upper()}'
    return True, {
        'transaction_ref':  transaction_ref,
        'gateway':          'STRIPE',
        'gateway_charge_id': f'ch_{uuid.uuid4().hex[:24]}',
        'amount_charged':   total_amount,
        'currency':         order_data.get('currency', 'USD'),
        'card_last4':       card_last4,
        'authorization_code': uuid.uuid4().hex[:6].upper(),
    }

def publish_payment_result(order_id, saga_id, success, order_data, payment_result):
    """Publish payment outcome to appropriate topic."""
    if success:
        topic      = config.PAYMENTS_PROCESSED_TOPIC
        event_type = 'PAYMENT_PROCESSED'
    else:
        topic      = config.PAYMENTS_FAILED_TOPIC
        event_type = 'PAYMENT_FAILED'

    event = {
        'event_id':    str(uuid.uuid4()),
        'event_type':  event_type,
        'order_id':    order_id,
        'saga_id':     saga_id,
        'event_time':  now_iso(),
        'data': {
            'order_id':       order_id,
            'customer_id':    order_data.get('customer_id'),
            'customer_email': order_data.get('customer_email'),
            'customer_name':  order_data.get('customer_name'),
            'total_amount':   order_data.get('total_amount'),
            'currency':       order_data.get('currency', 'USD'),
            'items':          order_data.get('items', []),
            'shipping_address': order_data.get('shipping_address', {}),
            'payment':        payment_result,
        },
    }

    producer.produce(
        topic=topic,
        key=order_id.encode('utf-8'),
        value=json.dumps(event).encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()
    return event

def process_order_placed(msg):
    """Handle one ORDER_PLACED event."""
    try:
        event     = json.loads(msg.value().decode('utf-8'))
        order_id  = event.get('order_id')
        saga_id   = event.get('saga_id', order_id)
        order_data = event.get('data', {})
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"{C.RED}  [PARSE ERROR] {e}{C.RESET}")
        return

    card_last4 = order_data.get('payment', {}).get('card_last4', '????')
    amount     = order_data.get('total_amount', 0)

    print(f"\n{SC}{C.BOLD}{'─'*60}{C.RESET}")
    print(f"{SC}{C.BOLD}[RECEIVED] ORDER_PLACED{C.RESET}")
    print(f"  order_id:  {order_id}")
    print(f"  saga_id:   {saga_id}")
    print(f"  amount:    ${amount:.2f}")
    print(f"  card:      **** **** **** {card_last4}")
    print(f"  customer:  {order_data.get('customer_name')}")
    print(f"\n{SC}Processing payment...{C.RESET}")

    success, payment_result = simulate_payment(order_data)

    if success:
        print(f"{C.GREEN}{C.BOLD}  PAYMENT APPROVED{C.RESET}")
        print(f"  transaction_ref: {payment_result.get('transaction_ref')}")
        print(f"  gateway_charge:  {payment_result.get('gateway_charge_id')}")
        print(f"\n{SC}Publishing PAYMENT_PROCESSED to {config.PAYMENTS_PROCESSED_TOPIC}{C.RESET}")
    else:
        print(f"{C.RED}{C.BOLD}  PAYMENT DECLINED{C.RESET}")
        print(f"  reason:  {payment_result.get('failure_reason')}")
        print(f"  message: {payment_result.get('gateway_message')}")
        print(f"\n{SC}Publishing PAYMENT_FAILED to {config.PAYMENTS_FAILED_TOPIC}{C.RESET}")

    result_event = publish_payment_result(
        order_id, saga_id, success, order_data, payment_result
    )

    outcome = "payments.processed" if success else "payments.failed"
    print(f"{C.GREEN if success else C.RED}"
          f"  [PUBLISHED] event_id={result_event['event_id'][:16]}... "
          f"→ {outcome}"
          f"{C.RESET}")
    print(f"\n{C.YELLOW}payment-service role complete for {order_id}.{C.RESET}")
    print(f"{C.YELLOW}{'inventory-service will continue the saga' if success else 'notification-service will handle the failure'}.{C.RESET}")

def main():
    shutdown = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown
        shutdown = True
        print(f"\n{C.YELLOW}payment-service shutting down...{C.RESET}")

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    consumer.subscribe([config.ORDERS_PLACED_TOPIC])

    print(f"\n{SC}{C.BOLD}payment-service starting...{C.RESET}")
    print(f"Cluster:        {config.BOOTSTRAP_SERVERS}")
    print(f"Consumer group: {config.PAYMENT_SERVICE_GROUP}")
    print(f"Consuming from: {config.ORDERS_PLACED_TOPIC}")
    print(f"Producing to:   {config.PAYMENTS_PROCESSED_TOPIC}")
    print(f"             OR {config.PAYMENTS_FAILED_TOPIC}")
    print(f"\n{C.YELLOW}Payment rules:")
    print(f"  Cards {config.DECLINED_CARD_SUFFIXES} → DECLINED")
    print(f"  Amount > ${config.HIGH_VALUE_THRESHOLD:.0f} → DECLINED")
    print(f"  All other → APPROVED{C.RESET}")
    print(f"\n{SC}Waiting for orders...{C.RESET}")

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

            process_order_placed(msg)
            consumer.commit(asynchronous=False)
            messages_processed += 1

    except Exception as e:
        print(f"{C.RED}payment-service error: {e}{C.RESET}")
        raise
    finally:
        consumer.close()
        print(f"\n{C.YELLOW}payment-service stopped. "
              f"Processed {messages_processed} orders.{C.RESET}")

if __name__ == '__main__':
    main()
