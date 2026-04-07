"""Positions and labels for every event stage in the OSI simulation.

Coordinate system used by vidigi / Plotly:
  • x increases to the right
  • y increases upward  (y=0 is bottom of the canvas)

Layout overview (approximate x ranges):
    CLIENT column .............. x =  60 (request ↓)   /  160 (response ↑)
    ROUTER 1 ................... x = 350-410 request   / 300-360 response
    ROUTER 2 ................... x = 560-620 request   / 510-570 response
    SERVER column .............. x = 870 (request ↑)   /  950 (response ↓)

OSI layer y-positions (Application at top, Physical at bottom):
  Application (L7) ........... y = 700
  Presentation (L6) .......... y = 610
  Session (L5) ............... y = 520
  Transport (L4) ............. y = 430
  Network (L3) ............... y = 340
  Data Link (L2) ............. y = 250
  Physical (L1) .............. y = 160
"""

import pandas as pd

# ---------------------------------------------------------------------------
# Y positions for each OSI layer (high = top of screen)
# ---------------------------------------------------------------------------
LAYER_Y = {
    "application": 700,
    "presentation": 610,
    "session": 520,
    "transport": 430,
    "network": 340,
    "data_link": 250,
    "physical": 160,
}

# ---------------------------------------------------------------------------
# X positions for each logical column
# ---------------------------------------------------------------------------
X_CLIENT_REQ = 60       # Client — request going DOWN  (Application→Physical)
X_CLIENT_RESP = 160     # Client — response going UP   (Physical→Application)

X_NODE1_REQ_IN = 350    # Router 1 request enters at physical and goes up
X_NODE1_REQ_OUT = 410   # Router 1 request leaves after going back down
X_NODE1_RESP_IN = 360   # Router 1 response enters at physical and goes up
X_NODE1_RESP_OUT = 300  # Router 1 response leaves after going back down

X_NODE2_REQ_IN = 560    # Router 2 request enters at physical and goes up
X_NODE2_REQ_OUT = 620   # Router 2 request leaves after going back down
X_NODE2_RESP_IN = 570   # Router 2 response enters at physical and goes up
X_NODE2_RESP_OUT = 510  # Router 2 response leaves after going back down

X_SERVER_REQ = 870      # Server — request arriving (Physical→Application)
X_SERVER_RESP = 960     # Server — response leaving (Application→Physical)


