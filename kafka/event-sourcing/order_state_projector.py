"""
order-state-projector : Read Model Builder

This service is the READ SIDE of the event sourcing architecture.
It consumes all events from orders.events and builds
an in-memory projection of current order state.

Design principles:
- Replays from offset 0 on startup (or from last committed offset)
- Maintains one state object per order_id
- CORRECTION events update metadata without changing order status
- Provides query interface: current status, orders by status, full history
- The projection is a CACHE of derived state, it can always be rebuilt
  from the event log if corrupted or lost

Consumer group: order-projector-v1
  This group's committed offset is how the projector knows
  where to resume after restart.

Usage:
    python3 order_state_projector.py [--from-beginning]
    --from-beginning forces replay from offset 0 regardless of
    committed position (useful for rebuild demonstration)
"""

import json
import sys
import signal
import time
from collections import defaultdict
from datetime import datetime, timezone
from confluent_kafka import Consumer, KafkaError
import config

# Projection state ──────────────────────────────────────────
# In production: persisted to PostgreSQL or Redis
# Here: in-memory, rebuilt on startup from Kafka

class OrderProjection:
    """
    Represents the current known state of one order.
    Built by applying events in sequence.
    """
    def __init__(self, order_id):
        self.order_id        = order_id
        self.status          = 'UNKNOWN'
        self.customer_id     = None
        self.total_amount    = None
        self.currency        = 'USD'
        self.items           = []
        self.shipping_address = None
        self.carrier         = None
        self.tracking_number = None
        self.delivery_attempts = 0
        self.corrections     = []
        self.event_history   = []   # ordered list of all events applied
        self.created_at      = None
        self.last_updated_at = None
        self.version         = 0    # number of events applied

    def to_dict(self):
        return {
            'order_id':          self.order_id,
            'status':            self.status,
            'customer_id':       self.customer_id,
            'total_amount':      self.total_amount,
            'currency':          self.currency,
            'items':             self.items,
            'shipping_address':  self.shipping_address,
            'carrier':           self.carrier,
            'tracking_number':   self.tracking_number,
            'delivery_attempts': self.delivery_attempts,
            'corrections_count': len(self.corrections),
            'event_count':       self.version,
            'created_at':        self.created_at,
            'last_updated_at':   self.last_updated_at,
        }

# Global projection store: order_id -> OrderProjection
projections = {}
total_events_processed = 0
replay_complete = False

