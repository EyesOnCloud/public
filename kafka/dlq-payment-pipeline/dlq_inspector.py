"""
dlq-inspector Dead Letter Queue Audit Viewer

READ-ONLY consumer of payments.dlq.
Does NOT produce anything. Does NOT process messages.
Purpose: Give operators visibility into what is in the DLQ,
why messages failed, and what action is needed.

In production, this is the tool an on-call engineer opens
when a DLQ lag alert fires. They read the failure headers,
understand the root cause, and decide:
  - Fix the producer and replay (Order 4, Order 6)
  - Escalate to compliance team (Order 8 policy violation)
  - Discard and file bug report (Order 2 schema error)

Consumer group: dlq-inspector-v1
  Separate from payment-service group.
  Reading DLQ does NOT affect payment-service's offset.

"""

import json
import signal
import sys
from confluent_kafka import Consumer, KafkaError
import config

C  = config.Colors
SC = config.SERVICE_COLORS['dlq-inspector']

consumer = Consumer({
    'bootstrap.servers':    config.BOOTSTRAP_SERVERS,
    'group.id':             config.DLQ_INSPECTOR_GROUP,
    'auto.offset.reset':    'earliest',
    'enable.auto.commit':   'true',
    'auto.commit.interval.ms': '5000',
    'client.id':            'dlq-inspector-consumer',
})

def parse_headers(headers):
    """Convert Kafka headers list to readable dict."""
    if not headers:
        return {}
    result = {}
    for key, value in headers:
        try:
            result[key] = value.decode('utf-8') if value else ''
        except Exception:
            result[key] = str(value)
    return result

def categorize_dlq_message(error_type, error_reason):
    """
    Determine recommended action for each DLQ message type.
    This mirrors what a real runbook would say.
    """
    recommendations = {
        'MISSING_REQUIRED_FIELD': (
            'SCHEMA ERROR',
            'Bug in producer. Contact order-service team. '
            'Message cannot be replayed without schema fix on producer side.',
            C.RED
        ),
        'INVALID_CARD_FORMAT': (
            'DATA ERROR — FIXABLE',
            'Card number format wrong. If correct card digits known, '
            'fix and replay via dlq-processor. If unknown, notify customer.',
            C.YELLOW
        ),
        'NEGATIVE_AMOUNT': (
            'DATA ERROR — FIXABLE',
            'Negative amount produced by order-service bug. '
            'Fix amount to correct positive value and replay.',
            C.YELLOW
        ),
        'ZERO_AMOUNT': (
            'DATA ERROR',
            'Zero-value order. Investigate whether this is a legitimate '
            'free item or a producer calculation error.',
            C.YELLOW
        ),
        'EXCEEDS_DAILY_LIMIT': (
            'POLICY VIOLATION',
            'Amount exceeds $10,000 daily limit. Requires manual '
            'authorization by finance team. Do NOT replay without approval.',
            C.MAGENTA
        ),
        'SCHEMA_VALIDATION_FAILED': (
            'SCHEMA ERROR',
            'Message structure does not match expected schema. '
            'Root cause in producer. Requires schema fix before replay.',
            C.RED
        ),
        'PAYMENT_GATEWAY_TIMEOUT': (
            'INFRASTRUCTURE ERROR',
            'Transient gateway timeout. Safe to replay. '
            'Check gateway status before replaying.',
            C.BLUE
        ),
    }
    return recommendations.get(error_reason, (
        'UNKNOWN ERROR',
        f'No runbook entry for {error_reason}. Investigate manually.',
        C.WHITE
    ))

