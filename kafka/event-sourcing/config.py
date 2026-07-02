"""
Centralized configuration for the order event sourcing microservices.
"""

# 3-node Kafka cluster bootstrap servers
BOOTSTRAP_SERVERS = (
    '192.168.100.21:9092,'
    '192.168.100.22:9092,'
    '192.168.100.23:9092'
)

# Topic configuration
ORDERS_EVENTS_TOPIC = 'orders.events'
TOPIC_PARTITIONS = 3
TOPIC_REPLICATION_FACTOR = 3

# Consumer group IDs
PROJECTOR_GROUP_ID = 'order-projector-v1'
AUDIT_GROUP_ID = 'audit-reader-v1'

# Valid order event types in lifecycle sequence
ORDER_EVENT_TYPES = [
    'ORDER_CREATED',
    'PAYMENT_RECEIVED',
    'ITEMS_PICKED',
    'SHIPPED',
    'DELIVERED',
    'CANCELLED',
    'DELIVERY_FAILED',
    'DELIVERY_RETRY',
    'CORRECTION',
]

# Valid order statuses (derived from events by projector)
ORDER_STATUS_MAP = {
    'ORDER_CREATED':    'PENDING_PAYMENT',
    'PAYMENT_RECEIVED': 'PAID',
    'ITEMS_PICKED':     'PROCESSING',
    'SHIPPED':          'SHIPPED',
    'DELIVERED':        'DELIVERED',
    'CANCELLED':        'CANCELLED',
    'DELIVERY_FAILED':  'DELIVERY_FAILED',
    'DELIVERY_RETRY':   'OUT_FOR_DELIVERY',
    'CORRECTION':       None,  # CORRECTION does not change status
}

# Terminal color codes for visual clarity in multi-terminal
class Colors:
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'
    RESET   = '\033[0m'
    BOLD    = '\033[1m'
