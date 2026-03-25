# CST8916 – Week 11 Lab: Clickstream Event Producer
#
# Sends simulated clickstream events to Azure Event Hubs in three batches.
# Each batch has different characteristics (device type, engagement, etc.)
# to demonstrate filtering, aggregation, and windowing in Stream Analytics.
#
# Usage:
#   export EVENT_HUB_CONNECTION_STR="Endpoint=sb://..."
#   export EVENT_HUB_NAME="clickstream"
#   python producer.py

import os
import json
import time
import uuid
import random
from datetime import datetime, timezone, timedelta

from azure.eventhub import EventHubProducerClient, EventData

# ---------------------------------------------------------------------------
# Configuration – read from environment variables
# ---------------------------------------------------------------------------
CONNECTION_STR = os.environ.get("EVENT_HUB_CONNECTION_STR", "")
EVENT_HUB_NAME = os.environ.get("EVENT_HUB_NAME", "clickstream")

if not CONNECTION_STR:
    print("ERROR: EVENT_HUB_CONNECTION_STR environment variable is not set.")
    print()
    print("Set it before running this script:")
    print('  export EVENT_HUB_CONNECTION_STR="Endpoint=sb://..."')
    print('  export EVENT_HUB_NAME="clickstream"')
    exit(1)

# ---------------------------------------------------------------------------
# Batch definitions
#
# Each batch simulates a different type of website traffic.
# Fields like userId, ipAddress, sessionId, and timeToCompletePage are
# randomized per event to create realistic variety. Fields like deviceType,
# eventScore, and isLead are fixed per batch so SAQL queries can produce
# clear, predictable groupings.
# ---------------------------------------------------------------------------

BROWSERS = ["Chrome", "Firefox", "Safari", "Edge"]
PATHS_MOBILE = [
    "/products/phones",
    "/products/phones/iphone",
    "/products/headphones",
    "/checkout",
    "/cart",
]
PATHS_DESKTOP = [
    "/pricing",
    "/products/laptops",
    "/products/laptops/dell-xps",
    "/enterprise/demo",
    "/contact-sales",
]
PATHS_BLOG = [
    "/blog/top-10-gadgets",
    "/blog/best-deals-2026",
    "/blog/phone-vs-tablet",
    "/support/faq",
    "/support/contact",
]

BATCHES = [
    {
        "name": "Batch 1 – Mobile users, high engagement",
        "count": 10,
        "template": {
            "os": "Android",
            "deviceType": "phone",
            "isLead": 1,
            "eventScore": 95,
            "eventDuration": 12000,
            "diagnostics": "",
        },
        "paths": PATHS_MOBILE,
        "referrers": ["http://google.com", "http://google.com/search?q=phones"],
        "load_time_range": (1500, 4000),
    },
    {
        "name": "Batch 2 – Desktop users, medium engagement",
        "count": 10,
        "template": {
            "os": "Windows",
            "deviceType": "desktop",
            "isLead": 1,
            "eventScore": 85,
            "eventDuration": 60000,
            "diagnostics": "",
        },
        "paths": PATHS_DESKTOP,
        "referrers": ["http://linkedin.com/feed", "http://google.com"],
        "load_time_range": (800, 2500),
    },
    {
        "name": "Batch 3 – Mobile users, low engagement",
        "count": 15,
        "template": {
            "os": "iOS",
            "deviceType": "phone",
            "isLead": 0,
            "eventScore": 22,
            "eventDuration": 2000,
            "diagnostics": "high_latency",
        },
        "paths": PATHS_BLOG,
        "referrers": ["http://instagram.com", "http://twitter.com", "http://facebook.com"],
        "load_time_range": (3000, 7000),
    },
]

PAUSE_BETWEEN_BATCHES = 30  # seconds


def generate_event(template, paths, referrers, load_time_range, base_time):
    """Generate a single clickstream event with randomized dynamic fields."""
    # Randomize the timestamp within a small range so events are close but not identical
    offset_seconds = random.uniform(0, 30)
    event_time = base_time + timedelta(seconds=offset_seconds)

    return {
        "timeStamp": event_time.strftime("%Y-%m-%d %H:%M:%S"),
        "ipAddress": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}",
        "userId": str(uuid.uuid4()),
        "sessionId": str(uuid.uuid4()),
        "path": random.choice(paths),
        "queryParameters": random.choice(["", "?ref=google", "?utm_source=social", "?promo=SPRING26"]),
        "referrerUrl": random.choice(referrers),
        "browser": random.choice(BROWSERS),
        "timeToCompletePage": random.randint(*load_time_range),
        "eventFirstTimestamp": random.randint(100000, 999999),
        **template,
    }


def send_batch(producer, batch_config, base_time):
    """Send a batch of events to Event Hubs."""
    name = batch_config["name"]
    count = batch_config["count"]

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  Sending {count} events...")
    print(f"  deviceType={batch_config['template']['deviceType']}, "
          f"eventScore={batch_config['template']['eventScore']}, "
          f"isLead={batch_config['template']['isLead']}")
    print(f"{'='*60}")

    event_batch = producer.create_batch()

    for i in range(count):
        event = generate_event(
            template=batch_config["template"],
            paths=batch_config["paths"],
            referrers=batch_config["referrers"],
            load_time_range=batch_config["load_time_range"],
            base_time=base_time,
        )
        event_data = EventData(json.dumps(event))
        event_batch.add(event_data)

        # Print a sample event (first one only)
        if i == 0:
            print(f"\n  Sample event:")
            print(f"  {json.dumps(event, indent=4)}")

    producer.send_batch(event_batch)
    print(f"\n  ✓ {count} events sent successfully!")


def main():
    print()
    print("CST8916 Week 11 – Clickstream Event Producer")
    print("=" * 60)
    print(f"  Event Hub:  {EVENT_HUB_NAME}")
    print(f"  Batches:    {len(BATCHES)}")
    print(f"  Pause:      {PAUSE_BETWEEN_BATCHES}s between batches")
    print()

    producer = EventHubProducerClient.from_connection_string(
        conn_str=CONNECTION_STR,
        eventhub_name=EVENT_HUB_NAME,
    )

    with producer:
        # Use current UTC time as the base, so events land in recent time windows
        base_time = datetime.now(timezone.utc)

        for i, batch_config in enumerate(BATCHES):
            # Offset each batch's timestamps so they fall in different windows
            batch_base_time = base_time + timedelta(seconds=i * 120)
            send_batch(producer, batch_config, batch_base_time)

            # Pause between batches (except after the last one)
            if i < len(BATCHES) - 1:
                print(f"\n  Waiting {PAUSE_BETWEEN_BATCHES} seconds before next batch...")
                time.sleep(PAUSE_BETWEEN_BATCHES)

    print()
    print("=" * 60)
    print("  All batches sent!")
    print()
    print("  Next steps:")
    print("  1. Go to your Stream Analytics job in the Azure Portal")
    print("  2. Click Query → paste a SAQL query → click Test query")
    print("  3. See the lab README for 8 example queries to try")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
