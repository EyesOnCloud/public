"""
Configuration for the DLQ payment pipeline lab.
"""

BOOTSTRAP_SERVERS = (
    '192.168.100.21:9092,'
    '192.168.100.22:9092,'
    '192.168.100.23:9092'
)

# ── Topics from previous demo (reused) ───────────────────────────────
ORDERS_PLACED_TOPIC      = 'orders.placed'
PAYMENTS_PROCESSED_TOPIC = 'payments.processed'
PAYMENTS_FAILED_TOPIC    = 'payments.failed'

# ── New DLQ topics for this demo ─────────────────────────────────
PAYMENTS_DLQ_TOPIC      = 'payments.dlq'
PAYMENTS_REPLAYED_TOPIC = 'payments.dlq.replayed'

# ── Consumer group IDs ────────────────────────────────────────
PAYMENT_SERVICE_GROUP    = 'payment-service-dlq-v1'
DLQ_INSPECTOR_GROUP      = 'dlq-inspector-v1'
DLQ_PROCESSOR_GROUP      = 'dlq-processor-v1'

# ── DLQ routing rules ─────────────────────────────────────────
# Maximum retry attempts before routing to DLQ
# Infrastructure failures (transient): retry up to MAX_RETRIES
# Data failures: route to DLQ immediately (0 retries)
MAX_INFRASTRUCTURE_RETRIES = 3

# Daily transaction limit — orders above this are policy violations
DAILY_LIMIT = 10000.00

# Valid card number format: exactly 4 digits
VALID_CARD_LAST4_PATTERN = r'^\d{4}$'

# Required fields in every order payload
REQUIRED_ORDER_FIELDS = [
    'order_id', 'customer_id', 'customer_email',
    'total_amount', 'currency', 'payment', 'items'
]

# Required fields in payment sub-object
REQUIRED_PAYMENT_FIELDS = ['method', 'card_last4']

# ── DLQ failure categories ────────────────────────────────────
# DATA failures: route to DLQ immediately, no retry
DLQ_DATA_FAILURES = {
    'MISSING_REQUIRED_FIELD',
    'INVALID_CARD_FORMAT',
    'NEGATIVE_AMOUNT',
    'ZERO_AMOUNT',
    'EXCEEDS_DAILY_LIMIT',
    'INVALID_CURRENCY',
    'SCHEMA_VALIDATION_FAILED',
    'UNSUPPORTED_PAYMENT_METHOD',
}

# INFRASTRUCTURE failures: retry before DLQ
DLQ_INFRASTRUCTURE_FAILURES = {
    'PAYMENT_GATEWAY_TIMEOUT',
    'DATABASE_CONNECTION_LOST',
    'DOWNSTREAM_SERVICE_UNAVAILABLE',
}

# ── Colors ────────────────────────────────────────────────────
class Colors:
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'
    BOLD    = '\033[1m'
    RESET   = '\033[0m'

SERVICE_COLORS = {
    'order-service':         Colors.CYAN,
    'payment-service-dlq':  Colors.BLUE,
    'dlq-inspector':        Colors.YELLOW,
    'dlq-processor':        Colors.MAGENTA,
}
