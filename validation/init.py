import json
from pathlib import Path
from time import sleep
import requests
from rdflib import Graph, Literal, RDF, Namespace
from rdflib.namespace import XSD
from dotenv import load_dotenv
import os

load_dotenv()

THINGS_ENDPOINT = os.getenv("OTV2_THINGS_URL")
TWINS_ENDPOINT = os.getenv("OTV2_TWINS_URL")

def removeAndInitDB():
    resp = requests.delete(TWINS_ENDPOINT + "/graphdb/all")
    try:
        resp.raise_for_status()
        #print("[INFO] Successfully deleted all db:", resp.json())
    except requests.HTTPError as e:
        print("[ERROR] Request failed:", e, resp.text)
        
    resp = requests.put(TWINS_ENDPOINT + "/graphdb/init")
    try:
        resp.raise_for_status()
        #print("[INFO] Successfully init schema:", resp.json())
    except requests.HTTPError as e:
        print("[ERROR] Request failed:", e, resp.text)
    return resp

def send_put(url, headers=None, json=None):
    resp = requests.put(url, headers=headers, json=json)
    try:
        resp.raise_for_status()
        #print("[INFO] Successfully sent")
    except requests.HTTPError as e:
        print("[ERROR] Request failed:", e, resp.text)
        
    return resp

def send_post(url, headers=None, json=None):
    resp = requests.post(url, headers=headers, json=json)
    try:
        resp.raise_for_status()
        #print("[INFO] Successfully sent:", resp.json())
    except requests.HTTPError as e:
        print("[ERROR] Request failed:", e, resp.text)
        
    return resp


def add_thing_to_twin(thingId):
    send_put(f"{TWINS_ENDPOINT}/twins/urn:test/things/{thingId}")

def post_thing(json_filename, add_id=""):
    json_path = Path(json_filename)
    if not json_path.exists():
        raise FileNotFoundError(f"File not found: {json_filename}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["id"] = data["id"] + add_id
    data["title"] = data["title"] + add_id
    if "otv2:subscribedEvents" in data and isinstance(data["otv2:subscribedEvents"], list) and len(data["otv2:subscribedEvents"]) > 0:
        data["otv2:subscribedEvents"] = [ {"otv2:event": data["otv2:subscribedEvents"][0]["otv2:event"] + add_id} ]
    if "otv2:rules" in data and isinstance(data["otv2:rules"], dict):
    # Accedemos directamente a "update" (ya que siempre está ahí)
        if "update" in data["otv2:rules"]:
            update_node = data["otv2:rules"]["update"]
            
            # Verificamos la ruta completa hacia el array de "=="
            if "otv2:if" in update_node and "==" in update_node["otv2:if"]:
                condition = update_node["otv2:if"]["=="]
                
                # Aseguramos que sea una lista y tenga al menos 2 elementos
                if isinstance(condition, list) and len(condition) > 1:
                    # Concatenamos el add_id directamente en el índice 1
                    condition[1] = f"{condition[1]}{add_id}"

    url = f"{THINGS_ENDPOINT}/things"
    headers = {"Content-Type": "application/json"}
    send_post(url, headers=headers, json=data)
    print(f"[INFO] Successfully posted thing: {data['id']}")
    
    return data["id"]

def prepare_base():
    
    removeAndInitDB()
    
    listId = []
    # Web of things
    listId.append(post_thing("thingDescriptions/domain-gate.json", "A1"))
    listId.append(post_thing("thingDescriptions/domain-gate.json", "A2"))
    listId.append(post_thing("thingDescriptions/domain-gate.json", "B1"))
    listId.append(post_thing("thingDescriptions/domain-gate.json", "B2"))
    listId.append(post_thing("thingDescriptions/domain-terminalA.json"))
    listId.append(post_thing("thingDescriptions/domain-terminalB.json"))
    listId.append(post_thing("thingDescriptions/domain-airport.json"))

    for i in range(1, 6):
        listId.append(post_thing("thingDescriptions/domain-plane.json", str(i)))
    
    listId.append(post_thing("thingDescriptions/resource-fmi.json"))
    listId.append(post_thing("thingDescriptions/resource-ml.json"))
    listId.append(post_thing("thingDescriptions/resource-telemetry.json"))

    # Create twin
    send_post(f"{TWINS_ENDPOINT}/twins/urn:test")
    add_thing_to_twin(",".join(listId))
    sleep(10)  # Wait for the twin to be updated
    #print(listId)



