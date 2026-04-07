"""SimPy simulation of HTTP web requests flowing through OSI layers.

Models a request travelling:
  Client (Application → Physical)
  → Network Node 1 (Physical → Network)
  → Network Node 2 (Physical → Network)
  → Server (Physical → Application)
  → Server processes and sends response
  → Server (Application → Physical)
  → Network Node 2 (Network → Physical)
  → Network Node 1 (Network → Physical)
  → Client (Physical → Application)
"""

import random

import simpy
from vidigi.logging import EventLogger

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
    "node1_physical",
    "node1_data_link",
    "node1_network",
]

NODE2_REQUEST_STAGES = [
    "node2_physical",
    "node2_data_link",
    "node2_network",
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
    "node2_resp_network",
    "node2_resp_data_link",
    "node2_resp_physical",
]

NODE1_RESPONSE_STAGES = [
    "node1_resp_network",
    "node1_resp_data_link",
    "node1_resp_physical",
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


def _web_request_process(env, request_id, logger, params):
    """SimPy process for a single HTTP web request (request + response)."""
    jitter = params["jitter"]

    def _do_stage(stage, base_time):
        logger.log_queue(entity_id=request_id, event=stage, time=env.now)
        duration = max(0.05, base_time + random.uniform(-jitter, jitter))
        return env.timeout(duration)

    logger.log_arrival(entity_id=request_id, time=env.now)

    # --- REQUEST: Client OSI stack (Application → Physical) ---
    for stage in CLIENT_REQUEST_STAGES:
        yield _do_stage(stage, params["client_layer_time"])

    # --- REQUEST: Network Node 1 (Physical → Network) ---
    for stage in NODE1_REQUEST_STAGES:
        yield _do_stage(stage, params["node_layer_time"])

    # --- REQUEST: Network Node 2 (Physical → Network) ---
    for stage in NODE2_REQUEST_STAGES:
        yield _do_stage(stage, params["node_layer_time"])

    # --- REQUEST: Server OSI stack (Physical → Application) ---
    for stage in SERVER_REQUEST_STAGES:
        yield _do_stage(stage, params["server_layer_time"])

    # Server processes the request
    yield env.timeout(
        max(0.1, params["server_processing_time"] + random.uniform(0, jitter * 2))
    )

    # --- RESPONSE: Server OSI stack (Application → Physical) ---
    for stage in SERVER_RESPONSE_STAGES:
        yield _do_stage(stage, params["server_layer_time"])

    # --- RESPONSE: Network Node 2 (Network → Physical) ---
    for stage in NODE2_RESPONSE_STAGES:
        yield _do_stage(stage, params["node_layer_time"])

    # --- RESPONSE: Network Node 1 (Network → Physical) ---
    for stage in NODE1_RESPONSE_STAGES:
        yield _do_stage(stage, params["node_layer_time"])

    # --- RESPONSE: Client OSI stack (Physical → Application) ---
    for stage in CLIENT_RESPONSE_STAGES:
        yield _do_stage(stage, params["client_layer_time"])

    logger.log_departure(entity_id=request_id, time=env.now)


def _request_generator(env, logger, params):
    """Generate web requests at exponentially-distributed intervals."""
    request_id = 0
    while True:
        inter = max(0.1, random.expovariate(1.0 / params["inter_arrival_time"]))
        yield env.timeout(inter)
        request_id += 1
        env.process(_web_request_process(env, request_id, logger, params))


def run_simulation(
    sim_duration: float = 300.0,
    inter_arrival_time: float = 18.0,
    client_layer_time: float = 1.2,
    node_layer_time: float = 0.6,
    server_layer_time: float = 1.2,
    server_processing_time: float = 5.0,
    jitter: float = 0.3,
    random_seed: int = 42,
):
    """Run the HTTP web-request OSI simulation.

    Parameters
    ----------
    sim_duration : float
        Total simulation time (arbitrary time units).
    inter_arrival_time : float
        Mean gap between successive web-request arrivals (same units).
    client_layer_time : float
        Mean time a packet spends at each client-side OSI layer.
    node_layer_time : float
        Mean time a packet spends at each network-node OSI layer.
    server_layer_time : float
        Mean time a packet spends at each server-side OSI layer.
    server_processing_time : float
        Mean time the server spends generating a response.
    jitter : float
        Half-width of the uniform random perturbation added to each delay.
    random_seed : int
        Seed for the random-number generator (for reproducibility).

    Returns
    -------
    pandas.DataFrame
        Event log with columns: ``entity_id``, ``time``, ``event_type``,
        ``event``.
    """
    random.seed(random_seed)

    env = simpy.Environment()
    logger = EventLogger(env=env)

    params = {
        "inter_arrival_time": inter_arrival_time,
        "client_layer_time": client_layer_time,
        "node_layer_time": node_layer_time,
        "server_layer_time": server_layer_time,
        "server_processing_time": server_processing_time,
        "jitter": jitter,
    }

    env.process(_request_generator(env, logger, params))
    env.run(until=sim_duration)

    return logger.to_dataframe()