def get_event_positions() -> pd.DataFrame:
    """Return a DataFrame with event stage positions and display labels.

    Columns
    -------
    event : str
        Unique event name (must match the names used in ``simulation.py``).
    x : int
        Horizontal position on the canvas.
    y : int
        Vertical position on the canvas (higher = closer to top).
    label : str
        Short human-readable label shown next to the position marker.
    """
    rows = []

    def _add(event, x, y, label):
        rows.append({"event": event, "x": x, "y": y, "label": label})

    # Place lifecycle arrival marker directly at the client application layer.
    _add("arrival", X_CLIENT_REQ, LAYER_Y["application"], "")

    # ------------------------------------------------------------------
    # CLIENT — request going DOWN (Application first, Physical last)
    # ------------------------------------------------------------------
    req_client = [
        ("client_application",  LAYER_Y["application"],  "Application"),
        ("client_presentation", LAYER_Y["presentation"], "Presentation"),
        ("client_session",      LAYER_Y["session"],      "Session"),
        ("client_transport",    LAYER_Y["transport"],    "Transport"),
        ("client_network",      LAYER_Y["network"],      "Network"),
        ("client_data_link",    LAYER_Y["data_link"],    "Data Link"),
        ("client_physical",     LAYER_Y["physical"],     "Physical"),
    ]
    for event, y, label in req_client:
        _add(event, X_CLIENT_REQ, y, label)

    # ------------------------------------------------------------------
    # ROUTER 1 — request direction (Physical → Data Link → Network → Data Link → Physical)
    # ------------------------------------------------------------------
    req_node1 = [
        ("node1_physical_in",   X_NODE1_REQ_IN,  LAYER_Y["physical"],  "Physical"),
        ("node1_data_link_up",  X_NODE1_REQ_IN,  LAYER_Y["data_link"], "Data Link"),
        ("node1_network",       X_NODE1_REQ_IN,  LAYER_Y["network"],   "Network"),
        ("node1_data_link_down", X_NODE1_REQ_OUT, LAYER_Y["data_link"], ""),
        ("node1_physical_out",   X_NODE1_REQ_OUT, LAYER_Y["physical"],  ""),
    ]
    for event, x, y, label in req_node1:
        _add(event, x, y, label)

    # ------------------------------------------------------------------
    # ROUTER 2 — request direction (Physical → Data Link → Network → Data Link → Physical)
    # ------------------------------------------------------------------
    req_node2 = [
        ("node2_physical_in",   X_NODE2_REQ_IN,  LAYER_Y["physical"],  "Physical"),
        ("node2_data_link_up",  X_NODE2_REQ_IN,  LAYER_Y["data_link"], "Data Link"),
        ("node2_network",       X_NODE2_REQ_IN,  LAYER_Y["network"],   "Network"),
        ("node2_data_link_down", X_NODE2_REQ_OUT, LAYER_Y["data_link"], ""),
        ("node2_physical_out",   X_NODE2_REQ_OUT, LAYER_Y["physical"],  ""),
    ]
    for event, x, y, label in req_node2:
        _add(event, x, y, label)

    # ------------------------------------------------------------------
    # SERVER — request arriving UP (Physical first, Application last)
    # ------------------------------------------------------------------
    req_server = [
        ("server_physical",     LAYER_Y["physical"],     "Physical"),
        ("server_data_link",    LAYER_Y["data_link"],    "Data Link"),
        ("server_network",      LAYER_Y["network"],      "Network"),
        ("server_transport",    LAYER_Y["transport"],    "Transport"),
        ("server_session",      LAYER_Y["session"],      "Session"),
        ("server_presentation", LAYER_Y["presentation"], "Presentation"),
        ("server_application",  LAYER_Y["application"],  "Application"),
    ]
    for event, y, label in req_server:
        _add(event, X_SERVER_REQ, y, label)

    # ------------------------------------------------------------------
    # SERVER — response leaving DOWN (Application first, Physical last)
    # ------------------------------------------------------------------
    resp_server = [
        ("server_resp_application",  LAYER_Y["application"],  ""),
        ("server_resp_presentation", LAYER_Y["presentation"], ""),
        ("server_resp_session",      LAYER_Y["session"],      ""),
        ("server_resp_transport",    LAYER_Y["transport"],    ""),
        ("server_resp_network",      LAYER_Y["network"],      ""),
        ("server_resp_data_link",    LAYER_Y["data_link"],    ""),
        ("server_resp_physical",     LAYER_Y["physical"],     ""),
    ]
    for event, y, label in resp_server:
        _add(event, X_SERVER_RESP, y, label)

    # ------------------------------------------------------------------
    # ROUTER 2 — response direction (Physical → Data Link → Network → Data Link → Physical)
    # ------------------------------------------------------------------
    resp_node2 = [
        ("node2_resp_physical_in",   X_NODE2_RESP_IN,  LAYER_Y["physical"],  ""),
        ("node2_resp_data_link_up",  X_NODE2_RESP_IN,  LAYER_Y["data_link"], ""),
        ("node2_resp_network",       X_NODE2_RESP_IN,  LAYER_Y["network"],   ""),
        ("node2_resp_data_link_down", X_NODE2_RESP_OUT, LAYER_Y["data_link"], ""),
        ("node2_resp_physical_out",   X_NODE2_RESP_OUT, LAYER_Y["physical"],  ""),
    ]
    for event, x, y, label in resp_node2:
        _add(event, x, y, label)

    # ------------------------------------------------------------------
    # ROUTER 1 — response direction (Physical → Data Link → Network → Data Link → Physical)
    # ------------------------------------------------------------------
    resp_node1 = [
        ("node1_resp_physical_in",   X_NODE1_RESP_IN,  LAYER_Y["physical"],  ""),
        ("node1_resp_data_link_up",  X_NODE1_RESP_IN,  LAYER_Y["data_link"], ""),
        ("node1_resp_network",       X_NODE1_RESP_IN,  LAYER_Y["network"],   ""),
        ("node1_resp_data_link_down", X_NODE1_RESP_OUT, LAYER_Y["data_link"], ""),
        ("node1_resp_physical_out",   X_NODE1_RESP_OUT, LAYER_Y["physical"],  ""),
    ]
    for event, x, y, label in resp_node1:
        _add(event, x, y, label)

    # ------------------------------------------------------------------
    # CLIENT — response arriving UP (Physical first, Application last)
    # ------------------------------------------------------------------
    resp_client = [
        ("client_resp_physical",     LAYER_Y["physical"],     ""),
        ("client_resp_data_link",    LAYER_Y["data_link"],    ""),
        ("client_resp_network",      LAYER_Y["network"],      ""),
        ("client_resp_transport",    LAYER_Y["transport"],    ""),
        ("client_resp_session",      LAYER_Y["session"],      ""),
        ("client_resp_presentation", LAYER_Y["presentation"], ""),
        ("client_resp_application",  LAYER_Y["application"],  ""),
    ]
    for event, y, label in resp_client:
        _add(event, X_CLIENT_RESP, y, label)

    return pd.DataFrame(rows)


