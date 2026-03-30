# CST8916 – Assignment 2

## Real-time Stream Analytics Pipeline

### 👤 Student Information

Name: Sara Mirzaei
Course: CST8916 – Remote Data and Real-time Applications
Semester: Winter 2026

---

# 📌 Overview

This project extends the Week 10 lab by building a **real-time clickstream analytics pipeline** using Azure services.

The system captures user interactions from a demo e-commerce store, enriches them with device metadata, processes them using Azure Stream Analytics, and displays insights on a live dashboard.

---

# 🏗️ Architecture

### Data Flow

```
Browser (client.html)
        ↓
Flask App (App Service)
        ↓
Azure Event Hubs
        ↓
Azure Stream Analytics
        ↓
Azure Blob Storage
   ↓             ↓
Device Output   Spike Output
        ↓
Flask API (/api/devices, /api/spikes)
        ↓
Dashboard (dashboard.html)
```

---

# ⚙️ Features Implemented

## ✅ Part 1 – Event Enrichment

Each event sent to Event Hubs includes:

| Field      | Description                             |
| ---------- | --------------------------------------- |
| deviceType | desktop / mobile / tablet               |
| browser    | Chrome / Firefox / Safari               |
| os         | Windows / macOS / Linux / Android / iOS |

### Implementation

* Enrichment is done in `client.html`
* Uses `navigator.userAgent` to extract device info
* Sent via `/track` endpoint to Flask backend

---

## ✅ Part 2 – Stream Analytics + Dashboard

### 🔹 Query 1 – Device Type Breakdown

```sql
SELECT
    deviceType,
    COUNT(*) AS event_count,
    System.Timestamp AS window_end
INTO analytics-output
FROM clickstream-input
TIMESTAMP BY timestamp
GROUP BY
    deviceType,
    TumblingWindow(second, 10)
```

👉 Shows which device types generate the most traffic.

---

### 🔹 Query 2 – Traffic Spike Detection

```sql
SELECT
    COUNT(*) AS total_events,
    System.Timestamp AS window_end
INTO spikeoutput
FROM clickstream-input
TIMESTAMP BY timestamp
GROUP BY
    TumblingWindow(second, 10)
HAVING COUNT(*) > 20
```

👉 Detects bursts of activity in the stream.

---

## 📊 Dashboard Features

The dashboard displays:

* ✅ Total events
* ✅ Event type breakdown
* ✅ Live event feed
* ✅ Device type activity (Stream Analytics)
* ✅ Traffic spike alerts

---

# 🧠 Design Decisions

### 1. Client-side Enrichment

* Device info captured in browser
* Reduces backend complexity
* Ensures data is available before reaching Event Hubs

---

### 2. Azure Stream Analytics

* Used for real-time aggregation
* Tumbling windows (10 seconds) provide near real-time insights

---

### 3. Blob Storage Output

* Stores processed results
* Easy integration with Flask backend
* Cost-effective and simple to query

---

### 4. Flask API Layer

Custom endpoints created:

* `/api/devices` → reads device analytics
* `/api/spikes` → reads spike data

---

# 🚀 Setup Instructions

## 1. Prerequisites

* Azure account
* Python 3.10
* Azure Event Hubs
* Azure Stream Analytics
* Azure Storage Account

---

## 2. Environment Variables

Set in Azure App Service:

```
EVENT_HUB_CONNECTION_STR=your_connection_string
EVENT_HUB_NAME=clickstream
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection
```

---

## 3. Install Dependencies

```
pip install -r requirements.txt
```

---

## 4. Run Locally

```
python app.py
```

---

## 5. Deploy to Azure

* Use GitHub Actions or ZIP deploy
* Ensure:

  * Python version = 3.10
  * Startup command:

```
gunicorn app:app
```

---

# 🎥 Video Demo

🔗 YouTube Link: *(Add your unlisted video here)*

The demo includes:

1. Running app on Azure
2. Generating click events
3. Showing enriched events in Event Hubs
4. Stream Analytics queries
5. Live dashboard updates

---

# 📂 Repository

🔗 GitHub Repo: *(Add your repo link here)*

⚠️ Repository is private and collaborator access is provided.

---

# ⚠️ Important Notes

* All Azure resources will be deleted after demo to avoid charges.
* AI tools were used for guidance, but all code was reviewed and understood.

---

# ✅ Conclusion

This project successfully demonstrates a complete real-time analytics pipeline using Azure services, providing meaningful insights from clickstream data and visualizing them in a live dashboard.

---
