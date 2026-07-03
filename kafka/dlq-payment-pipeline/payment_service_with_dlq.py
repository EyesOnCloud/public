"""
payment-service-with-dlq Payment Processor with Dead Letter Queue

Consumes from TWO topics:
  1. orders.placed       — live order traffic
  2. payments.dlq.replayed — replayed/fixed messages from DLQ

Produces to THREE topics:
  payments.processed  — successfully processed payments
  payments.failed     — payment declined by gateway (valid message, declined card)
  payments.dlq        — poison messages that cannot be processed

DLQ routing logic:
  DATA failures       → payments.dlq immediately (no retry)
  INFRASTRUCTURE fail → retry up to MAX_RETRIES, then payments.dlq
  PAYMENT declined    → payments.failed (not DLQ — these are valid messages)

Every message routed to DLQ carries headers:
  dlq-error-type      — DATA or INFRASTRUCTURE
  dlq-error-reason    — specific failure code
  dlq-error-detail    — human-readable description
  dlq-original-topic  — where the message came from
  dlq-failed-at       — timestamp of failure
  dlq-retry-count     — how many times it was retried
  dlq-service         — which service sent it to DLQ
  dlq-order-id        — for easy filtering in DLQ inspector
"""

import json
import uuid
import time
import re
import signal
import sys
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer, KafkaError
import config

C  = config.Colors
SC = config.SERVICE_COLORS['payment-service-dlq']

# ── Producer ──────────────────────────────────────────────────
producer = Producer({
    'bootstrap.servers': config.BOOTSTRAP_SERVERS,
    'enable.idempotence': 'true',
    'acks': 'all',
    'retries': '2147483647',
    'max.in.flight.requests.per.connection': '5',
    'compression.type': 'lz4',
    'linger.ms': '5',
    'client.id': 'payment-service-dlq-producer',
})

# ── Consumer ──────────────────────────────────────────────────
consumer = Consumer({
    'bootstrap.servers':    config.BOOTSTRAP_SERVERS,
    'group.id':             config.PAYMENT_SERVICE_GROUP,
    'auto.offset.reset':    'earliest',
    'enable.auto.commit':   'false',
    'max.poll.interval.ms': '60000',
    'session.timeout.ms':   '30000',
    'heartbeat.interval.ms':'10000',
    'client.id':            'payment-service-dlq-consumer',
})

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def delivery_callback(err, msg):
    if err:
        print(f"{C.RED}  [DELIVERY FAILED] {err}{C.RESET}")

# ═══════════════════════════════════════════════════════════════
# VALIDATION LAYER
# Every incoming message goes through validation before
# any business logic runs. Validation failures are DATA failures
# route to DLQ immediately, zero retries.
# ═══════════════════════════════════════════════════════════════

class ValidationError(Exception):
    """Raised when message fails data validation. Routes to DLQ, no retry."""
    def __init__(self, error_reason, detail):
        self.error_reason = error_reason
        self.detail       = detail
        super().__init__(detail)

class BusinessRuleError(Exception):
    """Raised when message violates a business rule. Routes to DLQ, no retry."""
    def __init__(self, error_reason, detail):
        self.error_reason = error_reason
        self.detail       = detail
        super().__init__(detail)

class InfrastructureError(Exception):
    """Raised for transient failures. Retried before DLQ."""
    def __init__(self, error_reason, detail):
        self.error_reason = error_reason
        self.detail       = detail
        super().__init__(detail)

