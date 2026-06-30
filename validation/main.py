#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RQ - Digital Twin Multiparadigm Orchestrator
"""

from datetime import datetime
import os
import sys
import time
import requests
import subprocess
import json
from rdflib import Graph
from dotenv import load_dotenv

# Ensure you have your local modules available
import init
import figure
import querys

load_dotenv()

class Logger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)  # Imprime en la consola
        self.log.write(message)       # Guarda en el archivo
        self.log.flush()              # Fuerza el guardado inmediato

    def flush(self):
        self.terminal.flush()

# ============================================
# Environment Variables & Configuration
# ============================================
TWINS_ENDPOINT = os.getenv("OTV2_TWINS_URL")
TWIN_ID = os.getenv("OTV2_TWIN_ID")
RDF_FORMAT = "nquads"
LOG_FILE = "output/execution_traces.log"
WAIT_TIME_SECONDS = 7 # Slightly increased to give simulators time to spin up and publish

# ============================================
# Helper Functions for KG Processing
# ============================================

def convert_custom_json_to_jsonld(data: dict) -> dict:
    """
    Transforms the custom JSON API response into standard JSON-LD format.
    Extracts context, uses 'thingId' as '@id', and normalizes relationships.
    """
    # 1. Build the @context from the namespace
    context = {}
    for ns in data.get("namespace", []):
        prefix = ns.get("prefix", "")
        uri = ns.get("uri", "")
        if prefix == "":
            context["@vocab"] = uri
        else:
            context[prefix] = uri

    # 2. Build the @graph from 'things'
    graph_nodes = []
    for thing in data.get("things", []):
        # The '@id' is essential for RDF relationships
        node = {
            "@id": thing["thingId"],
            "name": thing["name"],
            "createdAt": thing["createdAt"]
        }
        
        for rel in thing.get("relations", []):
            rel_name = rel.get("Relation.name", "")
            
            # NORMALIZATION: Unify relationships starting with hasTelemetry
            if rel_name.startswith("hasTelemetry"):
                rel_name = "hasTelemetry"
                
            # Extract target entities from 'relatedTo' or 'hasChild'
            targets = rel.get("relatedTo", [])
            if not targets:
                targets = rel.get("hasChild", [])
                
            # Create RDF references pointing to the target's 'thingId'
            target_refs = [{"@id": t["thingId"]} for t in targets]
            
            if target_refs:
                node[rel_name] = target_refs
                
        graph_nodes.append(node)

    return {
        "@context": context,
        "@graph": graph_nodes
    }

def load_graph_from_api(name):
    #print("Loading graph from API…")
    headers = {"Accept": "application/n-quads"}
    resp = requests.get(TWINS_ENDPOINT + "/twins/" + TWIN_ID, headers=headers)
    resp.raise_for_status()

    g = Graph()
    g.parse(data=resp.text, format=RDF_FORMAT)
    os.makedirs("output", exist_ok=True)
    g.serialize(f"output/{name}.ttl", format="turtle")
    g.serialize(f"output/{name}.jsonld", format="json-ld")
    #g.serialize(f"{name}.jsonld", format="json-ld")
    #print(f"Graph loaded with {len(g)} triples")
    if len(g) == 0:
        print("[ERROR] Graph empty")
    return g

# ============================================
# Subprocess Orchestrator
# ============================================

def run_scenario(scenario_id: int, description: str, expected_scenario: str):
    """
    Launches the Python simulators as background subprocesses, waits for them
    to populate the KG, evaluates the KG, and then kills the subprocesses.
    """
    print(f"\n[{time.strftime('%X')}] Triggering Scenario {scenario_id}: {description}")
    
    scripts = ["fmi-mock.py", "ml-mock.py", "telemetry-mock.py"]
    processes = []
    
    # 1. Launch simulators
    print("[INFO] Launching simulators in the background...")
    for script in scripts:
        # sys.executable ensures we use the exact same Python interpreter running this main script
        p = subprocess.Popen([sys.executable, script, "-s", str(scenario_id)])
        processes.append(p)
        
    # 2. Wait for MQTT propagation and API updates
    print(f"[INFO] Waiting {WAIT_TIME_SECONDS} seconds for simulators to process and KG to update...")
    time.sleep(WAIT_TIME_SECONDS)
    
    # 3. Fetch and evaluate the Knowledge Graph
    g = load_graph_from_api(f"esc{scenario_id}")
    querys.verify_isolated_scenario(g, expected_scenario=expected_scenario)
    
    # 4. Terminate simulators to prevent interference with the next scenario
    print(f"[INFO] Terminating simulators for Scenario {scenario_id}...")
    for p in processes:
        p.terminate()
        p.wait() # Ensure the process is fully closed before moving on

# ============================================
# Main Execution Flow
# ============================================

def execute_test():
    sys.stdout = Logger(LOG_FILE)
    print(f"\n\n>>> RUN DATETIME: {datetime.now()} <<<")
    print("Initializing base configuration for the DT environment...")
    init.prepare_base() 

    # SCENARIO 1: Baseline
    run_scenario(
        scenario_id=1, 
        description="Baseline. Everything is operating normally.",
        expected_scenario="baseline"
    )

    init.prepare_scenario2()
    # SCENARIO 2: Relationship Stress
    run_scenario(
        scenario_id=2, 
        description="Relationship Stress. All gates are related with planes.",
        expected_scenario="associative"
    )
    init.remove_scenario2()

    # SCENARIO 3: Telemetry Stress
    run_scenario(
        scenario_id=3, 
        description="Telemetry Stress. All gates report full occupancy.",
        expected_scenario="physical"
    )

    # SCENARIO 4: FMI Stress
    run_scenario(
        scenario_id=4, 
        description="FMI Stress. All 5 planes are approaching at the same time.",
        expected_scenario="aerial"
    )

    # SCENARIO 5: Multiparadigm ML Collapse
    run_scenario(
        scenario_id=5, 
        description="ML Collapse. Full gates + All planes flying = ML predicts collapse.",
        expected_scenario="prediction"
    )

    print("\nTest complete: Multiparadigm state consistency successfully validated via SPARQL.")


def main():
    try:
        #execute_test()
        # Figure module generates the visuals from the /output directory
        figure.visualize_all_graphs_paper_ready()
    except KeyboardInterrupt:
        print("\n[INFO] Orchestration aborted by user.")


if __name__ == "__main__":
    main()