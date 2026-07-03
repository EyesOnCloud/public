"""
dlq-processor Operator-Controlled DLQ Replay Tool

This service allows operators to:
  1. List messages currently in the DLQ
  2. Select specific messages to replay (after fixing them)
  3. Apply corrections to fixable messages
  4. Publish corrected messages to payments.dlq.replayed
  5. payment-service-with-dlq picks up from payments.dlq.replayed
     and processes them through the same validation pipeline

IMPORTANT DESIGN DECISIONS:
  - Operator explicitly selects WHICH messages to replay
    (not automatic batch replay of everything in DLQ)
  - Each replay applies a specific correction
  - The corrected message goes to payments.dlq.replayed,
    NOT back to orders.placed (maintains audit trail separation)
  - Messages 2 (missing customer_id) and 8 (exceeds limit)
    are intentionally NOT replayable in this lab —
    they require producer fix or management approval

Why not auto-replay everything?
  DLQ is a circuit breaker, not a retry queue.
  Auto-replaying everything defeats the purpose.
  The operator must diagnose each failure and decide:
  - Fix and replay (Orders 4 and 6)
  - Escalate (Order 8)
  - Discard with bug report (Order 2)

Consumer group: dlq-processor-v1

"""

import json
import uuid
import sys
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer, TopicPartition, KafkaError
import config

C  = config.Colors
SC = config.SERVICE_COLORS['dlq-processor']

producer = Producer({
    'bootstrap.servers': config.BOOTSTRAP_SERVERS,
    'enable.idempotence': 'true',
    'acks': 'all',
    'retries': '2147483647',
    'max.in.flight.requests.per.connection': '5',
    'client.id': 'dlq-processor-producer',
})

def delivery_callback(err, msg):
    if err:
        print(f"{C.RED}  [DELIVERY FAILED] {err}{C.RESET}")
    else:
        print(
            f"{C.GREEN}  [REPLAYED] "
            f"topic={msg.topic()} "
            f"partition={msg.partition()} "
            f"offset={msg.offset()} "
            f"key={msg.key().decode() if msg.key() else 'none'}"
            f"{C.RESET}"
        )

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def parse_headers(headers):
    if not headers:
        return {}
    return {
        k: v.decode('utf-8') if v else ''
        for k, v in headers
    }

def read_dlq_messages():
    """
    Read all current messages from payments.dlq.
    Returns list of (message, parsed_event, headers) tuples.
    Uses a fresh consumer with a temporary group to read from beginning.
    """
    print(f"\n{SC}Reading DLQ contents...{C.RESET}")

    scan_consumer = Consumer({
        'bootstrap.servers':  config.BOOTSTRAP_SERVERS,
        'group.id':           f'dlq-processor-scan-{uuid.uuid4().hex[:8]}',
        'auto.offset.reset':  'earliest',
        'enable.auto.commit': 'false',
        'client.id':          'dlq-processor-scanner',
    })

    scan_consumer.subscribe([config.PAYMENTS_DLQ_TOPIC])

    dlq_messages = []
    idle_count   = 0

    try:
        while idle_count < 3:
            msg = scan_consumer.poll(timeout=2.0)
            if msg is None:
                idle_count += 1
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    idle_count += 1
                continue

            idle_count = 0

            headers    = parse_headers(msg.headers())
            raw_value  = msg.value()

            try:
                envelope   = json.loads(raw_value.decode('utf-8'))
                order_data = envelope.get('data', envelope)
            except Exception:
                order_data = {}

            dlq_messages.append({
                'msg':        msg,
                'order_data': order_data,
                'headers':    headers,
                'order_id':   headers.get('dlq-order-id',
                              msg.key().decode() if msg.key() else 'UNKNOWN'),
                'error_reason': headers.get('dlq-error-reason', 'UNKNOWN'),
                'error_type':   headers.get('dlq-error-type', 'UNKNOWN'),
                'failed_at':    headers.get('dlq-failed-at', 'UNKNOWN'),
            })
    finally:
        scan_consumer.close()

    return dlq_messages

