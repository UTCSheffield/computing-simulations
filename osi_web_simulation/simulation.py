"""SimPy simulation of deterministic web traffic through OSI layers.

Flow model:
1) One DNS request/response resolves bbc.co.uk/ -> 151.101.128.81
2) One initial HTTP request for index.html
3) When index.html packets 2/3/4 reach client application, trigger requests for
   style.css / logo.png / hero.png respectively.

Concurrency rules:
- Max 2 active HTTP requests at once (connection pool)
- Server application serves only 1 request at a time
- More than one response packet can be in flight concurrently
- A request completes only when its last response packet reaches client app
"""

import simpy
from vidigi.logging import EventLogger

DNS_QUERY_DOMAIN = "bbc.co.uk/"
DNS_RESOLVED_IP = "151.101.128.81"

# 1 packet = 1KB
RESPONSE_FILES_KB = [
    ("index.html", 5),
    ("style.css", 5),
    ("logo.png", 10),
    ("hero.png", 10),
]
FILE_SIZE_KB = dict(RESPONSE_FILES_KB)
FINAL_RENDER_DELAY_MS = 5
INDEX_PACKET_TRIGGERS = {
    2: "style.css",
    3: "logo.png",
    4: "hero.png",
}

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


def _dns_entity_process(env, entity_id, logger, params, done_event):
    def _do_stage(stage, base_time, state_label):
        logger.log_queue(
            entity_id=entity_id,
            event=stage,
            time=env.now,
            state_label=state_label,
        )
        return env.timeout(max(1, base_time))

    logger.log_arrival(entity_id=entity_id, time=env.now, state_label=f"DNS:{DNS_QUERY_DOMAIN}")

    for stage in CLIENT_REQUEST_STAGES:
        yield _do_stage(stage, params["client_layer_time"], f"DNS query: {DNS_QUERY_DOMAIN}")

    for stage in NODE1_REQUEST_STAGES:
        yield _do_stage(stage, params["node_layer_time"], f"DNS query: {DNS_QUERY_DOMAIN}")

    for stage in DNS_REQUEST_STAGES:
        yield _do_stage(stage, params["node_layer_time"], f"DNS lookup for {DNS_QUERY_DOMAIN}")

    params["env_state"]["dns_map"][DNS_QUERY_DOMAIN] = DNS_RESOLVED_IP
    yield env.timeout(max(1, params["dns_processing_time"]))

    for stage in DNS_RESPONSE_STAGES:
        yield _do_stage(stage, params["node_layer_time"], f"DNS response: {DNS_RESOLVED_IP}")

    for stage in NODE1_RESPONSE_STAGES:
        yield _do_stage(stage, params["node_layer_time"], f"DNS response: {DNS_RESOLVED_IP}")

    for stage in [
        "client_resp_physical",
        "client_resp_data_link",
        "client_resp_network",
        "client_resp_transport",
        "client_resp_session",
        "client_resp_presentation",
        "client_resp_application",
    ]:
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

    def _deliver_response_packet(packet, packet_text, packet_done_event):
        pkt_entity_id = params["env_state"]["next_entity_id"]
        params["env_state"]["next_entity_id"] += 1

        def _pkt_stage(stage, base_time, state_label):
            logger.log_queue(
                entity_id=pkt_entity_id,
                event=stage,
                time=env.now,
                state_label=state_label,
                request_url=request_url,
            )
            return env.timeout(max(1, base_time))

        def _run():
            logger.log_arrival(
                entity_id=pkt_entity_id,
                time=env.now,
                state_label=f"TX {packet_text}",
                request_url=request_url,
            )

            yield _pkt_stage("server_resp_transport", 1, f"TX {packet_text}")

            for stage in ["server_resp_network", "server_resp_data_link", "server_resp_physical"]:
                yield _pkt_stage(stage, params["server_layer_time"], f"TX {packet_text}")

            for stage in NODE2_RESPONSE_STAGES:
                yield _pkt_stage(stage, params["node_layer_time"], f"Forward {packet_text}")

            for stage in NODE1_RESPONSE_STAGES:
                yield _pkt_stage(stage, params["node_layer_time"], f"Forward {packet_text}")

            for stage in ["client_resp_physical", "client_resp_data_link", "client_resp_network"]:
                yield _pkt_stage(stage, params["client_layer_time"], f"RX {packet_text}")

            yield _pkt_stage("client_resp_transport", params["client_layer_time"], f"In-order deliver {packet_text}")
            yield _pkt_stage("client_resp_session", params["client_layer_time"], f"Pass up {packet_text}")
            yield _pkt_stage("client_resp_presentation", params["client_layer_time"], f"Pass up {packet_text}")
            yield _pkt_stage("client_resp_application", params["client_layer_time"], f"App recv {packet_text}")

            # Track file completion at client application
            if file_name not in params["env_state"]["files_packets_received"]:
                params["env_state"]["files_packets_received"][file_name] = 0
            
            params["env_state"]["files_packets_received"][file_name] += 1
            packets_received = params["env_state"]["files_packets_received"][file_name]
            file_size_kb = FILE_SIZE_KB[file_name]
            
            # If this completes the file, emit "show file" message
            if packets_received == file_size_kb and file_name not in params["env_state"]["files_fully_received"]:
                params["env_state"]["files_fully_received"].add(file_name)

                # Start a persistent page-status entity at first file completion.
                # It never departs, so the final rendered label remains visible.
                if not params["env_state"]["page_status_started"]:
                    logger.log_arrival(entity_id=0, time=env.now, state_label="")
                    params["env_state"]["page_status_started"] = True
                
                # Log file completion event (using a pseudo entity)
                logger.log_queue(
                    entity_id=0,  # Use entity 0 for page events
                    event="file_complete",
                    time=env.now,
                    state_label=f"Show {file_name}",
                    request_url=DNS_QUERY_DOMAIN,
                )
                
                # Check if all files are now complete
                if len(params["env_state"]["files_fully_received"]) == 4:  # index + 3 secondary files
                    # Small render delay to model browser compose/paint time.
                    yield env.timeout(FINAL_RENDER_DELAY_MS)
                    logger.log_queue(
                        entity_id=0,
                        event="page_rendered",
                        time=env.now,
                        state_label=f"Rendered {DNS_QUERY_DOMAIN}",
                        request_url=DNS_QUERY_DOMAIN,
                    )

            logger.log_departure(
                entity_id=pkt_entity_id,
                time=env.now,
                state_label=f"Delivered {packet_text}",
                request_url=request_url,
            )

            if file_name == "index.html" and index_packet_callback is not None:
                index_packet_callback(packet["seq"])

            packet_done_event.succeed()

        return _run()

    # Active-request slot held for full lifecycle until last response packet reaches client app.
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

        # Ingress to server app
        for stage in SERVER_REQUEST_STAGES:
            if stage == "server_application":
                break
            yield _do_stage(stage, params["server_layer_time"], f"GET {request_url}")

        packet_store = simpy.Store(env)

        # Server application can only serve one request at a time.
        with params["server_app_resource"].request() as app_req:
            yield app_req

            yield _do_stage(
                "server_application",
                params["server_layer_time"],
                f"App server serving: {file_name}",
            )

            yield env.timeout(max(1, params["server_processing_time"]))

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

        # L4 emits one packet/tick; packet delivery continues concurrently.
        in_flight_done_events = []
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

            packet_done = env.event()
            in_flight_done_events.append(packet_done)
            env.process(_deliver_response_packet(packet, packet_text, packet_done))

        if in_flight_done_events:
            yield env.all_of(in_flight_done_events)

        logger.log_departure(
            entity_id=entity_id,
            time=env.now,
            state_label=f"Completed GET {request_url}; delivered {file_size_kb} packets",
            request_url=request_url,
        )

    done_event.succeed()


