import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import networkx as nx
import numpy as np
import json
import os
import re
import textwrap
from collections import defaultdict

# --------------------------------------------------------------------------
# Predicados que conectan un "Domain thing" con un "Resource thing"
# (telemetry / fmi simulation / ml model). Se aceptan con y sin prefijo otv2.
# --------------------------------------------------------------------------
RESOURCE_PREDICATES = {
    "hasTelemetry": "Telemetry",
    "otv2:hasTelemetry": "Telemetry",
    "hasFMISimulation": "FMI",
    "otv2:hasFMISimulation": "FMI",
    "hasMLModel": "ML",
    "otv2:hasMLModel": "ML",
}

HIERARCHY_PREDICATE = "hasChild"
NAME_KEY = "name"
IGNORE_KEYS = {"@id", "@type", NAME_KEY, "createdAt", "lastUpdate"}


def short_id(uri):
    """Se queda con la parte final del @id (urn:test:Plane1 -> Plane1)."""
    return uri.split(":")[-1].split("/")[-1]


def get_color(node_id, node_kind):
    """Colores IEEE-friendly, color-blind safe."""
    if node_kind == "resource":
        return "#C9B8E8"  # lila para los Resource things
    if "Airport" in node_id:
        return "#D06D6D"
    elif "Terminal" in node_id:
        return "#B7D8A9"
    elif "Gate" in node_id:
        return "#F2C97D"
    elif "Plane" in node_id:
        return "#7DA3C8"
    return "#CCCCCC"


def pretty_label(raw_label):
    """Inserta saltos de linea / espacios tipo 'GateA1' -> 'Gate\nA1'."""
    label = re.sub(r"^(Gate|Plane|Terminal)([A-Z]?[0-9]+)$", r"\1 \2", raw_label)
    label = re.sub(r"^(Gate|Plane)([0-9]+)$", r"\1 \2", label)
    label = re.sub(r"^(Terminal|Gate|Plane)([A-Z])$", r"\1 \2", label)
    parts = label.split()
    if len(parts) == 2:
        return f"{parts[0]}\n{parts[1]}"
    return label


def load_jsonld(fname):
    """
    Carga un archivo JSON-LD con forma {"@context":..., "@graph":[...]}
    y devuelve:
      - nodes: dict id -> {"name": str, "kind": "domain"/"resource"}
      - hierarchy_edges: lista de (parent, child) via hasChild
      - resource_edges: lista de (domain_node, resource_node, resource_type)
    """
    with open(fname, "r", encoding="utf-8") as f:
        data = json.load(f)

    graph_entries = data.get("@graph", data if isinstance(data, list) else [])

    nodes = {}
    hierarchy_edges = []
    resource_edges = []

    # Primero registramos todos los sujetos como "domain" por defecto
    for entry in graph_entries:
        node_id = entry.get("@id")
        if node_id is None:
            continue
        name = entry.get(NAME_KEY, short_id(node_id))
        nodes.setdefault(node_id, {"name": name, "kind": "domain"})

    # Luego recorremos predicados para sacar jerarquia y recursos,
    # y marcamos como "resource" cualquier nodo que sea destino de un
    # predicado de tipo hasTelemetry/hasFMISimulation/hasMLModel.
    for entry in graph_entries:
        subj = entry.get("@id")
        if subj is None:
            continue
        for key, value in entry.items():
            if key in IGNORE_KEYS or key == "@graph":
                continue

            # Normalizamos el valor a una lista de referencias {"@id": ...}
            if isinstance(value, dict) and "@id" in value:
                refs = [value]
            elif isinstance(value, list):
                refs = [v for v in value if isinstance(v, dict) and "@id" in v]
            else:
                continue

            if key == HIERARCHY_PREDICATE:
                for ref in refs:
                    child_id = ref["@id"]
                    nodes.setdefault(child_id, {"name": short_id(child_id), "kind": "domain"})
                    hierarchy_edges.append((subj, child_id))

            elif key in RESOURCE_PREDICATES:
                rtype = RESOURCE_PREDICATES[key]
                for ref in refs:
                    res_id = ref["@id"]
                    res_name = res_id
                    # buscamos el "name" real del recurso si esta en el grafo
                    for e2 in graph_entries:
                        if e2.get("@id") == res_id and NAME_KEY in e2:
                            res_name = e2[NAME_KEY]
                            break
                    nodes[res_id] = {"name": res_name, "kind": "resource", "rtype": rtype}
                    resource_edges.append((subj, res_id, rtype))

    return nodes, hierarchy_edges, resource_edges