def print_dlq_summary(dlq_messages):
    print(f"\n{SC}{C.BOLD}{'='*65}{C.RESET}")
    print(f"{SC}{C.BOLD}  DLQ CONTENTS — {len(dlq_messages)} messages{C.RESET}")
    print(f"{SC}{C.BOLD}{'='*65}{C.RESET}")

    if not dlq_messages:
        print(f"  {C.GREEN}DLQ is empty. No failed messages.{C.RESET}")
        return

    for i, item in enumerate(dlq_messages, 1):
        order_data   = item['order_data']
        error_reason = item['error_reason']
        error_type   = item['error_type']

        # Determine if this message can be replayed
        fixable = error_reason in {
            'INVALID_CARD_FORMAT', 'NEGATIVE_AMOUNT',
            'PAYMENT_GATEWAY_TIMEOUT', 'ZERO_AMOUNT'
        }
        needs_approval = error_reason in {'EXCEEDS_DAILY_LIMIT'}

        if fixable:
            replay_status = f"{C.GREEN}FIXABLE — can replay{C.RESET}"
        elif needs_approval:
            replay_status = f"{C.MAGENTA}NEEDS APPROVAL — do not replay yet{C.RESET}"
        else:
            replay_status = f"{C.RED}NOT REPLAYABLE — fix producer first{C.RESET}"

        type_color = C.RED if error_type == 'DATA' else C.BLUE

        print(f"\n  [{i}] {C.BOLD}{item['order_id']}{C.RESET}")
        print(f"      Error:     {type_color}{error_type}{C.RESET} / {error_reason}")
        print(f"      Amount:    ${order_data.get('total_amount', 'N/A')}")
        print(f"      Card:      {order_data.get('payment', {}).get('card_last4', 'N/A')}")
        print(f"      customer_id: {order_data.get('customer_id', C.RED + 'MISSING' + C.RESET)}")
        print(f"      Failed at: {item['failed_at']}")
        print(f"      Replay:    {replay_status}")

def apply_correction_and_replay(item):
    """
    Apply operator-specified correction to a DLQ message
    and publish the corrected version to payments.dlq.replayed.
    """
    order_data   = item['order_data']
    order_id     = item['order_id']
    error_reason = item['error_reason']

    print(f"\n{SC}{C.BOLD}Applying correction for {order_id}{C.RESET}")
    print(f"Error reason: {error_reason}")

    if error_reason == 'NEGATIVE_AMOUNT':
        # Order 4: amount was -500. Correct to the actual order value.
        original_amount = order_data.get('total_amount', -500)
        print(f"\n  Original amount: ${original_amount}")
        print(f"  This was a negative amount — likely a sign error in order-service.")
        corrected_amount = abs(original_amount)
        print(f"  Corrected amount: ${corrected_amount} (absolute value)")

        corrected_data = json.loads(json.dumps(order_data))  # deep copy
        corrected_data['total_amount'] = corrected_amount
        corrected_data['items'] = [
            {**item_data, 'unit_price': abs(item_data.get('unit_price', 0))}
            for item_data in corrected_data.get('items', [])
        ]
        correction_note = f'Corrected negative amount {original_amount} to {corrected_amount}'

    elif error_reason == 'INVALID_CARD_FORMAT':
        # Order 6: card_last4 was 'ABCD'. Correct to '4242'.
        original_card = order_data.get('payment', {}).get('card_last4', 'ABCD')
        print(f"\n  Original card_last4: '{original_card}' (invalid — contains letters)")
        corrected_card = input(f"  Enter corrected card_last4 (4 digits) [press Enter for '4242']: ").strip()
        if not corrected_card:
            corrected_card = '4242'
        if not corrected_card.isdigit() or len(corrected_card) != 4:
            print(f"{C.RED}  Invalid: must be exactly 4 digits. Aborting.{C.RESET}")
            return False

        corrected_data = json.loads(json.dumps(order_data))
        corrected_data['payment']['card_last4'] = corrected_card
        correction_note = f'Corrected card_last4 from {original_card} to {corrected_card}'

    elif error_reason == 'PAYMENT_GATEWAY_TIMEOUT':
        # Infrastructure error — replay without modification
        corrected_data = order_data
        correction_note = 'Infrastructure error cleared — replaying without modification'

    else:
        print(f"{C.RED}  Cannot auto-fix error reason: {error_reason}{C.RESET}")
        print(f"{C.RED}  This message requires manual intervention or producer fix.{C.RESET}")
        return False

    # Build replayed event
    replayed_event = {
        'event_id':         str(uuid.uuid4()),
        'event_type':       'ORDER_PLACED',
        'order_id':         order_id,
        'saga_id':          order_id,
        'event_time':       now_iso(),
        'data':             corrected_data,
        'replay_metadata': {
            'replayed_at':      now_iso(),
            'original_dlq_error': error_reason,
            'correction_applied': correction_note,
            'replayed_by':       'dlq-processor-v1',
            'original_order_id': order_id,
        },
    }

    print(f"\n{SC}Publishing corrected message to {config.PAYMENTS_REPLAYED_TOPIC}...{C.RESET}")
    print(f"  Correction: {correction_note}")

    producer.produce(
        topic=config.PAYMENTS_REPLAYED_TOPIC,
        key=order_id.encode('utf-8'),
        value=json.dumps(replayed_event).encode('utf-8'),
        callback=delivery_callback,
    )
    producer.flush()
    return True

def print_menu():
    print(f"\n{SC}{C.BOLD}{'='*65}{C.RESET}")
    print(f"{SC}{C.BOLD}  DLQ PROCESSOR — Operator Replay Tool{C.RESET}")
    print(f"{SC}{C.BOLD}{'='*65}{C.RESET}")
    print(f"  1. List all DLQ messages (read current state)")
    print(f"  2. Replay Order 4 (fix negative amount)")
    print(f"  3. Replay Order 6 (fix invalid card format)")
    print(f"  4. Show why Order 2 cannot be replayed")
    print(f"  5. Show why Order 8 cannot be replayed")
    print(f"  q. Quit")
    print(f"{SC}{'─'*65}{C.RESET}")