def apply_event_to_projection(event, kafka_partition, kafka_offset):
    """
    Apply one event to the in-memory projection.

    This function is the heart of the event sourcing pattern.
    It must be:
      Deterministic: same event always produces same state change
      Complete: handles every known event type
      Defensive: unknown event types are logged but do not crash

    Called for every event — both during initial replay from
    offset 0 and for live events arriving after replay completes.
    """
    global total_events_processed

    order_id   = event.get('order_id')
    event_type = event.get('event_type')
    event_id   = event.get('event_id')
    event_time = event.get('event_time')
    payload    = event.get('payload', {})

    # Get or create projection for this order
    if order_id not in projections:
        projections[order_id] = OrderProjection(order_id)

    proj = projections[order_id]

    # Record this event in the order's history
    proj.event_history.append({
        'event_id':   event_id,
        'event_type': event_type,
        'event_time': event_time,
        'partition':  kafka_partition,
        'offset':     kafka_offset,
    })
    proj.last_updated_at = event_time
    proj.version += 1
    total_events_processed += 1

    # Apply event-specific state changes
    if event_type == 'ORDER_CREATED':
        proj.status           = config.ORDER_STATUS_MAP['ORDER_CREATED']
        proj.customer_id      = payload.get('customer_id')
        proj.total_amount     = payload.get('total_amount')
        proj.currency         = payload.get('currency', 'USD')
        proj.items            = payload.get('items', [])
        proj.shipping_address = payload.get('shipping_address')
        proj.created_at       = event_time

    elif event_type == 'PAYMENT_RECEIVED':
        proj.status = config.ORDER_STATUS_MAP['PAYMENT_RECEIVED']

    elif event_type == 'ITEMS_PICKED':
        proj.status = config.ORDER_STATUS_MAP['ITEMS_PICKED']

    elif event_type == 'SHIPPED':
        proj.status          = config.ORDER_STATUS_MAP['SHIPPED']
        proj.carrier         = payload.get('carrier')
        proj.tracking_number = payload.get('tracking_number')

    elif event_type == 'DELIVERED':
        proj.status = config.ORDER_STATUS_MAP['DELIVERED']

    elif event_type == 'CANCELLED':
        proj.status = config.ORDER_STATUS_MAP['CANCELLED']

    elif event_type == 'DELIVERY_FAILED':
        proj.status             = config.ORDER_STATUS_MAP['DELIVERY_FAILED']
        proj.delivery_attempts  = payload.get('attempt_number', proj.delivery_attempts + 1)

    elif event_type == 'DELIVERY_RETRY':
        proj.status            = config.ORDER_STATUS_MAP['DELIVERY_RETRY']
        proj.delivery_attempts = payload.get('attempt_number', proj.delivery_attempts)

    elif event_type == 'CORRECTION':
        # CORRECTION does not change order status
        # It updates the relevant field and records the correction
        correction_type = payload.get('correction_type')
        correction_data = payload.get('correction_data', {})

        if correction_type == 'ADDRESS_CORRECTION':
            proj.shipping_address = correction_data.get(
                'corrected_address', proj.shipping_address
            )

        proj.corrections.append({
            'correction_type':   correction_type,
            'corrects_event_id': payload.get('corrects_event_id'),
            'authorized_by':     payload.get('authorized_by'),
            'reason':            payload.get('reason'),
            'correction_time':   payload.get('correction_time'),
        })

    else:
        print(f"  {config.Colors.YELLOW}"
              f"[WARN] Unknown event type: {event_type} for {order_id}"
              f"{config.Colors.RESET}")

    return proj

def print_event_applied(event, proj, partition, offset, is_replay):
    """Print formatted output for each event applied."""
    event_type = event.get('event_type')
    order_id   = event.get('order_id')

    mode = f"{config.Colors.YELLOW}[REPLAY]{config.Colors.RESET}" \
        if is_replay else \
        f"{config.Colors.GREEN}[LIVE]{config.Colors.RESET}"

    status_color = {
        'PENDING_PAYMENT': config.Colors.YELLOW,
        'PAID':            config.Colors.CYAN,
        'PROCESSING':      config.Colors.CYAN,
        'SHIPPED':         config.Colors.BLUE,
        'DELIVERED':       config.Colors.GREEN,
        'CANCELLED':       config.Colors.RED,
        'DELIVERY_FAILED': config.Colors.RED,
        'OUT_FOR_DELIVERY':config.Colors.CYAN,
    }.get(proj.status, config.Colors.WHITE)

    print(
        f"\n  {mode} "
        f"P{partition}:O{offset:4d} | "
        f"{config.Colors.BOLD}{order_id}{config.Colors.RESET} | "
        f"{event_type:20s} | "
        f"Status: {status_color}{proj.status}{config.Colors.RESET} | "
        f"v{proj.version}"
    )

    if event_type == 'CORRECTION':
        payload = event.get('payload', {})
        print(
            f"         {config.Colors.MAGENTA}"
            f"CORRECTION: {payload.get('correction_type')} | "
            f"Corrects: {str(payload.get('corrects_event_id',''))[:16]}... | "
            f"By: {payload.get('authorized_by')}"
            f"{config.Colors.RESET}"
        )

