# Predictive Logistics Control Tower (PLCT)

PLCT is a demo-ready AI logistics system that simulates live truck movement, predicts delivery delays, scores multiple route options, and auto-reroutes trucks when delay risk becomes too high.

## 1. Project Architecture

System flow:

`Truck Simulator -> FastAPI Backend -> Prediction Engine -> Routing Engine -> Decision Engine -> Streamlit Dashboard`

## 2. Folder Structure

```text
plct/
├── app/
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   └── database.py
│   ├── models/
│   │   └── schemas.py
│   ├── services/
│   │   ├── control_tower.py
│   │   ├── decision.py
│   │   ├── ors_client.py
│   │   ├── prediction.py
│   │   ├── routing.py
│   │   └── simulator.py
│   ├── main.py
│   └── utils.py
├── dashboard/
│   └── streamlit_app.py
├── data/
├── models/
├── .env.example
├── README.md
└── requirements.txt
```

## 3. Module Explanation

### `app/main.py`
Starts the FastAPI application and loads the control tower service when the backend boots.

### `app/api/routes.py`
Exposes API endpoints for health checks, reading dashboard state, advancing the simulation, and resetting the demo.

### `app/services/simulator.py`
Creates simulated truck movement and fake GPS updates so the system feels live during a demo.

### `app/services/prediction.py`
Contains two prediction styles:
- A simple rule-based delay predictor
- An ML-based predictor trained on synthetic data using scikit-learn

### `app/services/routing.py`
Builds route options and applies the route score formula:

`Score = w1(Time) + w2(Traffic) + w3(Cost) + w4(Risk)`

The route with the lowest score is treated as the best path.

### `app/services/decision.py`
Checks whether the truck should continue, be monitored, or be rerouted.

### `app/services/ors_client.py`
Shows how to integrate OpenRouteService. If the API key is missing, PLCT automatically falls back to simulated route options.

### `app/db/database.py`
Stores telemetry snapshots and alerts in SQLite so the system behaves more like a real product.

### `dashboard/streamlit_app.py`
Displays the live map, truck positions, route comparisons, KPIs, and alerts.

## 4. Core Logic

PLCT uses four route dimensions:

- Time
- Traffic
- Cost
- Risk

Delay prediction uses:

- Remaining distance
- Average speed
- Traffic intensity
- Route risk
- Time pressure

Decision rule:

- If `Delay Risk > Threshold`, reroute to the best available route

## 5. OpenRouteService Integration

1. Create a free API key from [OpenRouteService](https://openrouteservice.org/).
2. Copy `.env.example` to `.env`.
3. Add your API key:

```env
ORS_API_KEY=your_key_here
```

4. Run the app. The routing engine will try ORS first and fall back to demo routes if needed.

The API integration lives in [app/services/ors_client.py](/Users/pragathiprakash/Desktop/plct/app/services/ors_client.py).

## 6. Setup Instructions

### Step 1: Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Python `3.12` to `3.14` is a good range for this project. If you use Python `3.14`, keep the dependency versions from this repo because older pandas / SciPy / scikit-learn wheels may try to build from source on Apple Silicon.

### Step 2: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure environment variables

```bash
cp .env.example .env
```

You can keep the demo running without an ORS key, but the real route API needs it.

### Step 4: Start the FastAPI backend

```bash
uvicorn app.main:app --reload
```

Backend docs will be available at:

- [http://localhost:8000/docs](http://localhost:8000/docs)

### Step 5: Start the Streamlit dashboard

Open a new terminal:

```bash
streamlit run dashboard/streamlit_app.py
```

Dashboard URL:

- [http://localhost:8501](http://localhost:8501)

## 7. Demo Flow for Presentation

1. Show the live map with moving trucks.
2. Explain that each truck sends simulated GPS coordinates to the backend.
3. Show the prediction engine calculating delay risk and ETA.
4. Open route comparison and explain the weighted route scoring logic.
5. Highlight alerts where the decision engine recommends rerouting.
6. Explain that SQLite stores telemetry and alert history for analytics.

## 8. Hackathon-Level Innovation Ideas

### Add GenAI control tower assistant
Use an LLM assistant that explains *why* a truck was rerouted in natural language for operations teams.

### Add weather and strike risk feeds
Pull live weather, protests, or geopolitical disruption data into the risk score.

### Add customer SLA prioritization
Give high-priority shipments a stronger weight on time, while low-priority ones optimize cost.

### Add carbon-aware routing
Include fuel burn and carbon emissions in the route score to support green logistics.

### Add anomaly detection
Detect unusual truck stops, route deviations, or speed drops and flag them automatically.

## 9. Final Integration Summary

- FastAPI serves the backend APIs
- Streamlit acts as the control tower dashboard
- SQLite stores telemetry and alerts
- OpenRouteService provides real alternative routes when configured
- The simulator makes the project feel live even without hardware or IoT devices

This structure is designed to stay beginner-friendly while still looking like a real-world intelligent logistics system.