def main():
    print(f"\n{SC}{C.BOLD}dlq-processor starting...{C.RESET}")
    print(f"Cluster:      {config.BOOTSTRAP_SERVERS}")
    print(f"Replaying to: {config.PAYMENTS_REPLAYED_TOPIC}")
    print(f"\n{C.YELLOW}This tool replays SPECIFIC messages after operator diagnosis.")
    print(f"Not all DLQ messages are replayable — some require producer fixes.")
    print(f"payment-service-with-dlq consumes {config.PAYMENTS_REPLAYED_TOPIC}{C.RESET}")

    while True:
        print_menu()
        choice = input(f"\n  Select (1-5 or q): ").strip().lower()

        if choice == 'q':
            sys.exit(0)

        elif choice == '1':
            dlq_messages = read_dlq_messages()
            print_dlq_summary(dlq_messages)

        elif choice == '2':
            # Replay Order 4 — negative amount
            dlq_messages = read_dlq_messages()
            target = next(
                (m for m in dlq_messages
                 if m['order_id'] == 'ORD-LAB19-004'
                 and m['error_reason'] == 'NEGATIVE_AMOUNT'),
                None
            )
            if not target:
                print(f"{C.YELLOW}ORD-LAB19-004 (NEGATIVE_AMOUNT) not found in DLQ.")
                print(f"Produce Order 4 first (Terminal A, scenario 4).{C.RESET}")
            else:
                success = apply_correction_and_replay(target)
                if success:
                    print(f"\n{C.GREEN}Order 4 replayed. "
                          f"Watch Terminal B (payment-service-with-dlq) for processing.{C.RESET}")

        elif choice == '3':
            # Replay Order 6 — invalid card format
            dlq_messages = read_dlq_messages()
            target = next(
                (m for m in dlq_messages
                 if m['order_id'] == 'ORD-LAB19-006'
                 and m['error_reason'] == 'INVALID_CARD_FORMAT'),
                None
            )
            if not target:
                print(f"{C.YELLOW}ORD-LAB19-006 (INVALID_CARD_FORMAT) not found in DLQ.")
                print(f"Produce Order 6 first (Terminal A, scenario 6).{C.RESET}")
            else:
                success = apply_correction_and_replay(target)
                if success:
                    print(f"\n{C.GREEN}Order 6 replayed. "
                          f"Watch Terminal B (payment-service-with-dlq) for processing.{C.RESET}")

        elif choice == '4':
            print(f"\n{C.RED}{C.BOLD}WHY ORDER 2 CANNOT BE REPLAYED{C.RESET}")
            print(f"\n  Order 2 failed with: MISSING_REQUIRED_FIELD (customer_id)")
            print(f"\n  The problem: customer_id is completely absent from the message.")
            print(f"  The dlq-processor has the original message bytes but")
            print(f"  does NOT know what the correct customer_id should be.")
            print(f"  There is no way to look this up — the information")
            print(f"  was never in the message.")
            print(f"\n  Required action:")
            print(f"  1. File bug report against order-service-v2")
            print(f"     (it produced an order without customer_id)")
            print(f"  2. order-service team fixes the producer bug")
            print(f"  3. Customer re-places the order through the fixed system")
            print(f"  4. New order goes through the pipeline correctly")
            print(f"\n  The DLQ message is kept as evidence of the producer bug.")
            print(f"  It is NOT replayed. It is eventually expired by retention policy.")

        elif choice == '5':
            print(f"\n{C.MAGENTA}{C.BOLD}WHY ORDER 8 CANNOT BE REPLAYED (YET){C.RESET}")
            print(f"\n  Order 8 failed with: EXCEEDS_DAILY_LIMIT ($15,000 > $10,000)")
            print(f"\n  The message itself is perfectly valid:")
            print(f"  - customer_id present")
            print(f"  - card format correct")
            print(f"  - amount is positive")
            print(f"  - all required fields present")
            print(f"\n  The problem: business policy prohibits automatic processing")
            print(f"  of single transactions above $10,000 without manual authorization.")
            print(f"\n  Required action:")
            print(f"  1. Alert sent to finance team (via notifications.sent → DLQ alert)")
            print(f"  2. Finance team contacts customer to verify legitimacy")
            print(f"  3. Finance team grants manual authorization")
            print(f"  4. Authorized operator adjusts DAILY_LIMIT temporarily")
            print(f"     OR uses a special high-value approval workflow")
            print(f"  5. Message replayed with authorization token in headers")
            print(f"\n  This is a POLICY VIOLATION, not a data error or infrastructure error.")
            print(f"  Replaying without authorization would bypass financial controls.")

        else:
            print(f"{C.RED}Invalid choice.{C.RESET}")

if __name__ == '__main__':
    main()