def validate_order_schema(order_data):
    """
    Schema validation: verify all required fields are present
    and have correct types.

    This is the first defense against poison messages.
    Missing fields or wrong types are DATA failures — they will
    never succeed on retry because the data is permanently missing.
    """
    # Check required top-level fields
    for field in config.REQUIRED_ORDER_FIELDS:
        if field not in order_data:
            raise ValidationError(
                'MISSING_REQUIRED_FIELD',
                f"Required field '{field}' is missing from order payload. "
                f"Present fields: {list(order_data.keys())}"
            )

    # Check required payment fields
    payment = order_data.get('payment', {})
    for field in config.REQUIRED_PAYMENT_FIELDS:
        if field not in payment:
            raise ValidationError(
                'MISSING_REQUIRED_FIELD',
                f"Required field 'payment.{field}' is missing. "
                f"Present payment fields: {list(payment.keys())}"
            )

    # Validate total_amount type
    try:
        amount = float(order_data['total_amount'])
    except (TypeError, ValueError):
        raise ValidationError(
            'SCHEMA_VALIDATION_FAILED',
            f"Field 'total_amount' must be numeric. "
            f"Got: {type(order_data['total_amount']).__name__} = {order_data['total_amount']}"
        )

    # Validate card format: exactly 4 digits
    card_last4 = str(payment.get('card_last4', ''))
    if not re.match(config.VALID_CARD_LAST4_PATTERN, card_last4):
        raise ValidationError(
            'INVALID_CARD_FORMAT',
            f"Field 'payment.card_last4' must be exactly 4 digits. "
            f"Got: '{card_last4}' (length={len(card_last4)}). "
            f"Valid example: '4242'"
        )

    # Validate currency
    valid_currencies = {'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'}
    currency = order_data.get('currency', '')
    if currency not in valid_currencies:
        raise ValidationError(
            'INVALID_CURRENCY',
            f"Currency '{currency}' is not supported. "
            f"Supported: {valid_currencies}"
        )

    # Validate items list
    items = order_data.get('items', [])
    if not items or not isinstance(items, list):
        raise ValidationError(
            'SCHEMA_VALIDATION_FAILED',
            f"Field 'items' must be a non-empty list. Got: {type(items).__name__}"
        )

def validate_business_rules(order_data):
    """
    Business rule validation: even if schema is valid,
    business rules may reject the order.

    These are also DATA failures — the message will never
    be processable as-is. Route to DLQ immediately.
    """
    amount = float(order_data['total_amount'])

    # Rule 1: No negative amounts
    if amount < 0:
        raise BusinessRuleError(
            'NEGATIVE_AMOUNT',
            f"Order amount ${amount:.2f} is negative. "
            f"Negative amounts are not valid payment requests. "
            f"order_id={order_data.get('order_id')}"
        )

    # Rule 2: No zero amounts
    if amount == 0:
        raise BusinessRuleError(
            'ZERO_AMOUNT',
            f"Order amount is $0.00. "
            f"Zero-value orders must not reach the payment processor. "
            f"order_id={order_data.get('order_id')}"
        )

    # Rule 3: Daily transaction limit
    if amount > config.DAILY_LIMIT:
        raise BusinessRuleError(
            'EXCEEDS_DAILY_LIMIT',
            f"Order amount ${amount:.2f} exceeds single-transaction limit "
            f"of ${config.DAILY_LIMIT:.2f}. "
            f"Requires manual authorization. "
            f"order_id={order_data.get('order_id')}"
        )

# ═══════════════════════════════════════════════════════════════
# DLQ ROUTING
# ═══════════════════════════════════════════════════════════════

def route_to_dlq(original_msg, order_id, error_type, error_reason,
                 error_detail, retry_count, original_topic):
    """
    Route a poison message to payments.dlq.

    The original message bytes are preserved exactly — no modification.
    Failure context is added as Kafka message headers, not in the value.
    This means the DLQ consumer can read the original payload without
    parsing failure metadata mixed into the business data.

    Headers provide:
      - Why it failed (error_type, error_reason, error_detail)
      - When it failed (dlq-failed-at)
      - Where it came from (original_topic, dlq-service)
      - How many times it was retried (retry_count)
      - Business key for filtering (order_id)
    """
    failed_at = now_iso()

    headers = [
        ('dlq-error-type',     error_type.encode('utf-8')),
        ('dlq-error-reason',   error_reason.encode('utf-8')),
        ('dlq-error-detail',   error_detail.encode('utf-8')),
        ('dlq-original-topic', original_topic.encode('utf-8')),
        ('dlq-failed-at',      failed_at.encode('utf-8')),
        ('dlq-retry-count',    str(retry_count).encode('utf-8')),
        ('dlq-service',        'payment-service-dlq-v1'.encode('utf-8')),
        ('dlq-order-id',       order_id.encode('utf-8')),
        ('dlq-partition',      str(original_msg.partition()).encode('utf-8')),
        ('dlq-offset',         str(original_msg.offset()).encode('utf-8')),
    ]

    producer.produce(
        topic=config.PAYMENTS_DLQ_TOPIC,
        key=order_id.encode('utf-8'),
        value=original_msg.value(),  # Original bytes preserved
        headers=headers,
        callback=delivery_callback,
    )
    producer.flush()

