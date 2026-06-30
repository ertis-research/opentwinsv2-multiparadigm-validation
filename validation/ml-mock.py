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

# The specific topic for the ML model
ML_TOPIC = f"{BASE_TOPIC}/ml"
THING_ID = "urn:test:airport-ml-predictor"

def fetch_td():
    """Fetches the Thing Description from the OpenTwins platform."""
    print(f"[ML Mock] Fetching TD from {THINGS_ENDPOINT}/{THING_ID}...")
    resp = requests.get(f"{THINGS_ENDPOINT}/{THING_ID}", headers={"Accept": "application/td+json"})
    resp.raise_for_status()
    print("[ML Mock] TD successfully loaded.")
    return resp.json()

def run_mqtt_publisher(scenario):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    print(f"[ML Mock] Starting Machine Learning Simulator for Scenario {scenario}...")
    
    try:
        while True:
            # SCENARIO 5: The ML model detects an anomaly/collapse
            if scenario == 5:
                is_collapsed = True
            # ALL OTHER SCENARIOS: Normal operation, no collapse detected
            else:
                is_collapsed = False

            # Prepare and send the payload
            payload = {"collapsed": is_collapsed}
            client.publish(ML_TOPIC, json.dumps(payload))
            
            # Print to console for debugging
            print(f"[ML Mock] Published to {ML_TOPIC}: {payload}")

            # Wait 5 seconds before the next prediction tick
            time.sleep(5)
            
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print("\n[ML Mock] Disconnected.")

if __name__ == '__main__':
    # Argparse configuration to read the parameter from the console
    parser = argparse.ArgumentParser(description="Machine Learning Collapse Predictor")
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