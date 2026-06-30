import os
import time
import json
import argparse
import random
import requests
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

# Environment variables
THINGS_ENDPOINT = os.getenv("OTV2_THINGS_URL", "http://localhost:5001")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
BASE_TOPIC = os.getenv("MQTT_TOPIC_BASE", "test/base")

THING_ID = "urn:test:airport-telemetry-gates"

# Define the available gates
GATES = ["A1", "A2", "B1", "B2"]

def fetch_td():
    """Fetches the Thing Description from the OpenTwins platform."""
    print(f"[Telemetry Mock] Fetching TD from {THINGS_ENDPOINT}/{THING_ID}...")
    resp = requests.get(f"{THINGS_ENDPOINT}/{THING_ID}", headers={"Accept": "application/td+json"})
    resp.raise_for_status()
    print("[Telemetry Mock] TD successfully loaded.")
    return resp.json()

def run_mqtt_publisher(scenario):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    print(f"[Telemetry Mock] Starting Telemetry Gate Simulator for Scenario {scenario}...")
    
    try:
        while True:
            gate_states = {}

            if scenario == 3:
                # SCENARIO 3: All gates must be occupied (True)
                gate_states = {gate: True for gate in GATES}
            else:
                # ALL OTHER SCENARIOS: At least one gate must be free (False)
                # Randomly pick how many gates are occupied (0 to 3 max, never 4)
                num_occupied = random.randint(0, 3)
                occupied_gates = random.sample(GATES, num_occupied)
                
                # Assign True if the gate was selected, otherwise False
                gate_states = {gate: (gate in occupied_gates) for gate in GATES}

            # Publish the states for each gate to their specific topics
            for gate, is_occupied in gate_states.items():
                topic = f"{BASE_TOPIC}/gate{gate}"
                payload = {"occupied": is_occupied}
                client.publish(topic, json.dumps(payload))
                print(f"[Telemetry Mock] Published to {topic}: {payload}")
            
            print("-" * 40) # Separator for console readability
            
            # Wait 5 seconds before the next telemetry update
            time.sleep(5)
            
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print("\n[Telemetry Mock] Disconnected.")

if __name__ == '__main__':
    # Argparse configuration to read the scenario parameter from the console
    parser = argparse.ArgumentParser(description="Telemetry Gates Simulator")
    parser.add_argument(
        '-s', '--scenario', 
        type=int, 
        default=1, 
        help='Scenario number to execute (e.g., 1, 2, 3, 4, 5)'
    )
    
    args = parser.parse_args()

    try:
        # td = fetch_td() # Uncomment if you need to fetch the TD from OpenTwins
        run_mqtt_publisher(args.scenario)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not fetch TD from OpenTwins platform: {e}")