def print_dlq_message(msg, count):
    headers = parse_headers(msg.headers())

    error_type   = headers.get('dlq-error-type',   'UNKNOWN')
    error_reason = headers.get('dlq-error-reason',  'UNKNOWN')
    error_detail = headers.get('dlq-error-detail',  'No detail provided')
    orig_topic   = headers.get('dlq-original-topic','UNKNOWN')
    failed_at    = headers.get('dlq-failed-at',     'UNKNOWN')
    retry_count  = headers.get('dlq-retry-count',   '0')
    order_id     = headers.get('dlq-order-id', msg.key().decode() if msg.key() else 'UNKNOWN')
    orig_partition = headers.get('dlq-partition',   'UNKNOWN')
    orig_offset    = headers.get('dlq-offset',      'UNKNOWN')

    action_label, action_text, action_color = categorize_dlq_message(
        error_type, error_reason
    )

    type_color = C.RED if error_type == 'DATA' else C.BLUE

    print(f"\n{SC}{C.BOLD}{'═'*65}{C.RESET}")
    print(f"{SC}{C.BOLD}  DLQ MESSAGE #{count:03d}{C.RESET}")
    print(f"{SC}{'─'*65}{C.RESET}")

    print(f"\n  {C.BOLD}KAFKA METADATA:{C.RESET}")
    print(f"  DLQ partition:     {msg.partition()}")
    print(f"  DLQ offset:        {msg.offset()}")
    print(f"  DLQ key:           {order_id}")
    print(f"  Original topic:    {orig_topic}")
    print(f"  Original partition:{orig_partition}")
    print(f"  Original offset:   {orig_offset}")

    print(f"\n  {C.BOLD}FAILURE INFORMATION:{C.RESET}")
    print(f"  Error type:   {type_color}{error_type}{C.RESET}")
    print(f"  Error reason: {type_color}{error_reason}{C.RESET}")
    print(f"  Failed at:    {failed_at}")
    print(f"  Retry count:  {retry_count}")
    print(f"  Detail:       {error_detail}")

    print(f"\n  {C.BOLD}RECOMMENDED ACTION:{C.RESET}")
    print(f"  {action_color}{action_label}{C.RESET}")
    print(f"  {action_text}")

    # Parse and show original payload
    try:
        original = json.loads(msg.value().decode('utf-8'))
        order_data = original.get('data', original)
        print(f"\n  {C.BOLD}ORIGINAL PAYLOAD SUMMARY:{C.RESET}")
        print(f"  order_id:     {order_data.get('order_id', 'N/A')}")
        print(f"  customer_id:  {order_data.get('customer_id', C.RED + 'MISSING' + C.RESET)}")
        print(f"  amount:       ${order_data.get('total_amount', 'N/A')}")
        print(f"  card_last4:   {order_data.get('payment', {}).get('card_last4', 'N/A')}")
        print(f"  customer:     {order_data.get('customer_name', 'N/A')}")
    except Exception as e:
        print(f"\n  {C.RED}Could not parse original payload: {e}{C.RESET}")

    # Replay eligibility assessment
    fixable = error_reason in {'INVALID_CARD_FORMAT', 'NEGATIVE_AMOUNT',
                                'PAYMENT_GATEWAY_TIMEOUT', 'ZERO_AMOUNT'}
    needs_approval = error_reason in {'EXCEEDS_DAILY_LIMIT'}
    not_replayable = error_reason in {'MISSING_REQUIRED_FIELD', 'SCHEMA_VALIDATION_FAILED'}

    print(f"\n  {C.BOLD}REPLAY ELIGIBILITY:{C.RESET}")
    if fixable:
        print(f"  {C.GREEN}FIXABLE → Can be replayed via dlq-processor after correction{C.RESET}")
    elif needs_approval:
        print(f"  {C.MAGENTA}NEEDS APPROVAL → Escalate to finance/compliance before replay{C.RESET}")
    elif not_replayable:
        print(f"  {C.RED}NOT REPLAYABLE → Producer bug must be fixed first. "
              f"Cannot fix this message in dlq-processor.{C.RESET}")

def main():
    shutdown = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, handle_shutdown)

    consumer.subscribe([config.PAYMENTS_DLQ_TOPIC])

    print(f"\n{SC}{C.BOLD}dlq-inspector starting...{C.RESET}")
    print(f"Cluster:        {config.BOOTSTRAP_SERVERS}")
    print(f"Consumer group: {config.DLQ_INSPECTOR_GROUP}")
    print(f"Consuming from: {config.PAYMENTS_DLQ_TOPIC} (READ ONLY)")
    print(f"\n{C.YELLOW}This service NEVER produces anything.")
    print(f"It provides audit visibility into DLQ contents.")
    print(f"Replaying messages is done by dlq-processor (Terminal D).{C.RESET}")
    print(f"\n{SC}Waiting for DLQ messages...{C.RESET}")

    count = 0

    try:
        while not shutdown:
            msg = consumer.poll(timeout=2.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"{C.RED}Error: {msg.error()}{C.RESET}")
                continue

            count += 1
            print_dlq_message(msg, count)

    finally:
        consumer.close()
        print(f"\n{C.YELLOW}dlq-inspector stopped. Inspected {count} DLQ messages.{C.RESET}")

if __name__ == '__main__':
    main()