def route_to_processed(order_id, saga_id, order_data, payment_result):
    """Route successfully processed payment to payments.processed."""
    event = {
        'event_id':   str(uuid.uuid4()),
        'event_type': 'PAYMENT_PROCESSED',
        'order_id':   order_id,
        'saga_id':    saga_id,
        'event_time': now_iso(),
        'data': {
            **order_data,
            'payment_result': payment_result,
        },
    }
    producer.produce(
        topic=config.PAYMENTS_PROCESSED_TOPIC,
        key=order_id.encode('utf-8'),
        value=json.dumps(event).encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()

def route_to_failed(order_id, saga_id, order_data, decline_reason):
    """Route declined payment to payments.failed (not DLQ — valid message, card declined)."""
    event = {
        'event_id':   str(uuid.uuid4()),
        'event_type': 'PAYMENT_FAILED',
        'order_id':   order_id,
        'saga_id':    saga_id,
        'event_time': now_iso(),
        'data': {
            **order_data,
            'payment_failure': decline_reason,
        },
    }
    producer.produce(
        topic=config.PAYMENTS_FAILED_TOPIC,
        key=order_id.encode('utf-8'),
        value=json.dumps(event).encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()

# ═══════════════════════════════════════════════════════════════
# PAYMENT PROCESSING
# ═══════════════════════════════════════════════════════════════

DECLINED_CARDS = {'0002', '9999', '1111'}

def simulate_payment_gateway(order_data):
    """
    Simulate payment gateway call.
    Returns (success, result_dict).

    IMPORTANT: A declined card is NOT a poison message.
    It is a valid business outcome for a valid message.
    Declined payments route to payments.failed, not DLQ.
    """
    time.sleep(0.3)  # Gateway latency
    card_last4 = order_data['payment']['card_last4']
    amount     = float(order_data['total_amount'])

    if card_last4 in DECLINED_CARDS:
        return False, {
            'decline_reason': 'CARD_DECLINED',
            'gateway_code':   'do_not_honor',
            'gateway_msg':    f'Card ending {card_last4} declined by issuer',
        }

    return True, {
        'transaction_ref':   f'TXN-{uuid.uuid4().hex[:12].upper()}',
        'gateway':           'STRIPE',
        'gateway_charge_id': f'ch_{uuid.uuid4().hex[:24]}',
        'amount_charged':    amount,
        'currency':          order_data.get('currency', 'USD'),
        'card_last4':        card_last4,
        'auth_code':         uuid.uuid4().hex[:6].upper(),
    }

# ═══════════════════════════════════════════════════════════════
# MESSAGE PROCESSING PIPELINE
# ═══════════════════════════════════════════════════════════════

def process_message(msg, source_topic):
    """
    Full processing pipeline for one message.

    Stages:
      1. Parse JSON (infrastructure error if fails)
      2. Schema validation (data error if fails → DLQ)
      3. Business rule validation (data error if fails → DLQ)
      4. Payment gateway call (infrastructure error if fails → retry)
      5. Route to payments.processed or payments.failed
    """
    order_id = msg.key().decode('utf-8') if msg.key() else 'UNKNOWN'
    raw_value = msg.value()

    print(f"\n{SC}{C.BOLD}{'─'*60}{C.RESET}")
    print(f"{SC}{C.BOLD}[RECEIVED] from {source_topic}{C.RESET}")
    print(f"  key:       {order_id}")
    print(f"  partition: {msg.partition()}")
    print(f"  offset:    {msg.offset()}")
    print(f"  bytes:     {len(raw_value)}")

    # ── Stage 1: JSON parse ───────────────────────────────────
    try:
        envelope   = json.loads(raw_value.decode('utf-8'))
        order_data = envelope.get('data', {})
        saga_id    = envelope.get('saga_id', order_id)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"{C.RED}  [STAGE 1 FAIL] JSON parse error: {e}{C.RESET}")
        print(f"{C.RED}  → Routing to DLQ (unparseable message){C.RESET}")
        route_to_dlq(
            msg, order_id,
            error_type='DATA',
            error_reason='SCHEMA_VALIDATION_FAILED',
            error_detail=f'JSON parse failed: {str(e)}',
            retry_count=0,
            original_topic=source_topic,
        )
        return 'DLQ', 'JSON_PARSE_ERROR'

    amount    = order_data.get('total_amount', 'N/A')
    card_last4 = order_data.get('payment', {}).get('card_last4', '????')

    print(f"  order_id:  {order_data.get('order_id', order_id)}")
    print(f"  customer:  {order_data.get('customer_name', 'N/A')} "
          f"({order_data.get('customer_email', 'N/A')})")
    print(f"  amount:    ${amount}")
    print(f"  card:      **** **** **** {card_last4}")

    # ── Stage 2: Schema validation ────────────────────────────
    print(f"\n{SC}  Stage 2: Schema validation...{C.RESET}")
    try:
        validate_order_schema(order_data)
        print(f"{C.GREEN}  Schema: PASS{C.RESET}")
    except ValidationError as e:
        print(f"{C.RED}  [STAGE 2 FAIL] {e.error_reason}: {e.detail[:80]}{C.RESET}")
        print(f"{C.RED}  → DATA FAILURE: routing to DLQ immediately (no retry){C.RESET}")
        route_to_dlq(
            msg, order_id,
            error_type='DATA',
            error_reason=e.error_reason,
            error_detail=e.detail,
            retry_count=0,
            original_topic=source_topic,
        )
        print(f"{C.YELLOW}  Partition continues — next message unblocked.{C.RESET}")
        return 'DLQ', e.error_reason

    # ── Stage 3: Business rule validation ─────────────────────
    print(f"{SC}  Stage 3: Business rule validation...{C.RESET}")
    try:
        validate_business_rules(order_data)
        print(f"{C.GREEN}  Business rules: PASS{C.RESET}")
    except BusinessRuleError as e:
        print(f"{C.RED}  [STAGE 3 FAIL] {e.error_reason}: {e.detail[:80]}{C.RESET}")
        print(f"{C.RED}  → DATA FAILURE: routing to DLQ immediately (no retry){C.RESET}")
        route_to_dlq(
            msg, order_id,
            error_type='DATA',
            error_reason=e.error_reason,
            error_detail=e.detail,
            retry_count=0,
            original_topic=source_topic,
        )
        print(f"{C.YELLOW}  Partition continues — next message unblocked.{C.RESET}")
        return 'DLQ', e.error_reason

    # ── Stage 4: Payment gateway ───────────────────────────────
    print(f"{SC}  Stage 4: Payment gateway call...{C.RESET}")
    retry_count = 0
    while retry_count <= config.MAX_INFRASTRUCTURE_RETRIES:
        try:
            success, gateway_result = simulate_payment_gateway(order_data)
            break
        except InfrastructureError as e:
            retry_count += 1
            if retry_count > config.MAX_INFRASTRUCTURE_RETRIES:
                print(f"{C.RED}  [STAGE 4 FAIL] Max retries ({config.MAX_INFRASTRUCTURE_RETRIES}) "
                      f"exceeded: {e.detail}{C.RESET}")
                print(f"{C.RED}  → INFRASTRUCTURE FAILURE: routing to DLQ after {retry_count} retries{C.RESET}")
                route_to_dlq(
                    msg, order_id,
                    error_type='INFRASTRUCTURE',
                    error_reason=e.error_reason,
                    error_detail=e.detail,
                    retry_count=retry_count,
                    original_topic=source_topic,
                )
                return 'DLQ', e.error_reason
            print(f"{C.YELLOW}  Gateway timeout (attempt {retry_count}). "
                  f"Retrying in 1s...{C.RESET}")
            time.sleep(1.0)

    # ── Stage 5: Route outcome ────────────────────────────────
    if success:
        print(f"{C.GREEN}{C.BOLD}  PAYMENT APPROVED{C.RESET}")
        print(f"  transaction_ref: {gateway_result.get('transaction_ref')}")
        route_to_processed(order_id, saga_id, order_data, gateway_result)
        print(f"{C.GREEN}  → Published to {config.PAYMENTS_PROCESSED_TOPIC}{C.RESET}")
        return 'PROCESSED', 'SUCCESS'
    else:
        print(f"{C.RED}{C.BOLD}  PAYMENT DECLINED{C.RESET}")
        print(f"  reason: {gateway_result.get('decline_reason')}")
        print(f"  {C.YELLOW}Note: DECLINED is not a poison message.{C.RESET}")
        print(f"  {C.YELLOW}Valid message + declined card → payments.failed (not DLQ){C.RESET}")
        route_to_failed(order_id, saga_id, order_data, gateway_result)
        print(f"{C.RED}  → Published to {config.PAYMENTS_FAILED_TOPIC}{C.RESET}")
        return 'FAILED', 'CARD_DECLINED'

# ═══════════════════════════════════════════════════════════════
# MAIN CONSUMER LOOP
# ═══════════════════════════════════════════════════════════════

def main():
    shutdown = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown
        shutdown = True
        print(f"\n{C.YELLOW}payment-service-with-dlq shutting down...{C.RESET}")

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Subscribe to BOTH live traffic and replayed DLQ messages
    consumer.subscribe([
        config.ORDERS_PLACED_TOPIC,
        config.PAYMENTS_REPLAYED_TOPIC,
    ])

    print(f"\n{SC}{C.BOLD}payment-service-with-dlq starting...{C.RESET}")
    print(f"Cluster:        {config.BOOTSTRAP_SERVERS}")
    print(f"Consumer group: {config.PAYMENT_SERVICE_GROUP}")
    print(f"\nConsuming from:")
    print(f"  {config.ORDERS_PLACED_TOPIC}       (live traffic)")
    print(f"  {config.PAYMENTS_REPLAYED_TOPIC}  (DLQ replay)")
    print(f"\nProducing to:")
    print(f"  {config.PAYMENTS_PROCESSED_TOPIC} (success)")
    print(f"  {config.PAYMENTS_FAILED_TOPIC}    (card declined — not DLQ)")
    print(f"  {config.PAYMENTS_DLQ_TOPIC}       (poison messages)")
    print(f"\n{C.YELLOW}DLQ routing:")
    print(f"  DATA failures        → DLQ immediately (no retry)")
    print(f"  INFRASTRUCTURE fail  → retry {config.MAX_INFRASTRUCTURE_RETRIES}x, then DLQ")
    print(f"  CARD DECLINED        → payments.failed (not DLQ){C.RESET}")
    print(f"\n{SC}Waiting for orders...{C.RESET}")

    stats = {'processed': 0, 'failed': 0, 'dlq': 0, 'total': 0}

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

            source_topic = msg.topic()
            outcome, reason = process_message(msg, source_topic)

            stats['total'] += 1
            if outcome == 'PROCESSED':
                stats['processed'] += 1
            elif outcome == 'FAILED':
                stats['failed'] += 1
            elif outcome == 'DLQ':
                stats['dlq'] += 1

            consumer.commit(asynchronous=False)

            print(f"\n{SC}Stats: "
                  f"total={stats['total']} | "
                  f"processed={stats['processed']} | "
                  f"declined={stats['failed']} | "
                  f"dlq={stats['dlq']}"
                  f"{C.RESET}")

    except Exception as e:
        print(f"{C.RED}payment-service-with-dlq error: {e}{C.RESET}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        consumer.close()
        print(f"\n{C.YELLOW}payment-service-with-dlq stopped.{C.RESET}")
        print(f"Final stats: {stats}")

if __name__ == '__main__':
    main()