def hierarchy_pos(G, root, width=1.0, vert_gap=0.34, vert_loc=0, xcenter=0.0):
    """Layout jerarquico clasico (recursivo) basado solo en hasChild."""
    pos = {}
    children = list(G.successors(root))
    if not children:
        pos[root] = (xcenter, vert_loc)
    else:
        dx = width / len(children)
        nextx = xcenter - width / 2 - dx / 2
        for child in children:
            nextx += dx
            pos.update(hierarchy_pos(G, child, width=dx, vert_gap=vert_gap,
                                      vert_loc=vert_loc - vert_gap, xcenter=nextx))
        pos[root] = (xcenter, vert_loc)
    return pos


def build_layout(nodes, hierarchy_edges, resource_edges):
    """
    Construye una posicion coherente para todos los nodos:
      - fila 0: Airport (raiz)
      - fila 1: Terminales
      - fila 2: Gates (y cualquier otro hijo directo de Terminal)
      - fila 3: Plane* alineados, centrados
      - Resource things (Telemetry / FMI / ML): se colocan a la altura
        (mismo nivel "y") de los Domain things que los usan, desplazados
        a la derecha del diagrama, para que las lineas que los conectan
        sean cortas y horizontales y se entiendan mejor.
    """
    H = nx.DiGraph()
    H.add_edges_from(hierarchy_edges)

    domain_ids = [n for n, attrs in nodes.items() if attrs["kind"] == "domain"]
    resource_ids = [n for n, attrs in nodes.items() if attrs["kind"] == "resource"]

    # nodos de avion: los que contienen "Plane" en el id y no estan en la jerarquia
    plane_ids = sorted([n for n in domain_ids if "Plane" in n],
                        key=lambda x: short_id(x))

    tree_nodes = [n for n in domain_ids if n not in plane_ids]
    for n in tree_nodes:
        if n not in H:
            H.add_node(n)

    pos = {}

    # raiz: nodo de la jerarquia sin padres entrantes (p.ej. Airport)
    roots = [n for n in tree_nodes if H.in_degree(n) == 0]
    root = roots[0] if roots else (tree_nodes[0] if tree_nodes else None)

    if root is not None:
        pos.update(hierarchy_pos(H, root, width=max(1.4, 0.6 * len(tree_nodes))))

    # Reescalamos el eje X de la jerarquia para tener referencia de ancho
    if pos:
        xs = [p[0] for p in pos.values()]
        x_min, x_max = min(xs), max(xs)
    else:
        x_min, x_max = -0.5, 0.5

    # --- fila de aviones, debajo de la jerarquia, centrada, con mas separacion ---
    if plane_ids:
        n_planes = len(plane_ids)
        plane_width = max(x_max - x_min, 0.4)
        spacing = plane_width / max(n_planes - 1, 1) if n_planes > 1 else 0
        start_x = (x_min + x_max) / 2 - (plane_width / 2 if n_planes > 1 else 0)
        plane_y = (min(p[1] for p in pos.values()) if pos else 0) - 0.42
        for idx, pid in enumerate(plane_ids):
            px = start_x + idx * spacing if n_planes > 1 else (x_min + x_max) / 2
            pos[pid] = (px, plane_y)

    # --- Resource things: mismo nivel "y" que sus Domain things asociados ---
    if resource_ids:
        res_to_domains = defaultdict(list)
        for (s, r, _t) in resource_edges:
            res_to_domains[r].append(s)

        all_x = [p[0] for p in pos.values()] if pos else [0.0]
        right_edge = max(all_x) if all_x else 0.5

        # contador de cuantos recursos ya se han colocado a cada altura,
        # para apilarlos horizontalmente sin que se monten unos con otros
        level_counts = defaultdict(int)

        for rid in sorted(resource_ids, key=lambda x: short_id(x)):
            domains = [d for d in res_to_domains.get(rid, []) if d in pos]
            if domains:
                ry = sum(pos[d][1] for d in domains) / len(domains)
            else:
                ry = (min(p[1] for p in pos.values()) if pos else 0) - 0.42

            level_key = round(ry, 2)
            count = level_counts[level_key]
            rx = right_edge + 0.55 + count * 0.85
            pos[rid] = (rx, ry)
            level_counts[level_key] += 1

    return pos