def add_layout_decorations(fig, event_position_df: pd.DataFrame):
    """Add background shapes and annotations to a Plotly figure.

    Draws column boxes (CLIENT, ROUTER 1, ROUTER 2, SERVER) and horizontal
    OSI-layer bands to provide visual context for the animation.

    Parameters
    ----------
    fig : plotly.graph_objs.Figure
        Animated Plotly figure returned by ``animate_activity_log``.
    event_position_df : pd.DataFrame
        The same positions DataFrame passed to ``animate_activity_log``.

    Returns
    -------
    plotly.graph_objs.Figure
        The modified figure (edited in-place and returned).
    """
    pad_x = 20
    pad_y = 25

    def _box(x0, x1, y0, y1, color, name):
        fig.add_shape(
            type="rect",
            x0=x0 - pad_x, x1=x1 + pad_x,
            y0=y0 - pad_y, y1=y1 + pad_y,
            line=dict(color=color, width=3),
            fillcolor=color,
            opacity=0.14,
            layer="below",
        )
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=y1 + pad_y + 18,
            text=f"<b>{name}</b>",
            showarrow=False,
            font=dict(size=15, color=color),
        )

    # ---- Device boxes ----
    _box(X_CLIENT_REQ, X_CLIENT_RESP, LAYER_Y["physical"], LAYER_Y["application"],
         "#1f77b4", "CLIENT")
    
    # ---- User icon above client application ----
    fig.add_annotation(
        x=(X_CLIENT_REQ + X_CLIENT_RESP) / 2,
        y=LAYER_Y["application"] + 85,
        text="👤",
        showarrow=False,
        font=dict(size=28),
    )
    fig.add_annotation(
        x=(X_CLIENT_REQ + X_CLIENT_RESP) / 2,
        y=LAYER_Y["application"] + 55,
        text="<b>User</b>",
        showarrow=False,
        font=dict(size=12, color="#1f77b4"),
        xanchor="center",
    )

    _box(X_NODE1_RESP_OUT, X_NODE1_REQ_OUT, LAYER_Y["physical"], LAYER_Y["network"],
         "#ff7f0e", "ROUTER 1")
    _box(X_NODE2_RESP_OUT, X_NODE2_REQ_OUT, LAYER_Y["physical"], LAYER_Y["network"],
         "#ff7f0e", "ROUTER 2")
    _box(X_SERVER_REQ, X_SERVER_RESP, LAYER_Y["physical"], LAYER_Y["application"],
         "#2ca02c", "SERVER")

    # ---- OSI layer horizontal bands (light stripes across the full plot) ----
    x_left = event_position_df["x"].min() - 30
    x_right = event_position_df["x"].max() + 80  # room for labels

    layer_colors = {
        "application":  "rgba(255, 200, 100, 0.07)",
        "presentation": "rgba(200, 160, 240, 0.07)",
        "session":      "rgba(240, 180, 190, 0.07)",
        "transport":    "rgba(160, 220, 180, 0.07)",
        "network":      "rgba(140, 210, 230, 0.07)",
        "data_link":    "rgba(240, 210, 140, 0.07)",
        "physical":     "rgba(200, 180, 160, 0.07)",
    }
    layer_labels = {
        "application":  "L7 Application",
        "presentation": "L6 Presentation",
        "session":      "L5 Session",
        "transport":    "L4 Transport",
        "network":      "L3 Network",
        "data_link":    "L2 Data Link",
        "physical":     "L1 Physical",
    }
    half_band = 38
    for layer, y_center in LAYER_Y.items():
        fig.add_shape(
            type="rect",
            x0=x_left, x1=x_right,
            y0=y_center - half_band, y1=y_center + half_band,
            line=dict(width=0),
            fillcolor=layer_colors[layer],
            layer="below",
        )
        # Left-side OSI label
        fig.add_annotation(
            x=x_left - 5,
            y=y_center,
            text=layer_labels[layer],
            showarrow=False,
            xanchor="right",
            font=dict(size=10, color="#555555"),
        )

    # ---- Static stage labels ----
    labeled_positions = (
        event_position_df[event_position_df["label"] != ""]
        .drop_duplicates(subset=["x", "y", "label"])
        .sort_values(["x", "y"])
    )
    for row in labeled_positions.itertuples(index=False):
        if row.x <= X_CLIENT_RESP:
            xshift = 14
            xanchor = "left"
        elif row.x >= X_SERVER_REQ:
            xshift = 14
            xanchor = "left"
        else:
            xshift = 12
            xanchor = "left"

        fig.add_annotation(
            x=row.x,
            y=row.y,
            text=row.label,
            showarrow=False,
            xshift=xshift,
            xanchor=xanchor,
            font=dict(size=11, color="#333333"),
            bgcolor="rgba(255,255,255,0.72)",
            borderpad=1,
        )

    # ---- Direction arrows between columns (using data coordinates) ----
    arrow_y_req = LAYER_Y["physical"] + 16
    arrow_y_resp = LAYER_Y["physical"] - 16

    # Request arrows (→)
    for x_start, x_end in [
        (X_CLIENT_REQ + pad_x + 5,      X_NODE1_REQ_IN - pad_x - 5),
        (X_NODE1_REQ_OUT + pad_x + 5,   X_NODE2_REQ_IN - pad_x - 5),
        (X_NODE2_REQ_OUT + pad_x + 5,   X_SERVER_REQ - pad_x - 5),
    ]:
        fig.add_annotation(
            x=x_end, y=arrow_y_req,
            ax=x_start, ay=arrow_y_req,
            axref="x", ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.2,
            arrowwidth=1.8,
            arrowcolor="#4477bb",
        )

    # Response arrows (←)
    for x_start, x_end in [
        (X_SERVER_RESP - pad_x - 5,      X_NODE2_RESP_IN + pad_x + 5),
        (X_NODE2_RESP_OUT - pad_x - 5,   X_NODE1_RESP_IN + pad_x + 5),
        (X_NODE1_RESP_OUT - pad_x - 5,   X_CLIENT_RESP + pad_x + 5),
    ]:
        fig.add_annotation(
            x=x_end, y=arrow_y_resp,
            ax=x_start, ay=arrow_y_resp,
            axref="x", ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.2,
            arrowwidth=1.8,
            arrowcolor="#cc4444",
        )

    # ---- Legend for arrow colours ----
    legend_x = (X_CLIENT_REQ + X_SERVER_RESP) / 2
    legend_y = LAYER_Y["physical"] - 105
    fig.add_annotation(
        x=legend_x,
        y=legend_y,
        text=(
            '<span style="color:#4477bb;font-weight:bold">── HTTP Request →</span>'
            '&nbsp;&nbsp;&nbsp;'
            '<span style="color:#cc4444;font-weight:bold">← HTTP Response ──</span>'
        ),
        showarrow=False,
        font=dict(size=12),
        align="center",
    )

    return fig
