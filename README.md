# FloodAid 🌊

AI-powered flood risk intelligence and emergency response coordination for communities across the United States.

## Overview

FloodAid is a hackathon-built multi-agent flood prediction and response platform that combines real-time hydrological data, weather forecasting, and spatial reasoning to assess flood risk and recommend safer evacuation routes and nearby emergency resources.

The system ingests live environmental signals from public government APIs and transforms them into actionable flood intelligence.

FloodAid was built as part of the 2026 BeaverHacks hackathon.

## Why FloodAid?

Flooding is one of the most common and costly natural disasters in the United States.

Existing public data sources provide critical environmental information, but the data is fragmented across multiple systems and difficult to operationalize in real time.

FloodAid bridges that gap by combining:

* Real-time USGS stream gauge data
* NOAA weather forecasts and alerts
* Spatial gauge proximity analysis
* Flood risk scoring
* Emergency route intelligence

## Features

### Real-Time Hydrology Monitoring

Pulls live streamflow and water level data from USGS gauge stations nationwide.

### Weather Intelligence

Integrates NOAA weather forecasts and active weather alerts.

### Flood Risk Prediction

Computes environmental risk states using:

* Streamflow percentile ranking
* Water level trend analysis
* Rainfall forecast severity
* Alert conditions

### Spatial Gauge Network

Maps locations to nearest hydrological monitoring stations across the US.

### Emergency Decision Support

Provides:

* Safer evacuation route recommendations
* Nearby emergency shelters/resources
* Risk-aware route prioritization

### Multi-Agent Architecture

FloodAid is structured as cooperating agents for:

* Hydrology analysis
* Weather analysis
* Feature engineering
* Risk fusion
* Routing intelligence

---

## Architecture

```text
User Location
    ↓
Spatial Gauge Resolution
    ↓
USGS Hydrology Agent
    ↓
NOAA Weather Agent
    ↓
Feature Engineering Agent
    ↓
Flood Risk Fusion Agent
    ↓
Emergency Routing + Resource Recommendation
```

---

## Tech Stack

### Backend

* Python
* NVIDIA Nemotron for Chatbot


### Frontend

* Flutter

### Data Sources

* USGS Water Services API
* NOAA weather.gov API



### System Design

* Multi-agent service orchestration

---

## Project Structure

TBD

```text
FloodAid/
├── backend/
│   └── services/
│       ├── food_service.py
│       ├── hospital_service.py
│       ├── shelter_service.py
│       ├── usgs_service.py
│       └── weather_service.py
│   └── agents/
│       ├── chat.py
│       ├── emergency_resource_agent.py
│       └── risk_region_agent.py
│
├── frontend/
│   └── floodaid/
│   └── flutter/
├── main.py
└── README.md
```

---

## Getting Started

### Clone

```bash
git clone https://github.com/Jeeya7/FloodAid.git
cd FloodAid
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Install Flutter

```bash
# TODO
```

### Run

```bash
# TODO
```

---

## Example Output

```json
{
  "rain_forecast_inches": 2.4,
  "water_level_status": "high",
  "streamflow_status": "above_normal",
  "weather_alert": "flood_watch",
  "water_level_trend": "rising"
}
```

<!-- ---

## Hackathon Vision

FloodAid aims to make flood intelligence accessible, interpretable, and actionable for both emergency responders and local communities.

Our long-term vision includes:

* National flood coverage
* Predictive watershed modeling
* Real-time alert subscriptions
* Community emergency coordination

---

## Future Work

* Watershed graph modeling
* ML-based flood forecasting
* Persistent geospatial indexing
* Distributed event processing
* Interactive emergency response dashboard

--- -->

## Team


---
<!-- 
## License

MIT -->