def draw_scenario(ax, fname, idx):
    ax.set_facecolor("white")

    if not os.path.exists(fname):
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"Scenario {idx + 1}", fontsize=15, fontweight="bold")
        return

    nodes, hierarchy_edges, resource_edges = load_jsonld(fname)
    pos = build_layout(nodes, hierarchy_edges, resource_edges)

    G_draw = nx.DiGraph()
    G_draw.add_nodes_from(nodes.keys())
    G_draw.add_edges_from(hierarchy_edges)
    res_edge_list = [(s, r) for (s, r, _t) in resource_edges]
    G_draw.add_edges_from(res_edge_list)

    node_colors = [get_color(n, nodes[n]["kind"]) for n in G_draw.nodes]
    node_shapes_domain = [n for n in G_draw.nodes if nodes[n]["kind"] == "domain"]
    node_shapes_resource = [n for n in G_draw.nodes if nodes[n]["kind"] == "resource"]

    labels = {}
    for n in G_draw.nodes:
        if nodes[n]["kind"] == "resource":
            labels[n] = textwrap.fill(nodes[n]["name"], width=9)
        else:
            labels[n] = pretty_label(nodes[n]["name"])

    # --- nodos: circulos para Domain things, cuadrados para Resource things ---
    nx.draw_networkx_nodes(G_draw, pos, ax=ax, nodelist=node_shapes_domain,
                            node_color=[get_color(n, "domain") for n in node_shapes_domain],
                            node_shape="o", node_size=1700,
                            edgecolors="#666666", linewidths=1.5)
    nx.draw_networkx_nodes(G_draw, pos, ax=ax, nodelist=node_shapes_resource,
                            node_color=[get_color(n, "resource") for n in node_shapes_resource],
                            node_shape="s", node_size=2600,
                            edgecolors="#444444", linewidths=1.5)

    # --- aristas jerarquicas (hasChild), solidas ---
    nx.draw_networkx_edges(G_draw, pos, ax=ax, edgelist=hierarchy_edges,
                            arrows=True, arrowstyle="->", width=1.5,
                            alpha=0.8, edge_color="#333333")

    # --- aristas hacia Resource things, discontinuas ---
    nx.draw_networkx_edges(G_draw, pos, ax=ax, edgelist=res_edge_list,
                            arrows=True, arrowstyle="->", width=1.1,
                            alpha=0.6, edge_color="#8866AA", style="dashed",
                            connectionstyle="arc3,rad=0.08")

    nx.draw_networkx_labels(G_draw, pos, labels={n: l for n, l in labels.items() if nodes[n]["kind"] == "domain"},
                             ax=ax, font_size=9, font_weight="bold")
    nx.draw_networkx_labels(G_draw, pos, labels={n: l for n, l in labels.items() if nodes[n]["kind"] == "resource"},
                             ax=ax, font_size=7.5, font_weight="bold")

    pos_values = np.array(list(pos.values()))
    ax.set_xlim(pos_values[:, 0].min() - 0.45, pos_values[:, 0].max() + 0.45)
    ax.set_ylim(pos_values[:, 1].min() - 0.40, pos_values[:, 1].max() + 0.40)

    # --- Subtitulo: resultado esperado vs. razonado (collapsed / not collapsed) ---
    if idx == 0:
        subtitle = "Expected: Not Collapsed   |   Reasoned: Not Collapsed"
    else:
        subtitle = "Expected: Collapsed   |   Reasoned: Collapsed"

    ax.set_title(f"Scenario {idx + 1}", fontsize=15, pad=34, fontweight="bold")
    ax.text(0.5, 1.055, subtitle, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=9.5, style="italic", color="#333333")
    for spine in ax.spines.values():
        spine.set_edgecolor("black")
        spine.set_linewidth(2)
    ax.set_xticks([])
    ax.set_yticks([])


