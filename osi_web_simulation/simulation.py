"""SimPy simulation of HTTP web sessions flowing through OSI layers.

Each user session generates two sequenced entities:

    1. DNS query (📧) — resolves the web-server hostname to an IP address:
             Client (Application → Physical)
             → Router 1 (Physical → Network → Physical)
             → DNS Server (Physical → Application → Physical)
             → Router 1 (Physical → Network → Physical)
             → Client (Physical → Application)

    2. HTTP request (🌐) — only dispatched after the DNS response arrives:
             Client (Application → Physical)
             → Router 1 (Physical → Network → Physical)
             → Router 2 (Physical → Network → Physical)
             → Web Server (Physical → Application → Physical)
             → Router 2 (Physical → Network → Physical)
             → Router 1 (Physical → Network → Physical)
             → Client (Physical → Application)

Entity IDs are assigned so icon cycling remains stable:
    DNS uses entity_id=1 (icon index 0, e.g. 📧)
    HTTP entities use even IDs only (2, 4, 6, ...) so they stay 🌐.
"""

import simpy
from vidigi.logging import EventLogger

DNS_QUERY_DOMAIN = "bbc.co.uk/"
DNS_RESOLVED_IP = "151.101.128.81"

INDEX_HTML_FRAGMENTS = [
    "<html><head>",
    '<link rel="stylesheet" href="style.css">',
    "</head><body><h1>Heading</h1>",
    '<img src="logo.png">',
    '<img src="hero.png"></body></html>',
]

# ---------------------------------------------------------------------------
# Stage name lists — each string is a unique event name logged for vidigi
# ---------------------------------------------------------------------------

CLIENT_REQUEST_STAGES = [
    "client_application",
    "client_presentation",
    "client_session",
    "client_transport",
    "client_network",
    "client_data_link",
    "client_physical",
]

NODE1_REQUEST_STAGES = [
    "node1_physical_in",
    "node1_data_link_up",
    "node1_network",
    "node1_data_link_down",
    "node1_physical_out",
]

# ---- DNS Server (only DNS entities visit this) ----
DNS_REQUEST_STAGES = [
    "dns_physical",
    "dns_data_link",
    "dns_network",
    "dns_transport",
    "dns_session",
    "dns_presentation",
    "dns_application",
]

DNS_RESPONSE_STAGES = [
    "dns_resp_application",
    "dns_resp_presentation",
    "dns_resp_session",
    "dns_resp_transport",
    "dns_resp_network",
    "dns_resp_data_link",
    "dns_resp_physical",
]

# ---- HTTP path (Router 2 + Web Server — only HTTP entities visit) ----
NODE2_REQUEST_STAGES = [
    "node2_physical_in",
    "node2_data_link_up",
    "node2_network",
    "node2_data_link_down",
    "node2_physical_out",
]

SERVER_REQUEST_STAGES = [
    "server_physical",
    "server_data_link",
    "server_network",
    "server_transport",
    "server_session",
    "server_presentation",
    "server_application",
]

SERVER_RESPONSE_STAGES = [
    "server_resp_application",
    "server_resp_presentation",
    "server_resp_session",
    "server_resp_transport",
    "server_resp_network",
    "server_resp_data_link",
    "server_resp_physical",
]

NODE2_RESPONSE_STAGES = [
    "node2_resp_physical_in",
    "node2_resp_data_link_up",
    "node2_resp_network",
    "node2_resp_data_link_down",
    "node2_resp_physical_out",
]

NODE1_RESPONSE_STAGES = [
    "node1_resp_physical_in",
    "node1_resp_data_link_up",
    "node1_resp_network",
    "node1_resp_data_link_down",
    "node1_resp_physical_out",
]

CLIENT_RESPONSE_STAGES = [
    "client_resp_physical",
    "client_resp_data_link",
    "client_resp_network",
    "client_resp_transport",
    "client_resp_session",
    "client_resp_presentation",
    "client_resp_application",
]


