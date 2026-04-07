# computing-simulations
computing-simulations using simpy, vidigi and streamlit

## OSI Web-Request Simulation

A visual simulation of HTTP web requests flowing through the seven OSI layers — from a client browser, through two network routers, to a web server — and the response returning along the same path.

### Features

- **SimPy** discrete-event simulation of HTTP request/response cycles
- **Vidigi** animated visualisation showing 🌐 icons moving through OSI layers
- **Streamlit** interactive UI with configurable simulation parameters
- Client OSI stack on the left, two routers in the middle, server OSI stack on the right
- Both the HTTP request (→) and response (←) journeys are animated

### Running the App

```bash
pip install -r requirements.txt
streamlit run osi_web_simulation/app.py
```

### Project Structure

```
osi_web_simulation/
  simulation.py   — SimPy simulation (request/response OSI layer processing)
  layout.py       — Canvas positions and visual decorations for each stage
  app.py          — Streamlit application
requirements.txt
```

### OSI Layer Journey

| Direction | Path |
|-----------|------|
| **Request (→)** | Client (App→Physical) → Router 1 → Router 2 → Server (Physical→App) |
| **Response (←)** | Server (App→Physical) → Router 2 → Router 1 → Client (Physical→App) |
