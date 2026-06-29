import os
import time
import json
import requests
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()
THINGS_ENDPOINT = os.getenv("OTV2_THINGS_URL", "http://localhost:8080")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
THING_ID = "urn:test:airport-telemetry"

def fetch_td():
    print(f"[Telemetry] Fetching TD from {THINGS_ENDPOINT}/things/{THING_ID}...")
    resp = requests.get(f"{THINGS_ENDPOINT}/things/{THING_ID}", headers={"Accept": "application/td+json"})
    resp.raise_for_status()
    print("[Telemetry] TD successfully loaded.")
    return resp.json()

def run_mqtt_publisher():
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    planes = {
        "Plane1": {"flying": False}, "Plane2": {"flying": False},
        "Plane3": {"flying": False}, "Plane4": {"flying": True},
        "Plane5": {"flying": True}
    }
    gates = {
        "GateA1": {"occupied": True}, "GateA2": {"occupied": True},
        "GateB1": {"occupied": True}, "GateB2": {"occupied": False}
    }

    print("[Telemetry] Starting IoT sensor emulation...")
    try:
        while True:
            client.publish("telemetry/airport/telemetry/planes", json.dumps(planes))
            client.publish("telemetry/airport/telemetry/gates", json.dumps(gates))
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print("\n[Telemetry] Disconnected.")

if __name__ == '__main__':
    try:
        td = fetch_td()
        run_mqtt_publisher()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not fetch TD from OpenTwins platform: {e}")