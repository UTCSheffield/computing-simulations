"""Streamlit app — HTTP Web-Request OSI Layer Simulation.

Visualises web requests flowing through the seven OSI layers on a client
machine, across two network routers, and up the server's OSI stack, then
the response travelling back.

Run with:
    streamlit run osi_web_simulation/app.py
"""

import os
import sys

# Ensure sibling modules (simulation, layout) are importable regardless of
# the working directory from which Streamlit is launched.
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from vidigi.animation import animate_activity_log

from simulation import run_simulation
from layout import get_event_positions, add_layout_decorations

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="OSI Web-Request Simulation",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 HTTP Web-Request — OSI Layer Simulation")
st.markdown(
    """
    This simulation models an HTTP request leaving a **client browser**, passing
    through the seven [OSI layers](https://en.wikipedia.org/wiki/OSI_model),
    traversing two **network routers**, arriving at a **web server**, and the
    HTTP response travelling back the same path.

    Each 🌐 icon represents one web request/response cycle.
    Use the sidebar to adjust simulation parameters, then press **Run Simulation**.
    """
)

# ---------------------------------------------------------------------------
# Sidebar — simulation controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Simulation Parameters")

    sim_duration = st.slider(
        "Simulation duration (time units)",
        min_value=50, max_value=600, value=250, step=25,
        help="Total length of the simulation run.",
    )
    inter_arrival_time = st.slider(
        "Mean time between requests (time units)",
        min_value=5, max_value=60, value=12, step=1,
        help="Average gap between successive web requests arriving.",
    )
    client_layer_time = st.slider(
        "Client layer processing time",
        min_value=0.2, max_value=4.0, value=1.2, step=0.1,
        help="Mean time a packet spends at each client-side OSI layer.",
    )
    node_layer_time = st.slider(
        "Router layer processing time",
        min_value=0.1, max_value=2.0, value=0.6, step=0.1,
        help="Mean time a packet spends at each network-router OSI layer.",
    )
    server_layer_time = st.slider(
        "Server layer processing time",
        min_value=0.2, max_value=4.0, value=1.2, step=0.1,
        help="Mean time a packet spends at each server-side OSI layer.",
    )
    server_processing_time = st.slider(
        "Server processing time",
        min_value=1.0, max_value=30.0, value=5.0, step=0.5,
        help="Mean time the server takes to generate the HTTP response.",
    )
    jitter = st.slider(
        "Jitter (±random variation)",
        min_value=0.0, max_value=1.0, value=0.3, step=0.05,
        help="Half-width of random delay variation at each stage.",
    )
    random_seed = st.number_input(
        "Random seed", min_value=0, max_value=9999, value=42, step=1,
        help="Seed for reproducibility.",
    )
    every_x_units = st.slider(
        "Animation snapshot interval",
        min_value=1, max_value=10, value=2, step=1,
        help=(
            "Time units between animation frames. "
            "Smaller values give smoother animation but take longer to render."
        ),
    )
    frame_duration = st.slider(
        "Frame duration (ms)",
        min_value=100, max_value=1000, value=300, step=50,
        help="How long each animation frame is displayed.",
    )
    run_btn = st.button("▶ Run Simulation", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Main area — run simulation and render animation
# ---------------------------------------------------------------------------
if run_btn:
    with st.spinner("Running SimPy simulation…"):
        event_log = run_simulation(
            sim_duration=sim_duration,
            inter_arrival_time=inter_arrival_time,
            client_layer_time=client_layer_time,
            node_layer_time=node_layer_time,
            server_layer_time=server_layer_time,
            server_processing_time=server_processing_time,
            jitter=jitter,
            random_seed=int(random_seed),
        )

    if event_log.empty:
        st.warning("No events were generated. Try increasing the simulation duration.")
        st.stop()

    num_requests = event_log["entity_id"].nunique()
    completed = event_log[event_log["event_type"] == "arrival_departure"]
    num_completed = (
        completed[completed["event"] == "depart"]["entity_id"].nunique()
        if "depart" in completed["event"].values
        else 0
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total requests generated", num_requests)
    col2.metric("Simulation duration", f"{sim_duration} units")
    col3.metric("Events logged", len(event_log))

    event_position_df = get_event_positions()

    with st.spinner("Building animation…"):
        fig = animate_activity_log(
            event_log=event_log,
            event_position_df=event_position_df,
            simulation_time_unit="seconds",
            every_x_time_units=every_x_units,
            plotly_height=820,
            plotly_width=1300,
            include_play_button=True,
            display_stage_labels=True,
            entity_icon_size=20,
            text_size=12,
            gap_between_entities=10,
            frame_duration=frame_duration,
            frame_transition_duration=frame_duration,
            override_x_max=1150,
            override_y_max=820,
            wrap_queues_at=5,
            step_snapshot_max=30,
            custom_entity_icon_list=["🌐"],
        )

    fig = add_layout_decorations(fig, event_position_df)

    fig.update_layout(
        title=dict(
            text="HTTP Request → OSI Layers → Routers → Server → Response",
            font=dict(size=16),
            x=0.5,
            xanchor="center",
        ),
        margin=dict(l=120, r=20, t=60, b=80),
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Raw event log (first 100 rows)"):
        st.dataframe(event_log.head(100), use_container_width=True)

else:
    st.info(
        "👈 Adjust the simulation parameters in the sidebar, then click "
        "**▶ Run Simulation** to generate the animation."
    )

    # Show the stage layout for reference
    st.subheader("Stage Layout")
    event_position_df = get_event_positions()
    st.markdown(
        "The table below lists every named stage and its position on the canvas."
    )
    st.dataframe(event_position_df, use_container_width=True)
