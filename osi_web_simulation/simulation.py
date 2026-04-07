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

# 1 packet = 1KB. Deterministic server response set.
RESPONSE_FILES_KB = [
    ("index.html", 5),
    ("style.css", 5),
    ("logo.png", 10),
    ("hero.png", 10),
]
TOTAL_RESPONSE_PACKETS = sum(size_kb for _, size_kb in RESPONSE_FILES_KB)
FILE_SIZE_KB = dict(RESPONSE_FILES_KB)
INDEX_PACKET_TRIGGERS = {
    2: "style.css",
    3: "logo.png",
    4: "hero.png",
}



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


def _server_l7_to_l5_response_builder(
    env,
    entity_id,
    logger,
    params,
    request_url,
    file_name,
    file_size_kb,
    packet_store,
    done_event,
):
    """Server L7→L5 process: serves files one at a time and queues packet metadata."""
    layer_time = params["server_layer_time"]
    logger.log_queue(
        entity_id=entity_id,
        event="server_resp_application",
        time=env.now,
        state_label=f"App server serving: {file_name}",
        request_url=request_url,
    )
    yield env.timeout(max(1, layer_time))

    logger.log_queue(
        entity_id=entity_id,
        event="server_resp_presentation",
        time=env.now,
        state_label=f"Prepare {file_name} payload",
        request_url=request_url,
    )
    yield env.timeout(max(1, layer_time))

    logger.log_queue(
        entity_id=entity_id,
        event="server_resp_session",
        time=env.now,
        state_label=f"Open stream for {file_name}",
        request_url=request_url,
    )
    yield env.timeout(max(1, layer_time))

    for file_packet in range(1, file_size_kb + 1):
        yield packet_store.put(
            {
                "seq": file_packet,
                "file": file_name,
                "file_packet": file_packet,
                "file_total": file_size_kb,
                "size_kb": 1,
            }
        )

    done_event.succeed()


def _http_file_request_process(
    env,
    entity_id,
    logger,
    params,
    resolved_ip,
    file_name,
    done_event,
    index_packet_callback=None,
):
    """Process one HTTP file request from send to final packet at client application."""
    if file_name == "index.html":
        request_path = "/"
    else:
        request_path = f"/{file_name}"
    request_url = f"{resolved_ip}:80{request_path}"
    file_size_kb = FILE_SIZE_KB[file_name]

    def _do_stage(stage, base_time, state_label, **extra_fields):
        logger.log_queue(
            entity_id=entity_id,
            event=stage,
            time=env.now,
            state_label=state_label,
            request_url=request_url,
            **extra_fields,
        )
        return env.timeout(max(1, base_time))

    # One slot represents one active HTTP request lifecycle, from request send
    # until the final response packet is delivered to client application.
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
            if stage == "server_application":
                yield _do_stage(
                    stage,
                    params["server_layer_time"],
                    f"App server serving: {file_name}",
                )
            else:
                yield _do_stage(stage, params["server_layer_time"], f"GET {request_url}")

        # Server processing before response-building starts.
        yield env.timeout(max(1, params["server_processing_time"]))

        packet_store = simpy.Store(env)
        build_done = env.event()
        env.process(
            _server_l7_to_l5_response_builder(
                env,
                entity_id,
                logger,
                params,
                request_url,
                file_name,
                file_size_kb,
                packet_store,
                build_done,
            )
        )
        yield build_done

        # L4 packetization: exactly 1 packet per tick, then forward packet down stack.
        for _ in range(file_size_kb):
            packet = yield packet_store.get()
            packet_text = (
                f"pkt {packet['seq']} "
                f"{packet['file']} {packet['file_packet']}/{packet['file_total']} (1KB)"
            )

            yield _do_stage(
                "server_resp_transport",
                1,
                f"TX {packet_text}",
                packet_seq=packet["seq"],
                packet_file=packet["file"],
                packet_file_seq=packet["file_packet"],
                packet_file_total=packet["file_total"],
                packet_size_kb=packet["size_kb"],
            )

            # Server L3→L1 for this packet.
            for stage in ["server_resp_network", "server_resp_data_link", "server_resp_physical"]:
                yield _do_stage(stage, params["server_layer_time"], f"TX {packet_text}")

            # Routers forward packet.
            for stage in NODE2_RESPONSE_STAGES:
                yield _do_stage(stage, params["node_layer_time"], f"Forward {packet_text}")

            for stage in NODE1_RESPONSE_STAGES:
                yield _do_stage(stage, params["node_layer_time"], f"Forward {packet_text}")

            # Client receives L1→L3 then L4 releases in-sequence.
            for stage in ["client_resp_physical", "client_resp_data_link", "client_resp_network"]:
                yield _do_stage(stage, params["client_layer_time"], f"RX {packet_text}")

            yield _do_stage("client_resp_transport", params["client_layer_time"], f"In-order deliver {packet_text}")
            yield _do_stage("client_resp_session", params["client_layer_time"], f"Pass up {packet_text}")
            yield _do_stage("client_resp_presentation", params["client_layer_time"], f"Pass up {packet_text}")
            yield _do_stage("client_resp_application", params["client_layer_time"], f"App recv {packet_text}")

            if file_name == "index.html" and index_packet_callback is not None:
                index_packet_callback(packet["seq"])

        logger.log_departure(
            entity_id=entity_id,
            time=env.now,
            state_label=f"Completed GET {request_url}; delivered {file_size_kb} packets",
            request_url=request_url,
        )
    done_event.succeed()


def _single_dns_then_http_flow(env, logger, params):
    """Run exactly one DNS then one HTTP process end-to-end."""
    dns_id = 1
    dns_done = env.event()
    env.process(_dns_entity_process(env, dns_id, logger, params, dns_done))
    yield dns_done

    resolved_ip = params["env_state"]["dns_map"].get(DNS_QUERY_DOMAIN, DNS_RESOLVED_IP)

    spawned_done_events = []

    def _spawn_request(file_name):
        if file_name in params["env_state"]["requested_files"]:
            return
        params["env_state"]["requested_files"].add(file_name)
        entity_id = params["env_state"]["next_entity_id"]
        params["env_state"]["next_entity_id"] += 2
        ev = env.event()
        spawned_done_events.append(ev)
        env.process(
            _http_file_request_process(
                env,
                entity_id,
                logger,
                params,
                resolved_ip,
                file_name,
                ev,
            )
        )

    def _on_index_packet_at_client(packet_no):
        file_to_request = INDEX_PACKET_TRIGGERS.get(packet_no)
        if file_to_request is not None:
            _spawn_request(file_to_request)

    http_done = env.event()
    params["env_state"]["requested_files"].add("index.html")
    env.process(
        _http_file_request_process(
            env,
            2,
            logger,
            params,
            resolved_ip,
            "index.html",
            http_done,
            index_packet_callback=_on_index_packet_at_client,
        )
    )
    yield http_done

    if spawned_done_events:
        yield env.all_of(spawned_done_events)


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
        Retained for backward compatibility. Ignored in single-flow mode.
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
    Runs one deterministic DNS + HTTP flow and stops when it completes.
    HTTP flows use an internal connection pool with capacity 2.
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
            "requested_files": set(),
            "next_entity_id": 4,
        },
    }

    # Run to natural completion of the single deterministic flow.
    env.process(_single_dns_then_http_flow(env, logger, params))
    env.run()

    return logger.to_dataframe()
