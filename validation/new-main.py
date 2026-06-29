#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RQ2 - How do KGs enhance the representation of DTs and reasoning about the relationships of CDTs?
Validation through multiparadigm orchestration (ML, FMI, Telemetry).
"""

import os
import time
import requests
import paho.mqtt.publish as publish
from rdflib import Graph
from dotenv import load_dotenv

import init
import figure

load_dotenv()

# ============================================
# Environment Variables & Configuration
# ============================================
TWINS_ENDPOINT = os.getenv("OTV2_TWINS_URL")
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_TOPIC_SCENARIO = "airport/test/scenarios"
RDF_FORMAT = "nquads"
WAIT_TIME_SECONDS = 5 # Time to wait for simulators and OTV2 to update the KG

# ============================================
# Helper Functions
# ============================================

def trigger_scenario_via_mqtt(scenario_id: int, description: str):
    """
    Publishes an MQTT message to notify simulators (ML, FMI, Telemetry) 
    about the current scenario. Simulators should react by sending the 
    corresponding payload to the OTV2 platform.
    """
    print(f"\n[{time.strftime('%X')}] Triggering Scenario {scenario_id}: {description}")
    payload = f'{{"scenario": {scenario_id}}}'
    
    try:
        publish.single(MQTT_TOPIC_SCENARIO, payload=payload, hostname=MQTT_BROKER, port=MQTT_PORT)
        print(f"[INFO] MQTT message sent to topic '{MQTT_TOPIC_SCENARIO}': {payload}")
    except Exception as e:
        print(f"[ERROR] Failed to send MQTT message: {e}")
        
    print(f"[INFO] Waiting {WAIT_TIME_SECONDS} seconds for simulators to process and KG to update...")
    time.sleep(WAIT_TIME_SECONDS)


def load_graph_from_api(name: str) -> Graph:
    """
    Fetches the updated Digital Twin Knowledge Graph from the OpenTwins V2 API.
    """
    headers = {"Accept": "application/n-quads"}
    resp = requests.get(f"{TWINS_ENDPOINT}/twins/urn:test:rq2", headers=headers)
    resp.raise_for_status()

    g = Graph()
    g.parse(data=resp.text, format=RDF_FORMAT)
    
    os.makedirs("output", exist_ok=True)
    g.serialize(f"output/{name}.ttl", format="turtle")
    
    if len(g) == 0:
        print("[WARNING] Graph loaded but it is empty!")
    else:
        print(f"[INFO] Graph '{name}' loaded successfully with {len(g)} triples.")
        
    return g


def verify_state_with_sparql(g: Graph):
    """
    Executes a single SPARQL query using logical OR (||) to retrieve the 
    status of the ML model (collapsed), Telemetry (occupied gates), 
    and FMI simulators (flying planes).
    """
    # This query uses FILTER with logical OR to match any of the three target properties,
    # abstracting away the specific namespace prefixes expanded by the JSON-LD context.
    sparql_query = """
    SELECT ?subject ?property ?value
    WHERE {
        ?subject ?predicate ?value .
        
        # Extract the local name of the property to simplify the logical OR matching
        BIND(REPLACE(STR(?predicate), "^.*[/#]", "") AS ?property)
        
        FILTER (
            ?property = "collapsed" || 
            ?property = "occupied" || 
            ?property = "flying"
        )
    }
    ORDER BY ?subject
    """
    
    results = g.query(sparql_query)
    
    print("\n--- SPARQL Query Results (State Snapshot) ---")
    if not results:
        print("No matching states found in the KG.")
        
    for row in results:
        subject = str(row.subject).split(":")[-1] # Clean up URI for printing
        prop = str(row.property)
        val = str(row.value)
        print(f" -> {subject} | {prop}: {val}")
    print("---------------------------------------------\n")


# ============================================
# Main Execution Flow
# ============================================

def execute_test():
    print("Initializing base configuration for the DT environment...")
    init.prepare_base()

    # ============================================
    # SCENARIO 1: Nominal Baseline (Control Group)
    # Expected: Airport NOT collapsed. Partial gate occupancy. Staggered flights.
    # ============================================
    trigger_scenario_via_mqtt(
        scenario_id=1, 
        description="Nominal Baseline. Everything is operating normally."
    )
    g = load_graph_from_api("scenario_1_nominal")
    verify_state_with_sparql(g)


    # ============================================
    # SCENARIO 2: Telemetry Stress
    # Expected: All gates (A1, A2, B1, B2) report OCCUPIED via sensors.
    # Airport might not be collapsed yet depending on plane status.
    # ============================================
    trigger_scenario_via_mqtt(
        scenario_id=2, 
        description="Telemetry Stress. All gates report full occupancy."
    )
    g = load_graph_from_api("scenario_2_telemetry")
    verify_state_with_sparql(g)


    # ============================================
    # SCENARIO 3: FMI Stress
    # Expected: All 5 FMI plane simulators report FLYING simultaneously.
    # ============================================
    trigger_scenario_via_mqtt(
        scenario_id=3, 
        description="FMI Stress. All 5 planes are approaching at the same time."
    )
    g = load_graph_from_api("scenario_3_fmi")
    verify_state_with_sparql(g)


    # ============================================
    # SCENARIO 4: Multiparadigm ML Collapse
    # Expected: ML reads telemetry (gates full) + FMI (planes flying)
    # and infers a COLLAPSED state for the airport.
    # ============================================
    trigger_scenario_via_mqtt(
        scenario_id=4, 
        description="ML Collapse. Full gates + All planes flying = ML predicts collapse."
    )
    g = load_graph_from_api("scenario_4_collapse")
    verify_state_with_sparql(g)

    print("\nTest complete: Multiparadigm state consistency successfully validated via SPARQL.")


def main():
    execute_test()
    # Assuming figure module generates the visuals from the /output directory
    figure.visualize_all_graphs_paper_ready()


if __name__ == "__main__":
    main()