def _dns_entity_process(env, entity_id, logger, params, done_event):
    """SimPy process for a DNS query entity (📧). Signals done_event on completion."""
    def _do_stage(stage, base_time, state_label):
        logger.log_queue(
            entity_id=entity_id,
            event=stage,
            time=env.now,
            state_label=state_label,
        )
        return env.timeout(max(1, base_time))

    logger.log_arrival(
        entity_id=entity_id,
        time=env.now,
        state_label=f"DNS:{DNS_QUERY_DOMAIN}",
    )

    for stage in CLIENT_REQUEST_STAGES:
        yield _do_stage(stage, params["client_layer_time"], f"DNS query: {DNS_QUERY_DOMAIN}")

    for stage in NODE1_REQUEST_STAGES:
        yield _do_stage(stage, params["node_layer_time"], f"DNS query: {DNS_QUERY_DOMAIN}")

    # DNS Server — Physical → Application
    for stage in DNS_REQUEST_STAGES:
        yield _do_stage(stage, params["node_layer_time"], f"DNS lookup for {DNS_QUERY_DOMAIN}")

    # DNS server resolves the query
    params["env_state"]["dns_map"][DNS_QUERY_DOMAIN] = DNS_RESOLVED_IP
    yield env.timeout(max(1, params["dns_processing_time"]))

    # DNS Server — Application → Physical
    for stage in DNS_RESPONSE_STAGES:
        yield _do_stage(stage, params["node_layer_time"], f"DNS response: {DNS_RESOLVED_IP}")

    for stage in NODE1_RESPONSE_STAGES:
        yield _do_stage(stage, params["node_layer_time"], f"DNS response: {DNS_RESOLVED_IP}")

    for stage in CLIENT_RESPONSE_STAGES:
        yield _do_stage(stage, params["client_layer_time"], f"DNS response: {DNS_RESOLVED_IP}")

    logger.log_departure(
        entity_id=entity_id,
        time=env.now,
        state_label=f"Resolved {DNS_QUERY_DOMAIN} -> {DNS_RESOLVED_IP}",
    )
    done_event.succeed()


def _http_entity_process(env, entity_id, logger, params, done_event):
    """SimPy process for an HTTP request entity (🌐). Starts only after DNS resolves."""
    resolved_ip = params["env_state"]["dns_map"].get(DNS_QUERY_DOMAIN)
    if resolved_ip is None:
        resolved_ip = DNS_RESOLVED_IP

    request_url = f"{resolved_ip}:80/"

    def _do_stage(stage, base_time, state_label):
        logger.log_queue(
            entity_id=entity_id,
            event=stage,
            time=env.now,
            state_label=state_label,
            request_url=request_url,
        )
        return env.timeout(max(1, base_time))

    # Limit concurrent HTTP work to the configured connection pool size.
    with params["http_connections"].request() as conn_req:
        yield conn_req

        logger.log_arrival(
            entity_id=entity_id,
            time=env.now,
            state_label=f"HTTP request: GET {request_url}",
            request_url=request_url,
        )

        for stage in CLIENT_REQUEST_STAGES:
            yield _do_stage(stage, params["client_layer_time"], f"GET {request_url}")

        for stage in NODE1_REQUEST_STAGES:
            yield _do_stage(stage, params["node_layer_time"], f"GET {request_url}")

        for stage in NODE2_REQUEST_STAGES:
            yield _do_stage(stage, params["node_layer_time"], f"GET {request_url}")

        for stage in SERVER_REQUEST_STAGES:
            yield _do_stage(stage, params["server_layer_time"], f"Server received GET {request_url}")

        # Server app decides the root response file.
        for fragment in INDEX_HTML_FRAGMENTS:
            params["env_state"]["response_fragments"].append(fragment)

        # Web server processes the request
        yield env.timeout(max(1, params["server_processing_time"]))

        # At transport, the server splits index.html into deterministic packets.
        total = len(INDEX_HTML_FRAGMENTS)
        for i, fragment in enumerate(INDEX_HTML_FRAGMENTS, start=1):
            yield _do_stage(
                "server_resp_transport",
                params["server_layer_time"],
                f"Packet {i}/{total}: {fragment}",
            )

        for stage in SERVER_RESPONSE_STAGES:
            if stage == "server_resp_transport":
                continue
            yield _do_stage(stage, params["server_layer_time"], "index.html response")

        for stage in NODE2_RESPONSE_STAGES:
            yield _do_stage(stage, params["node_layer_time"], "index.html response")

        for stage in NODE1_RESPONSE_STAGES:
            yield _do_stage(stage, params["node_layer_time"], "index.html response")

        # Transport only releases fragments to app in order.
        for i, fragment in enumerate(INDEX_HTML_FRAGMENTS, start=1):
            yield _do_stage(
                "client_resp_transport",
                params["client_layer_time"],
                f"Reassemble {i}/{total}: {fragment}",
            )
            yield _do_stage(
                "client_resp_application",
                params["client_layer_time"],
                f"Render {i}/{total}: {fragment}",
            )

        for stage in CLIENT_RESPONSE_STAGES:
            if stage in ("client_resp_transport", "client_resp_application"):
                continue
            yield _do_stage(stage, params["client_layer_time"], "index.html response")

        logger.log_departure(
            entity_id=entity_id,
            time=env.now,
            state_label=f"Completed GET {request_url}; rendered index.html",
            request_url=request_url,
        )
    done_event.succeed()


