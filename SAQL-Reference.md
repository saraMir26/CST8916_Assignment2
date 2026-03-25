# Azure Stream Analytics – SAQL Query Reference

**CST8916 – Remote Data and Real-time Applications – Week 11**

This reference covers the **Stream Analytics Query Language (SAQL)** — the SQL-like language used to query real-time data streams in Azure Stream Analytics. If you have used SQL before (e.g., `SELECT`, `WHERE`, `GROUP BY`), you will find SAQL very familiar. The main difference is that SAQL runs **continuously** on data that never stops flowing, rather than running once on a static table.

---

## Table of Contents

- [Simple Query Examples](#saql-simple-query-examples)
- [Aggregation](#saql-aggregation)
  - [Understanding TIMESTAMP BY](#understanding-timestamp-by)
  - [Handling Late-Arriving Events](#handling-late-arriving-events)
- [Windowing Functions](#windowing-functions)
  - [Tumbling Window](#tumbling-window)
  - [Hopping Window](#hopping-window)
  - [Sliding Window](#sliding-window)
  - [Session Window](#session-window)
  - [Summary](#windowing-functions-summary)
- [JOIN with Reference Data](#saql-join-with-reference-data)
- [Temporal JOIN (Stream-to-Stream)](#saql-temporal-join-stream-to-stream)
- [ASA Output Destinations](#asa-output-destinations)

---

## SAQL: Simple Query Examples

These examples use a stream called `SensorInput`. Think of it as a table that new rows are constantly being added to — one row every time a sensor sends a reading.

Each row (event) in `SensorInput` looks something like this:

```json
{ "deviceId": "sensor-01", "temperature": 72.5, "eventTime": "2026-03-24T14:30:00Z" }
```

### Pass-through (Forward All Events)

```sql
SELECT *
FROM SensorInput
```

- `SELECT *` means "give me all columns"
- This forwards **every single event** to the output with no changes — useful for debugging or logging all raw data

### Filtering

```sql
SELECT deviceId, temperature, eventTime
FROM SensorInput
WHERE temperature > 100
```

- `WHERE temperature > 100` acts as a filter — only events where the temperature is above 100 are passed through
- Everything else is **silently dropped**
- **Real-world analogy:** Imagine a security guard who only lets people through the door if they have a VIP badge. Everyone else is turned away.

### Projection (Selecting Specific Fields)

```sql
SELECT deviceId,
       temperature * 1.8 + 32 AS temperatureF,
       eventTime
FROM SensorInput
```

- **Projection** means picking only the columns you need (instead of `SELECT *` which grabs everything)
- `temperature * 1.8 + 32 AS temperatureF` converts Celsius to Fahrenheit and gives the result a new name (`temperatureF`)
- `AS` is just an alias — it renames the column in the output so it is easier to understand

---

## SAQL: Aggregation

In a regular database, you can compute `AVG(price)` across all rows because the table has a fixed number of rows. But a stream **never ends** — new events keep arriving forever. So the question "what is the average?" does not make sense unless you specify **over what time period**.

That is why aggregation in stream processing always requires a **time window** — a defined chunk of time to group events into.

```sql
SELECT deviceId,
       AVG(temperature) AS avgTemp,
       MAX(temperature) AS maxTemp,
       COUNT(*) AS eventCount,
       System.Timestamp() AS windowEnd
FROM SensorInput
TIMESTAMP BY eventTime
GROUP BY deviceId, TumblingWindow(minute, 5)
```

Let's break this down line by line:

| Line | What it does |
|------|-------------|
| `SELECT deviceId` | Include the device ID in the output so we know which sensor this is for |
| `AVG(temperature) AS avgTemp` | Calculate the average temperature across all events in the window |
| `MAX(temperature) AS maxTemp` | Find the highest temperature reading in the window |
| `COUNT(*) AS eventCount` | Count how many events (readings) arrived in the window |
| `System.Timestamp() AS windowEnd` | The timestamp marking the end of each window — tells you *when* this result was calculated |
| `FROM SensorInput` | Read from the sensor data stream |
| `TIMESTAMP BY eventTime` | Use the `eventTime` field from the event as the official timestamp (explained below) |
| `GROUP BY deviceId, TumblingWindow(minute, 5)` | Group results by device AND by 5-minute time windows |

**Result:** Every 5 minutes, this query outputs one row per device showing the average, max, and count for that period.

### Understanding TIMESTAMP BY

You may have noticed the `TIMESTAMP BY eventTime` line in the query above. This is a critical clause — it tells ASA **which field in your event represents the actual time** the event occurred.

Every event has **two timestamps**:

1. **Event time** — when the event actually happened at the source (e.g., when the sensor took the reading)
2. **Arrival time** — when Azure Event Hubs received the event (could be later due to network delays)

Without `TIMESTAMP BY`, ASA uses the arrival time. With it, ASA uses the event time — which is more accurate.

**Real-world analogy:** Imagine you mail a letter on Monday (event time), but the post office receives it on Wednesday (arrival time). If you are sorting mail by "when it was written," you want to use Monday, not Wednesday.

```
Event generated:  14:30:00   (event time — when the sensor measured)
Event arrives:    14:30:05   (arrival time — when Event Hubs received it)

Without TIMESTAMP BY: ASA uses 14:30:05
With TIMESTAMP BY:    ASA uses 14:30:00  ← more accurate
```

This matters especially for **windowing** — if you are grouping events into 1-minute windows, a 5-second delay could cause an event to land in the wrong window. You will see `TIMESTAMP BY` used in almost every SAQL query throughout this reference.

### Handling Late-Arriving Events

Real-world data is messy. Events can arrive **late** due to:
- **Network delays** — a sensor's Wi-Fi drops briefly and the event is retransmitted
- **Device buffering** — a device batches events and sends them all at once
- **Retransmission** — a failed send is retried seconds or minutes later

**The problem:** If a window covers 14:30–14:35, and an event with `eventTime = 14:33` arrives at 14:36 (after the window has already closed), should it be included in that window or dropped?

ASA provides two configurable policies for handling this:

**1. Late Arrival Tolerance** (default: 5 seconds)

This controls how late an event can physically arrive and still be placed in the correct window.

```
Example: Late Arrival Tolerance = 1 minute

Window: 14:30 – 14:35

Event arrives at 14:36 with eventTime = 14:33
  → 14:36 - 14:35 = 1 min late → Within tolerance → included in window ✓

Event arrives at 14:40 with eventTime = 14:33
  → 14:40 - 14:35 = 5 min late → Exceeds tolerance → dropped or adjusted ✗
```

**2. Out-of-Order Tolerance** (default: 0 seconds)

Events do not always arrive in the order they were created. This controls how much ASA will wait to **re-sort** events into the correct order before processing them.

```
Example: Out-of-Order Tolerance = 10 seconds

Three events arrive at Event Hubs in this order:
  Arrived 1st:  eventTime = 14:30:20   (created second)
  Arrived 2nd:  eventTime = 14:30:10   (created first — arrived out of order!)
  Arrived 3rd:  eventTime = 14:30:25   (created third)

  → 14:30:20 - 14:30:10 = 10 seconds out of order
  → Within tolerance → ASA re-sorts them: 14:30:10, 14:30:20, 14:30:25 ✓

If the gap were larger than 10 seconds, ASA would NOT wait to re-sort
and would process them in arrival order instead.
```

**In simple terms:**
- **Late Arrival** = "the event showed up after the window already closed" (like turning in homework after the deadline)
- **Out-of-Order** = "events arrived in the wrong sequence" (like receiving email replies before the original message)

**Rule of thumb for beginners:** Start with the defaults. If you notice events being dropped (your counts seem too low), increase the late arrival tolerance. A higher tolerance uses more memory but ensures more events land in the correct window.

---

## Windowing Functions

Windows are what make stream processing powerful. They define **how to group events over time**. Without windows, you cannot do any aggregation (SUM, AVG, COUNT, etc.) on a never-ending stream.

**Think of it this way:** Imagine you are standing by a highway counting cars. You cannot say "the total number of cars" because cars never stop coming. But you *can* say "the number of cars in the last 5 minutes." That 5-minute chunk is a **window**.

Azure Stream Analytics supports four types of windows:

```
Time ──────────────────────────────────────────→

Tumbling:    |  Window 1  |  Window 2  |  Window 3  |
             |____________|____________|____________|
             No overlap, no gaps

Hopping:     |  Window 1     |
                |  Window 2     |
                   |  Window 3     |
             Overlapping windows

Sliding:         |  Window  |
             Triggered only when events enter/exit

Session:     |  Session 1  |      |  Session 2  |
             Groups events with gaps < timeout
```

---

### Tumbling Window

The simplest and most commonly used window type.

- **Fixed-size**, **non-overlapping**, **contiguous** time intervals
- Every event belongs to **exactly one** window — no event is counted twice
- Windows follow each other back-to-back with no gaps

**Real-world analogy:** Think of a cash register that prints a subtotal every 5 minutes. At 2:00 PM it prints the total sales from 1:55–2:00, then at 2:05 PM it prints 2:00–2:05, and so on. Each sale is counted in exactly one subtotal.

```
Events:    e1  e2  e3  e4  e5  e6  e7  e8  e9
Time:      |────5 min────|────5 min────|────5 min────|
           |  Window 1   |  Window 2   |  Window 3   |
           | e1, e2, e3  | e4, e5, e6  | e7, e8, e9  |
```

```sql
SELECT deviceId,
       AVG(temperature) AS avgTemp,
       System.Timestamp() AS windowEnd
FROM SensorInput
TIMESTAMP BY eventTime
GROUP BY deviceId, TumblingWindow(minute, 5)
```

- `TumblingWindow(minute, 5)` means "create a new window every 5 minutes"
- The first argument is the time unit (`second`, `minute`, `hour`), the second is the size

**Use case:** Calculate average temperature every 5 minutes per device.

---

### Hopping Window

- **Fixed-size** windows that **overlap** with each other
- Defined by two parameters: **window size** (how long each window lasts) and **hop size** (how often a new window starts)
- Because windows overlap, a single event can belong to **multiple** windows and be counted more than once

**Real-world analogy:** Imagine a weather report that always covers the last 10 minutes but is updated every 5 minutes. The 2:00 PM report covers 1:50–2:00, the 2:05 PM report covers 1:55–2:05. Events between 1:55 and 2:00 appear in *both* reports.

```
Window size = 10 min, Hop size = 5 min

Events:    e1  e2  e3  e4  e5  e6  e7  e8  e9
Time:      |──────────10 min──────────|
                     |──────────10 min──────────|
                                  |──────────10 min──────────|
           |←─5 min─→|
              (hop)
```

```sql
SELECT deviceId,
       AVG(temperature) AS avgTemp,
       System.Timestamp() AS windowEnd
FROM SensorInput
TIMESTAMP BY eventTime
GROUP BY deviceId, HoppingWindow(minute, 10, 5)
```

- `HoppingWindow(minute, 10, 5)` means "each window is 10 minutes long, and a new window starts every 5 minutes"
- When `hop size = window size`, a Hopping Window becomes identical to a Tumbling Window

**Use case:** Compute a rolling 10-minute average, updated every 5 minutes. Useful for smoothing out temporary spikes.

---

### Sliding Window

- Triggered **only when an event enters or exits** the window
- Unlike Tumbling and Hopping, Sliding Windows are not on a fixed schedule — they fire based on event activity
- Produces output only when the window contents actually change

**Real-world analogy:** Imagine a fire alarm that checks "have there been more than 3 smoke detections in the last 5 minutes?" It does not check on a schedule — it re-evaluates every time a new detection happens or an old one falls outside the 5-minute lookback.

```
Events:      e1       e2    e3         e4
Time:     ───┼────────┼─────┼──────────┼──→
              |──5 min──|
                       |──5 min──|
                             |──5 min──|
```

```sql
SELECT deviceId,
       COUNT(*) AS eventCount,
       System.Timestamp() AS windowEnd
FROM SensorInput
TIMESTAMP BY eventTime
GROUP BY deviceId, SlidingWindow(minute, 5)
HAVING COUNT(*) > 3
```

- `SlidingWindow(minute, 5)` means "look at the last 5 minutes from the current event"
- `HAVING COUNT(*) > 3` is a post-aggregation filter — it only outputs a result if more than 3 events occurred in that window. (`HAVING` is like `WHERE`, but it filters *after* the aggregation instead of before)

**Use case:** Alert when more than 3 events occur within any 5-minute window — useful for detecting bursts of activity or potential problems.

---

### Session Window

- Groups events that arrive **close together** in time into a single session
- A session ends when there is a **gap** (period of inactivity) larger than the specified **timeout**
- Windows vary in size — a session can be 10 seconds or 10 minutes long, depending on the data

**Real-world analogy:** Think about how a website tracks your "browsing session." You visit several pages over a few minutes, then walk away for lunch. When you come back 2 hours later, that is a new session. The session ends when you stop clicking for long enough.

```
Timeout = 5 min

Events:   e1 e2 e3      (gap > 5 min)      e4 e5 e6 e7    (gap > 5 min)    e8
          |──Session 1──|                   |───Session 2───|                |S3|
```

```sql
SELECT userId,
       COUNT(*) AS clickCount,
       MIN(eventTime) AS sessionStart,
       MAX(eventTime) AS sessionEnd
FROM ClickStream
TIMESTAMP BY eventTime
GROUP BY userId, SessionWindow(minute, 5)
```

- `SessionWindow(minute, 5)` means "keep the session open as long as events keep arriving within 5 minutes of each other"
- `MIN(eventTime)` and `MAX(eventTime)` give you the start and end time of each session
- Notice the `FROM` is `ClickStream` — this example uses web clicks instead of sensor data to show that SAQL works with any kind of streaming data

**Use case:** Group user clicks into browsing sessions. A new session starts after 5 minutes of inactivity.

---

### Windowing Functions: Summary

| Window Type | Overlap | Trigger | Best For |
|-------------|---------|---------|----------|
| **Tumbling** | None | Fixed interval | Regular periodic aggregations (e.g., every 5 min) |
| **Hopping** | Yes | Fixed interval | Rolling/sliding averages with overlap |
| **Sliding** | Yes | Event arrival/departure | Detecting bursts or threshold violations |
| **Session** | None | Gap timeout | Grouping related events (e.g., user sessions) |

**How to choose:**
- Need a simple periodic report? → **Tumbling**
- Need a smoothed-out average that updates frequently? → **Hopping**
- Need to detect "too many events in a short time"? → **Sliding**
- Need to group activity separated by periods of silence? → **Session**

---

## SAQL: JOIN with Reference Data

Sometimes your streaming events contain only IDs (like `deviceId: "sensor-042"`), but you want your output to include human-readable names (like `deviceName: "Boiler Room Sensor"`). That extra information lives in a **reference table** — a static or slowly changing dataset.

A JOIN lets you **combine** data from two sources by matching rows on a common column.

```sql
SELECT s.deviceId,
       r.deviceName,
       r.location,
       s.temperature,
       s.eventTime
FROM SensorInput s
JOIN DeviceReference r
  ON s.deviceId = r.deviceId
```

Let's break this down:

| Part | Meaning |
|------|---------|
| `FROM SensorInput s` | The streaming data — `s` is a short alias so we do not have to type `SensorInput` every time |
| `JOIN DeviceReference r` | The reference (lookup) table — `r` is its alias |
| `ON s.deviceId = r.deviceId` | The matching condition — "connect the rows where the device ID is the same" |
| `s.temperature` | Comes from the stream (the live reading) |
| `r.deviceName`, `r.location` | Come from the reference table (static metadata) |

**Result:** Each sensor reading is **enriched** with the device's name and location. Instead of seeing `sensor-042, 76.5°`, you see `Boiler Room Sensor, Building A, 76.5°`.

---

## SAQL: Temporal JOIN (Stream-to-Stream)

What if you have **two separate streams** and want to combine them? For example, temperature readings come from one stream and humidity readings come from another, but they are from the same device.

A **temporal JOIN** matches events from two streams that happen **close together in time**.

```sql
SELECT a.deviceId,
       a.temperature,
       b.humidity,
       a.eventTime
FROM TemperatureStream a
TIMESTAMP BY a.eventTime
JOIN HumidityStream b
TIMESTAMP BY b.eventTime
  ON a.deviceId = b.deviceId
  AND DATEDIFF(second, a, b) BETWEEN 0 AND 10
```

Let's break this down:

| Part | Meaning |
|------|---------|
| `FROM TemperatureStream a` | The first stream (temperature readings) |
| `JOIN HumidityStream b` | The second stream (humidity readings) |
| `ON a.deviceId = b.deviceId` | Match events from the same device |
| `DATEDIFF(second, a, b) BETWEEN 0 AND 10` | Only match if the two events happened within 10 seconds of each other |

**Why the time constraint?** Without it, a temperature reading from Monday could be matched with a humidity reading from Friday, which makes no sense. The `DATEDIFF` clause ensures we only combine readings that are close enough in time to be meaningful.

**Result:** Each output row contains both the temperature and humidity from the same device, captured at roughly the same moment.

---

## ASA Output Destinations

After Stream Analytics processes your data, the results need to go somewhere. ASA can send processed results to multiple destinations at the same time:

| Output | What It Is | Use Case |
|--------|-----------|----------|
| **Azure Blob Storage / Data Lake** | Cloud file storage (like a hard drive in the cloud) | Save processed data for long-term storage or later analysis |
| **Azure SQL Database** | A relational database in the cloud | Store structured results that your app can query with SQL |
| **Power BI** | Microsoft's dashboard and visualization tool | Show live charts and graphs that update in real-time |
| **Azure Cosmos DB** | A NoSQL database designed for very fast reads/writes | Store results that need to be accessed with extremely low latency |
| **Azure Functions** | Small pieces of code that run on-demand (serverless) | Trigger an action like sending an email or SMS when a condition is met |
| **Azure Event Hubs** | The same ingestion service we covered in Week 10 | Feed processed events into another downstream pipeline for further processing |
| **Azure Service Bus** | A message queuing service | Route processed events to message queues for reliable delivery to other services |

**Key point:** You can send the same Stream Analytics job's output to **multiple destinations** at once. For example, send averages to Power BI for a dashboard **and** send alerts to Azure Functions for email notifications — both from the same job.

