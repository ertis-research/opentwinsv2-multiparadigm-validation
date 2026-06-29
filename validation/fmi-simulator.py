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
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
THING_ID = "urn:test:ops:airport-fmi-fuel"

def fetch_td():
    print(f"[FMI Mock] Fetching TD from {THINGS_ENDPOINT}/things/{THING_ID}...")
    resp = requests.get(f"{THINGS_ENDPOINT}/things/{THING_ID}", headers={"Accept": "application/td+json"})
    resp.raise_for_status()
    print("[FMI Mock] TD successfully loaded.")
    return resp.json()

def run_mqtt_publisher():
    client = mqtt.Client()
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    remaining_fuel_minutes = 45.0
    print("[FMI Mock] Starting thermodynamic fuel simulation...")
    try:
        while True:
            burn_rate = 1.5 
            remaining_fuel_minutes = max(0.0, remaining_fuel_minutes - burn_rate)
            client.publish("airport/fmi/fuel", json.dumps({"remainingMinutes": round(remaining_fuel_minutes, 2)}))
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print("\n[FMI Mock] Disconnected.")

if __name__ == '__main__':
    try:
        td = fetch_td()
        run_mqtt_publisher()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not fetch TD from OpenTwins platform: {e}")