def print_projection_summary():
    """Print current state of all orders in the projection."""
    print(f"\n{config.Colors.BOLD}{'═'*65}{config.Colors.RESET}")
    print(f"{config.Colors.BOLD}  CURRENT ORDER PROJECTIONS{config.Colors.RESET}")
    print(f"{config.Colors.BOLD}{'═'*65}{config.Colors.RESET}")

    if not projections:
        print(f"  No orders in projection yet.")
        return

    status_groups = defaultdict(list)
    for order_id, proj in sorted(projections.items()):
        status_groups[proj.status].append(proj)

    for status, orders in sorted(status_groups.items()):
        color = {
            'PENDING_PAYMENT': config.Colors.YELLOW,
            'PAID':            config.Colors.CYAN,
            'PROCESSING':      config.Colors.CYAN,
            'SHIPPED':         config.Colors.BLUE,
            'DELIVERED':       config.Colors.GREEN,
            'CANCELLED':       config.Colors.RED,
            'DELIVERY_FAILED': config.Colors.RED,
            'OUT_FOR_DELIVERY':config.Colors.CYAN,
        }.get(status, config.Colors.WHITE)

        print(f"\n  {color}{status}{config.Colors.RESET} "
              f"({len(orders)} order{'s' if len(orders) > 1 else ''}):")

        for proj in orders:
            corrections_note = (
                f" | {config.Colors.MAGENTA}{len(proj.corrections)} correction(s){config.Colors.RESET}"
                if proj.corrections else ''
            )
            delivery_note = (
                f" | delivery attempts: {proj.delivery_attempts}"
                if proj.delivery_attempts > 0 else ''
            )
            print(
                f"    {config.Colors.BOLD}{proj.order_id}{config.Colors.RESET} | "
                f"customer={proj.customer_id} | "
                f"amount=${proj.total_amount:.2f} {proj.currency} | "
                f"events={proj.version}"
                f"{corrections_note}"
                f"{delivery_note}"
            )

    print(f"\n  Total orders in projection: {len(projections)}")
    print(f"  Total events processed:     {total_events_processed}")
    print(f"{'═'*65}")

def query_orders_by_status(status):
    """Query the in-memory projection no Kafka read required."""
    results = [
        proj for proj in projections.values()
        if proj.status == status
    ]
    return results

def query_order_by_id(order_id):
    """Query current state of a specific order no Kafka read required."""
    return projections.get(order_id)

def print_query_result(order_id):
    proj = query_order_by_id(order_id)
    if not proj:
        print(f"  Order {order_id} not found in projection.")
        return

    print(f"\n{config.Colors.BOLD}QUERY RESULT: {order_id}{config.Colors.RESET}")
    for k, v in proj.to_dict().items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} items")
        else:
            print(f"  {k}: {v}")

    if proj.event_history:
        print(f"\n  Event history ({len(proj.event_history)} events):")
        for e in proj.event_history:
            print(f"    [{e['event_type']:20s}] "
                  f"at {e['event_time']} "
                  f"P{e['partition']}:O{e['offset']}")

    if proj.corrections:
        print(f"\n  Corrections applied:")
        for c in proj.corrections:
            print(f"    type={c['correction_type']} | "
                  f"corrects={str(c['corrects_event_id'])[:16]}... | "
                  f"by={c['authorized_by']}")

# Main consumer loop ────────────────────────────────────────

