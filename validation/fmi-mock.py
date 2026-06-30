import os
import time
import json
import argparse
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

THING_ID = "urn:test:airport-fmi-flight"

def fetch_td():
    """Fetches the Thing Description from the OpenTwins platform."""
    print(f"[FMI Mock] Fetching TD from {THINGS_ENDPOINT}/{THING_ID}...")
    resp = requests.get(f"{THINGS_ENDPOINT}/{THING_ID}", headers={"Accept": "application/td+json"})
    resp.raise_for_status()
    print("[FMI Mock] TD successfully loaded.")
    return resp.json()

def run_mqtt_publisher(scenario):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    # Initial estimated flying times (in minutes). 
    # Staggered to represent planes arriving at different times normally.
    remaining_flying_times = {
        "fmi1": 15.0,
        "fmi2": 22.0,
        "fmi3": 30.0,
        "fmi4": 45.0,
        "fmi5": 60.0
    }
    
    # Accelerated time simulation (decreases 1 minute per tick)
    time_decrease_rate = 1.0 
    print(f"[FMI Mock] Starting simulation for Scenario {scenario}...")
    
    try:
        while True:
            if scenario == 4:
                # SCENARIO 4: FMI Stress
                # All planes sync to the same flying time to simulate a concurrent arrival.
                remaining_flying_times["fmi1"] = max(0.0, remaining_flying_times["fmi1"] - time_decrease_rate)
                concurrent_arrival_time = remaining_flying_times["fmi1"]
                
                for fmi_id in remaining_flying_times.keys():
                    remaining_flying_times[fmi_id] = concurrent_arrival_time 
                    topic = f"{BASE_TOPIC}/{fmi_id}"
                    payload = {"flying": round(concurrent_arrival_time, 2)}
                    client.publish(topic, json.dumps(payload))
            
            else:
                # NORMAL SCENARIOS (1, 2, etc.): 
                # Planes approach the airport independently.
                for fmi_id in remaining_flying_times.keys():
                    remaining_flying_times[fmi_id] = max(0.0, remaining_flying_times[fmi_id] - time_decrease_rate)
                    topic = f"{BASE_TOPIC}/{fmi_id}"
                    payload = {"flying": round(remaining_flying_times[fmi_id], 2)}
                    client.publish(topic, json.dumps(payload))

            time.sleep(5)
            
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print("\n[FMI Mock] Disconnected.")

if __name__ == '__main__':
    # Argparse configuration to read the parameter from the console
    parser = argparse.ArgumentParser(description="FMI Flight Time Simulator")
    parser.add_argument(
        '-s', '--scenario', 
        type=int, 
        default=1, 
        help='Scenario number to execute (e.g., 1, 2, 3)'
    )
    
    args = parser.parse_args()

    try:
        # td = fetch_td() # Uncomment if you need to fetch the TD
        run_mqtt_publisher(args.scenario)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not fetch TD from OpenTwins platform: {e}")