import os
import time
import json
import random
import requests
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()
THINGS_ENDPOINT = os.getenv("OTV2_THINGS_URL", "http://localhost:8080")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
THING_ID = "urn:test:airport-ml-predictor"

def fetch_td():
    print(f"[ML Mock] Fetching TD from {THINGS_ENDPOINT}/things/{THING_ID}...")
    resp = requests.get(f"{THINGS_ENDPOINT}/things/{THING_ID}", headers={"Accept": "application/td+json"})
    resp.raise_for_status()
    print("[ML Mock] TD successfully loaded.")
    return resp.json()

def run_mqtt_publisher():
    client = mqtt.Client()
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    probability = 50.0
    print("[ML Mock] Starting airport ML model...")
    try:
        while True:
            res = random.choice([True, False])
            client.publish("telemetry/ml", json.dumps({"collapsed": res}))
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print("\n[ML Mock] Disconnected.")

if __name__ == '__main__':
    try:
        td = fetch_td()
        run_mqtt_publisher()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not fetch TD from OpenTwins platform: {e}")