def main():
    global replay_complete

    from_beginning = '--from-beginning' in sys.argv

    print(f"\n{config.Colors.BOLD}order-state-projector starting...{config.Colors.RESET}")
    print(f"Cluster:       {config.BOOTSTRAP_SERVERS}")
    print(f"Topic:         {config.ORDERS_EVENTS_TOPIC}")
    print(f"Consumer group:{config.PROJECTOR_GROUP_ID}")
    print(f"Start offset:  {'EARLIEST (full replay)' if from_beginning else 'COMMITTED (resume)'}")

    consumer = Consumer({
        'bootstrap.servers':  config.BOOTSTRAP_SERVERS,
        'group.id':           config.PROJECTOR_GROUP_ID,
        'auto.offset.reset':  'earliest',
        'enable.auto.commit': 'false',
        'max.poll.interval.ms': '60000',
        'session.timeout.ms':   '30000',
        'heartbeat.interval.ms':'10000',
    })

    if from_beginning:
        # Reset to beginning by temporarily subscribing, getting assignment,
        # then seeking to beginning
        consumer.subscribe([config.ORDERS_EVENTS_TOPIC])
        # Poll once to trigger assignment
        consumer.poll(timeout=5.0)
        # Seek all assigned partitions to beginning
        assignment = consumer.assignment()
        if assignment:
            from confluent_kafka import TopicPartition
            beginning_offsets = [
                TopicPartition(tp.topic, tp.partition, 0)
                for tp in assignment
            ]
            consumer.assign(beginning_offsets)
            print(f"{config.Colors.YELLOW}"
                  f"Seeked to beginning on {len(assignment)} partitions."
                  f"{config.Colors.RESET}")
    else:
        consumer.subscribe([config.ORDERS_EVENTS_TOPIC])

    shutdown = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown
        shutdown = True
        print(f"\n{config.Colors.YELLOW}Shutdown requested.{config.Colors.RESET}")

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print(f"\n{config.Colors.CYAN}Replaying event log...{config.Colors.RESET}")
    print(f"{'─'*65}")

    last_message_time = time.time()
    IDLE_TIMEOUT = 5.0  # seconds of no messages = initial replay complete

    try:
        while not shutdown:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                # Check if initial replay is complete
                if (not replay_complete and
                        total_events_processed > 0 and
                        time.time() - last_message_time > IDLE_TIMEOUT):
                    replay_complete = True
                    print_projection_summary()
                    print(f"\n{config.Colors.GREEN}"
                          f"Initial replay complete. "
                          f"Listening for live events..."
                          f"{config.Colors.RESET}")
                    print(f"\nCommands while running:")
                    print(f"  Press ENTER to print current projection summary")
                    print(f"  Type order ID (e.g. ORD-1001) + ENTER to query specific order")
                    print(f"  Type status (e.g. CANCELLED) + ENTER to query by status")
                    print(f"  Ctrl+C to stop")

                # Handle interactive query input
                # (non-blocking stdin check)
                import select
                if select.select([sys.stdin], [], [], 0)[0]:
                    user_input = sys.stdin.readline().strip()
                    if not user_input:
                        print_projection_summary()
                    elif user_input.startswith('ORD-'):
                        print_query_result(user_input)
                    elif user_input.upper() in [
                        'PENDING_PAYMENT', 'PAID', 'PROCESSING',
                        'SHIPPED', 'DELIVERED', 'CANCELLED',
                        'DELIVERY_FAILED', 'OUT_FOR_DELIVERY'
                    ]:
                        results = query_orders_by_status(user_input.upper())
                        print(f"\nOrders with status={user_input.upper()}: "
                              f"{len(results)}")
                        for proj in results:
                            print(f"  {proj.order_id} | "
                                  f"customer={proj.customer_id} | "
                                  f"amount=${proj.total_amount:.2f}")
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"{config.Colors.RED}Error: {msg.error()}{config.Colors.RESET}")
                continue

            last_message_time = time.time()

            # Parse event
            try:
                event = json.loads(msg.value().decode('utf-8'))
            except json.JSONDecodeError as e:
                print(f"{config.Colors.RED}"
                      f"Parse error at P{msg.partition()}:O{msg.offset()}: {e}"
                      f"{config.Colors.RESET}")
                continue

            # Apply to projection
            proj = apply_event_to_projection(
                event, msg.partition(), msg.offset()
            )

            # Print what happened
            print_event_applied(
                event, proj,
                msg.partition(), msg.offset(),
                is_replay=not replay_complete
            )

            # Commit offset after successful projection
            consumer.commit(asynchronous=False)

    except Exception as e:
        print(f"{config.Colors.RED}Projector error: {e}{config.Colors.RESET}")
        raise
    finally:
        consumer.close()
        print(f"\n{config.Colors.YELLOW}Projector stopped.{config.Colors.RESET}")
        print_projection_summary()

if __name__ == '__main__':
    main()
