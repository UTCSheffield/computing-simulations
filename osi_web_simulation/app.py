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
    This simulation models traffic through the seven
    [OSI layers](https://en.wikipedia.org/wiki/OSI_model).
    The model performs **one DNS lookup** (`bbc.co.uk/` → `151.101.128.81`),
    then requests `index.html` from `151.101.128.81:80/`.

    As `index.html` packets arrive at **client application layer**, they trigger
    additional requests:
    - packet 2 → `style.css`
    - packet 3 → `logo.png`
    - packet 4 → `hero.png`

    The server response is deterministic and packetized at L4 (1 packet = 1KB):
    - `index.html` = 5 packets
    - `style.css` = 5 packets
    - `logo.png` = 10 packets
    - `hero.png` = 10 packets

    - 📧 **DNS query / response** — Client → Router 1 → DNS Server → Router 1 → Client
    - 🌐 **HTTP request / response** — Client → Router 1 → Router 2 → Web Server → Router 2 → Router 1 → Client

    Use the sidebar to adjust simulation parameters, then press **Run Simulation**.
    """
)

# ---------------------------------------------------------------------------
# Sidebar — simulation controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Simulation Parameters")

    client_layer_time = st.slider(
        "Client layer processing time (ms)",
        min_value=1, max_value=10, value=1, step=1,
        help="Mean time a packet spends at each client-side OSI layer.",
    )
    node_layer_time = st.slider(
        "Router layer processing time (ms)",
        min_value=1, max_value=10, value=1, step=1,
        help="Mean time a packet spends at each network-router OSI layer.",
    )
    server_layer_time = st.slider(
        "Server layer processing time (ms)",
        min_value=1, max_value=10, value=1, step=1,
        help="Mean time a packet spends at each server-side OSI layer.",
    )
    server_processing_time = st.slider(
        "Server processing time (ms)",
        min_value=1, max_value=100, value=5, step=1,
        help="Mean time the server takes to generate the HTTP response.",
    )
    dns_processing_time = st.slider(
        "DNS lookup time (ms)",
        min_value=1, max_value=20, value=2, step=1,
        help="Mean time the DNS server takes to resolve the hostname.",
    )
    playback_mode = st.selectbox(
        "Playback speed",
        options=[
            "1000 ms per frame (slow)",
            "500 ms per frame (default)",
            "250 ms per frame (fast)",
            "100 ms per frame (very fast)",
        ],
        index=1,
        help="Fixed frame duration for the animation. All options keep 1 ms snapshots.",
    )
    run_btn = st.button("▶ Run Simulation", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Main area — run simulation and render animation
# ---------------------------------------------------------------------------
if run_btn:
    with st.spinner("Running SimPy simulation…"):
        event_log = run_simulation(
            client_layer_time=client_layer_time,
            node_layer_time=node_layer_time,
            server_layer_time=server_layer_time,
            server_processing_time=server_processing_time,
            dns_processing_time=dns_processing_time,
        )

    if event_log.empty:
        st.warning("No events were generated. Try increasing the simulation duration.")
        st.stop()

    num_entities = event_log["entity_id"].nunique()
    num_http_requests = event_log[event_log["entity_id"] != 1]["entity_id"].nunique()
    num_dns = 1 if (event_log["entity_id"] == 1).any() else 0
    completed = event_log[event_log["event_type"] == "arrival_departure"]
    num_completed = (
        completed[completed["event"] == "depart"]["entity_id"].nunique()
        if "depart" in completed["event"].values
        else 0
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total entities generated", num_entities)
    col2.metric("Completion time", f"{event_log['time'].max():.0f} ms")
    col3.metric("Events logged", len(event_log))

    st.caption(
        f"Deterministic rules: DNS lookups={num_dns} (startup only), "
        f"HTTP requests={num_http_requests}, packets delivered=30 (1KB each)"
    )

    event_position_df = get_event_positions()

    # Always capture every simulation step (1 ms snapshots).
    every_x_units = 1

    # Playback timing uses explicit fixed frame-duration presets.
    frame_duration_map = {
        "1000 ms per frame (slow)": 1000,
        "500 ms per frame (default)": 500,
        "250 ms per frame (fast)": 250,
        "100 ms per frame (very fast)": 100,
    }
    frame_duration = frame_duration_map[playback_mode]
    
    with st.spinner("Building animation…"):
        fig = animate_activity_log(
            event_log=event_log,
            event_position_df=event_position_df,
            simulation_time_unit="milliseconds",
            every_x_time_units=every_x_units,
            plotly_height=820,
            plotly_width=1300,
            include_play_button=True,
            display_stage_labels=False,
            entity_icon_size=20,
            text_size=12,
            gap_between_entities=10,
            frame_duration=frame_duration,
            frame_transition_duration=0,
            override_x_max=1200,
            override_y_max=820,
            wrap_queues_at=5,
            step_snapshot_max=30,
            custom_entity_icon_list=["📧", "🌐"],
        )

    # --- Fix fly-in animation artefact ---
    # Vidigi uses px.scatter with a single trace per frame and .ids for
    # animation_group tracking. When an entity_id appears for the first
    # time, Plotly's JS animates it from (0, 0) to its real position.
    # Fix: pre-populate every pre-arrival frame with a phantom point at
    # the entity's first real position but with empty text (invisible),
    # so Plotly never encounters a "brand new" animation_group mid-run.
    entity_first: dict = {}  # entity_id -> {x, y, cdata}
    for frame in fig.frames:
        t = frame.data[0]
        if t.ids is None:
            continue
        for i, eid in enumerate(t.ids):
            eid = int(eid)
            if eid not in entity_first:
                entity_first[eid] = {
                    "x": float(t.x[i]),
                    "y": float(t.y[i]),
                    "cdata": list(t.customdata[i]) if t.customdata is not None else [],
                }

    def _add_phantoms(trace):
        present = set(int(e) for e in trace.ids) if trace.ids is not None else set()
        absent = set(entity_first.keys()) - present
        if not absent:
            return
        xs = list(trace.x)
        ys = list(trace.y)
        texts = list(trace.text) if trace.text is not None else []
        ids = list(trace.ids) if trace.ids is not None else []
        cdata = [list(c) for c in trace.customdata] if trace.customdata is not None else []
        for eid in sorted(absent):
            ef = entity_first[eid]
            xs.append(ef["x"])
            ys.append(ef["y"])
            texts.append("")
            ids.append(eid)
            cdata.append(list(ef["cdata"]))
        trace.x = tuple(xs)
        trace.y = tuple(ys)
        trace.text = tuple(texts)
        trace.ids = tuple(ids)
        if cdata:
            trace.customdata = tuple(tuple(c) for c in cdata)

    _add_phantoms(fig.data[0])
    for frame in fig.frames:
        _add_phantoms(frame.data[0])

    # --- Show per-entity state labels beside icons ---
    # Build a time-ordered label history for each entity.
    label_history = (
        event_log[event_log["state_label"].notna() & (event_log["state_label"] != "")]
        .sort_values(["entity_id", "time"])
        [["entity_id", "time", "state_label"]]
    )
    entity_labels = {}
    for row in label_history.itertuples(index=False):
        eid = int(row.entity_id)
        entity_labels.setdefault(eid, []).append((float(row.time), str(row.state_label)))

    def _label_at_time(entity_id: int, frame_time: float) -> str:
        history = entity_labels.get(entity_id, [])
        latest = ""
        for t, lbl in history:
            if t <= frame_time:
                latest = lbl
            else:
                break
        return latest

    def _apply_state_text(trace, frame_time: float):
        if trace.ids is None or trace.text is None:
            return
        label_font_size_px = 11
        new_text = []
        for eid_raw, base_text in zip(trace.ids, trace.text):
            base_text = str(base_text) if base_text is not None else ""
            if base_text == "":
                # Keep phantom points invisible.
                new_text.append("")
                continue
            eid = int(eid_raw)
            state = _label_at_time(eid, frame_time)
            if state:
                new_text.append(
                    f"{base_text} <span style='font-size:{label_font_size_px}px'>{state}</span>"
                )
            else:
                new_text.append(base_text)
        trace.text = tuple(new_text)

    initial_time = float(fig.frames[0].name) if fig.frames else 0.0
    _apply_state_text(fig.data[0], initial_time)
    for frame in fig.frames:
        try:
            frame_time = float(frame.name)
        except (TypeError, ValueError):
            frame_time = initial_time
        _apply_state_text(frame.data[0], frame_time)

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

    # --- Display file completion and page render milestones ---
    milestones = event_log[event_log["entity_id"] == 0].copy()
    if not milestones.empty:
        st.subheader("📍 Page Load Milestones")
        st.markdown("These events mark when files finish loading at the client application and when the page is fully rendered:")
        milestone_display = milestones[["time", "event", "state_label"]].copy()
        milestone_display.columns = ["Time (ms)", "Event Type", "Status"]
        st.dataframe(milestone_display, use_container_width=True)

    with st.expander("🧾 Request / Response Rules and Entity Summary", expanded=True):
        st.markdown(
            """
            **Generation rules (deterministic):**
            - Exactly one DNS request/response pair is generated.
                        - `index.html` is requested after DNS resolution.
                        - `style.css`, `logo.png`, and `hero.png` requests are triggered by
                            index packets 2, 3, and 4 arriving at client application.
            - Server L7→L5 runs as a separate response-builder process.
            - L4 packetization uses 1 packet/tick and 1 packet = 1KB.
            - Client L4 only releases packets in sequence order.

            **Response rules:**
            - Each DNS request has one DNS response.
            - HTTP response files are fixed: index(5), css(5), logo(10), hero(10).
            """
        )

        lifecycle = event_log[event_log["event_type"] == "arrival_departure"].copy()
        arrivals = (
            lifecycle[lifecycle["event"] == "arrival"][["entity_id", "time"]]
            .rename(columns={"time": "start_ms"})
        )
        departs = (
            lifecycle[lifecycle["event"] == "depart"][["entity_id", "time"]]
            .rename(columns={"time": "finish_ms"})
        )
        summary_df = arrivals.merge(departs, on="entity_id", how="left")
        summary_df["type"] = summary_df["entity_id"].apply(
            lambda eid: "DNS" if int(eid) == 1 else "HTTP"
        )
        summary_df["duration_ms"] = summary_df["finish_ms"] - summary_df["start_ms"]
        summary_df["response_rule"] = summary_df["type"].apply(
            lambda t: "1 DNS response" if t == "DNS" else "1 HTTP response"
        )
        summary_df = summary_df[
            ["entity_id", "type", "start_ms", "finish_ms", "duration_ms", "response_rule"]
        ].sort_values("entity_id")
        st.dataframe(summary_df, use_container_width=True)

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