def _single_dns_then_http_flow(env, logger, params):
    dns_done = env.event()
    env.process(_dns_entity_process(env, 1, logger, params, dns_done))
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

    index_done = env.event()
    params["env_state"]["requested_files"].add("index.html")
    env.process(
        _http_file_request_process(
            env,
            2,
            logger,
            params,
            resolved_ip,
            "index.html",
            index_done,
            index_packet_callback=_on_index_packet_at_client,
        )
    )
    yield index_done

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
    """Run deterministic DNS + HTTP simulation and return event log DataFrame."""
    sim_duration = max(1, int(round(sim_duration)))
    inter_arrival_time = max(1, int(round(inter_arrival_time)))
    client_layer_time = max(1, int(round(client_layer_time)))
    node_layer_time = max(1, int(round(node_layer_time)))
    server_layer_time = max(1, int(round(server_layer_time)))
    server_processing_time = max(1, int(round(server_processing_time)))
    dns_processing_time = max(1, int(round(dns_processing_time)))

    env = simpy.Environment()
    logger = EventLogger(env=env)

    params = {
        "inter_arrival_time": inter_arrival_time,
        "client_layer_time": client_layer_time,
        "node_layer_time": node_layer_time,
        "server_layer_time": server_layer_time,
        "server_processing_time": server_processing_time,
        "dns_processing_time": dns_processing_time,
        "http_connections": simpy.Resource(env, capacity=2),
        "server_app_resource": simpy.Resource(env, capacity=1),
        "env_state": {
            "dns_map": {},
            "requested_files": set(),
            "next_entity_id": 4,
            "files_packets_received": {},  # Track packets received per file at client app
            "files_fully_received": set(),  # Track completed files
            "page_status_started": False,  # Tracks persistent client L7 status entity
        },
    }

    env.process(_single_dns_then_http_flow(env, logger, params))
    env.run()
    return logger.to_dataframe()