def visualize_all_graphs_paper_ready():
    """
    Carga esc1.jsonld ... esc4.jsonld y los dibuja en un grid 2x2.
    Distingue visualmente:
      - Domain things (Airport/Terminal/Gate/Plane): circulos coloreados
        por tipo, organizados jerarquicamente (hasChild) con los aviones
        alineados debajo.
      - Resource things (Telemetry/FMI/ML): cuadrados lilas alineados en
        la fila inferior, conectados mediante aristas discontinuas a los
        Domain things que los usan.
    """
    fig, axes = plt.subplots(2, 2, figsize=(13, 13), facecolor="white")
    axes = axes.flatten()
    filenames = [f"output/esc{i}.jsonld" for i in range(1, 5)]

    for i, fname in enumerate(filenames):
        draw_scenario(axes[i], fname, i)

    # --- Leyenda comun, agrupada por secciones ---
    blank = mlines.Line2D([], [], color="none", label="")
    legend_handles = [
        mlines.Line2D([], [], color="none", label="Domain Things:"),
        mpatches.Patch(facecolor="#D06D6D", edgecolor="#666666", label="Airport"),
        mpatches.Patch(facecolor="#B7D8A9", edgecolor="#666666", label="Terminal"),
        mpatches.Patch(facecolor="#F2C97D", edgecolor="#666666", label="Gate"),
        mpatches.Patch(facecolor="#7DA3C8", edgecolor="#666666", label="Plane"),
        mlines.Line2D([], [], color="none", label="Resource Things:"),
        mlines.Line2D([], [], marker="s", linestyle="None", markersize=12,
                       markerfacecolor="#C9B8E8", markeredgecolor="#444444",
                       label="Telemetry / FMI / ML"),
        blank,
        mlines.Line2D([], [], color="none", label="Relations:"),
        mlines.Line2D([], [], color="#333333", linewidth=1.5, label="hasChild"),
        mlines.Line2D([], [], color="#8866AA", linewidth=1.1, linestyle="dashed",
                       label="hasTelemetry / hasFMISimulation / hasMLModel"),
    ]
    legend = fig.legend(handles=legend_handles, loc="lower center", ncol=3,
                         frameon=False, fontsize=9, handlelength=2.0,
                         bbox_to_anchor=(0.5, -0.06))
    header_labels = {"Domain Things:", "Resource Things:", "Relations:"}
    for text in legend.get_texts():
        if text.get_text() in header_labels:
            text.set_fontweight("bold")

    plt.tight_layout()
    plt.rcParams["text.usetex"] = False
    plt.rcParams["font.size"] = 11
    plt.rcParams["font.family"] = "sans-serif"
    plt.subplots_adjust(wspace=0.30, hspace=0.35)
    plt.savefig("output/rq2_graphs_paper.pdf", dpi=600,
                bbox_inches="tight", facecolor="white")
    print("[INFO] Image 'rq2_graphs_paper.pdf' successfully generated.")


if __name__ == "__main__":
    visualize_all_graphs_paper_ready()