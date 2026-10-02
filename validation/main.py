#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RQ - Digital Twin Multiparadigm Orchestrator
"""

from datetime import datetime
import os
import sys
import pandas as pd
from time import perf_counter
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
import quantitative

load_dotenv()

timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = os.path.join("output", timestamp_str)
os.makedirs(OUTPUT_DIR, exist_ok=True)
METRICS_CSV = os.path.join(OUTPUT_DIR, "performance_metrics.csv")
metrics_data = [] # List to hold metrics dicts in memory before flushing

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
RDF_FORMAT = "nquads"  # Default format for RDF serialization
LOG_FILE = os.path.join(OUTPUT_DIR, "execution_traces.log")
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
    t0_api = perf_counter()
    resp = requests.get(TWINS_ENDPOINT + "/twins/" + TWIN_ID, headers=headers)
    resp.raise_for_status()
    t1_api = perf_counter()
    api_fetch_time_ms = (t1_api - t0_api) * 1000

    g = Graph()
    g.parse(data=resp.text, format=RDF_FORMAT)
    g.serialize(os.path.join(OUTPUT_DIR, f"{name}.ttl"), format="turtle")
    g.serialize(os.path.join(OUTPUT_DIR, f"{name}.jsonld"), format="json-ld")
    #g.serialize(f"{name}.jsonld", format="json-ld")
    #print(f"Graph loaded with {len(g)} triples")
    if len(g) == 0:
        print("[ERROR] Graph empty")
    return g, api_fetch_time_ms, len(g)

# ============================================
# Subprocess Orchestrator
# ============================================

def run_scenario(scenario_id: int, description: str, expected_scenario: str, num_runs: int = 5, num_warmup: int = 1):
    """
    Launches the Python simulators as background subprocesses, waits for them
    to populate the KG, evaluates the KG, and then kills the subprocesses.
    """
    print(f"\n[{time.strftime('%X')}] Triggering Scenario {scenario_id}: {description}")
    scripts = ["fmi-mock.py", "ml-mock.py", "telemetry-mock.py"]
    total_iterations = num_warmup + num_runs

    for iteration in range(1, total_iterations + 1):
        is_warmup = iteration <= num_warmup
        run_index = iteration - num_warmup
        run_label = "WARM-UP" if is_warmup else f"RUN {run_index}/{num_runs}"
        
        print(f"\n--- Scenario {scenario_id} | {run_label} ---")
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
        g, api_time_ms, num_triples = load_graph_from_api(f"esc{scenario_id}")
        all_passed, query_times, query_results = querys.verify_isolated_scenario(g, expected_scenario=expected_scenario)

        # 4. Terminate simulators to prevent interference with the next scenario
        print(f"[INFO] Terminating simulators for Scenario {scenario_id}...")
        for p in processes:
            p.terminate()
            p.wait() # Ensure the process is fully closed before moving on
        
        # Store and persist metrics
        if not is_warmup:
            metric_entry = {
                "Scenario_ID": scenario_id,
                "Expected_Scenario": expected_scenario,
                "Run_Number": run_index,
                "Verdict_Passed": all_passed,  # <-- Stores the final verdict
                "API_Fetch_Time_ms": api_time_ms,
                "Graph_Triples_Count": num_triples
            }
            
            for q_name, q_time in query_times.items():
                metric_entry[f"SPARQL_{q_name}_ms"] = q_time
                metric_entry[f"Result_{q_name}"] = query_results[q_name]
                
            metrics_data.append(metric_entry)
            
            df_metrics = pd.DataFrame(metrics_data)
            df_metrics.to_csv(METRICS_CSV, index=False)
            print(f"[METRICS] Scenario {scenario_id} saved. API: {api_time_ms:.2f}ms | Triples: {num_triples}")

# ============================================
# Main Execution Flow
# ============================================

def execute_test():
    sys.stdout = Logger(LOG_FILE)
    print(f"\n\n>>> RUN DATETIME: {datetime.now()} <<<")
    print(f">>> OUTPUT DIR: {OUTPUT_DIR} <<<")
    print("Initializing base configuration for the DT environment...")
    init.prepare_base() 

    # SCENARIO 1: Baseline
    run_scenario(
        scenario_id=1, 
        description="Baseline. Everything is operating normally.",
        expected_scenario="baseline"
    )
    time.sleep(1)

    init.prepare_scenario2()
    # SCENARIO 2: Relationship Stress
    run_scenario(
        scenario_id=2, 
        description="Relationship Stress. All gates are related with planes.",
        expected_scenario="associative"
    )
    init.remove_scenario2()
    time.sleep(1)

    # SCENARIO 3: Telemetry Stress
    run_scenario(
        scenario_id=3, 
        description="Telemetry Stress. All gates report full occupancy.",
        expected_scenario="physical"
    )
    time.sleep(1)
    # SCENARIO 4: FMI Stress
    run_scenario(
        scenario_id=4, 
        description="FMI Stress. All 5 planes are approaching at the same time.",
        expected_scenario="aerial"
    )
    time.sleep(1)

    # SCENARIO 5: Multiparadigm ML Collapse
    run_scenario(
        scenario_id=5, 
        description="ML Collapse. Full gates + All planes flying = ML predicts collapse.",
        expected_scenario="prediction"
    )

    print("\nTest complete: Multiparadigm state consistency successfully validated via SPARQL.")


def main():
    try:
        execute_test()
        # Figure module generates the visuals from the /output directory
        # OUTPUT_DIR = os.path.join("output", "20260928_193620")
        figure.visualize_all_graphs_paper_ready(OUTPUT_DIR)
        quantitative.plot_granular_sparql_metrics(OUTPUT_DIR)
        quantitative.plot_api_fetch_metrics(OUTPUT_DIR)
    except KeyboardInterrupt:
        print("\n[INFO] Orchestration aborted by user.")


if __name__ == "__main__":
    main()