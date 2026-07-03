"""
Centralized configuration for choreography saga microservices.
All services import from here.

IMPORTANT: In a real microservices architecture, each service
would have its own config file and would NOT share configuration
with other services. They are deployed independently.
We use a shared config here ONLY for lab convenience —
it avoids participants editing four files to change broker addresses.
The services themselves remain fully decoupled in their logic.
"""

BOOTSTRAP_SERVERS = (
    '192.168.100.21:9092,'
    '192.168.100.22:9092,'
    '192.168.100.23:9092'
)

# Topic names ───────────────────────────────────────────────
ORDERS_PLACED_TOPIC         = 'orders.placed'
PAYMENTS_PROCESSED_TOPIC    = 'payments.processed'
PAYMENTS_FAILED_TOPIC       = 'payments.failed'
INVENTORY_RESERVED_TOPIC    = 'inventory.reserved'
INVENTORY_FAILED_TOPIC      = 'inventory.failed'
NOTIFICATIONS_SENT_TOPIC    = 'notifications.sent'

ALL_TOPICS = [
    ORDERS_PLACED_TOPIC,
    PAYMENTS_PROCESSED_TOPIC,
    PAYMENTS_FAILED_TOPIC,
    INVENTORY_RESERVED_TOPIC,
    INVENTORY_FAILED_TOPIC,
    NOTIFICATIONS_SENT_TOPIC,
]

# Consumer group IDs ────────────────────────────────────────
PAYMENT_SERVICE_GROUP    = 'payment-service-v1'
INVENTORY_SERVICE_GROUP  = 'inventory-service-v1'
NOTIFICATION_SERVICE_GROUP = 'notification-service-v1'

# ── Payment simulation rules ──────────────────────────────────
# Cards ending in these last 4 digits always fail payment
# Simulates declined cards, insufficient funds, fraud blocks
DECLINED_CARD_SUFFIXES = {'0002', '9999', '1111'}

# Orders above this amount require additional verification
# (simplified: we just fail them for the lab scenario)
HIGH_VALUE_THRESHOLD = 3000.00

# Inventory simulation ──────────────────────────────────────
# SKUs with zero stock will trigger inventory.failed
OUT_OF_STOCK_SKUS = {'SKU-CHAIR-ERGO', 'SKU-GPU-4090', 'SKU-MONITOR-8K'}

# ── Terminal colors ───────────────────────────────────────────
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

# Service identity colors — each service has its own color
# so multi-terminal output is visually distinguishable
SERVICE_COLORS = {
    'order-service':        Colors.CYAN,
    'payment-service':      Colors.BLUE,
    'inventory-service':    Colors.MAGENTA,
    'notification-service': Colors.GREEN,
}