def _initial_dns_then_http_generator(env, logger, params):
    """Run one DNS lookup first, then generate HTTP requests indefinitely.

    DNS is a single startup operation (entity_id=1), and all HTTP requests
    use even IDs only so icon assignment stays HTTP=🌐 with icon cycling.
    """
    dns_id = 1
    dns_done = env.event()
    env.process(_dns_entity_process(env, dns_id, logger, params, dns_done))
    yield dns_done

    http_id = 2

    def _start_http_request():
        nonlocal http_id
        done = env.event()
        env.process(_http_entity_process(env, http_id, logger, params, done))
        http_id += 2

    # First HTTP request starts immediately once DNS is resolved.
    _start_http_request()

    while True:
        inter = max(1, params["inter_arrival_time"])
        yield env.timeout(inter)
        _start_http_request()


def _session_generator(env, logger, params):
    """Backward-compatible wrapper name used by run_simulation."""
    yield from _initial_dns_then_http_generator(env, logger, params)


def run_simulation(
    sim_duration: int = 300,
    inter_arrival_time: int = 18,
    client_layer_time: int = 1,
    node_layer_time: int = 1,
    server_layer_time: int = 1,
    server_processing_time: int = 5,
    dns_processing_time: int = 2,
):
    """Run the HTTP web-request OSI simulation.

    Parameters
    ----------
    sim_duration : int
        Total simulation time in milliseconds.
    inter_arrival_time : int
        Mean gap between successive web-request arrivals (milliseconds).
    client_layer_time : int
        Mean time a packet spends at each client-side OSI layer (milliseconds).
    node_layer_time : int
        Mean time a packet spends at each network-node OSI layer (milliseconds).
    server_layer_time : int
        Mean time a packet spends at each server-side OSI layer (milliseconds).
    server_processing_time : int
        Mean time the server spends generating a response (milliseconds).
    Notes
    -----
    HTTP flows are limited by an internal connection pool with capacity 2.
    Returns
    -------
    pandas.DataFrame
        Event log with columns: ``entity_id``, ``time``, ``event_type``,
        ``event``.
    """
    # Normalize timing inputs to integer milliseconds.
    sim_duration = max(1, int(round(sim_duration)))
    inter_arrival_time = max(1, int(round(inter_arrival_time)))
    client_layer_time = max(1, int(round(client_layer_time)))
    node_layer_time = max(1, int(round(node_layer_time)))
    server_layer_time = max(1, int(round(server_layer_time)))
    server_processing_time = max(1, int(round(server_processing_time)))
    dns_processing_time = max(1, int(round(dns_processing_time)))

    env = simpy.Environment()
    logger = EventLogger(env=env)
    http_connections = simpy.Resource(env, capacity=2)

    params = {
        "inter_arrival_time": inter_arrival_time,
        "client_layer_time": client_layer_time,
        "node_layer_time": node_layer_time,
        "server_layer_time": server_layer_time,
        "server_processing_time": server_processing_time,
        "dns_processing_time": dns_processing_time,
        "http_connections": http_connections,
        "env_state": {
            "dns_map": {},
            "response_fragments": [],
        },
    }

    env.process(_session_generator(env, logger, params))
    env.run(until=sim_duration)

    return logger.to_dataframe()
