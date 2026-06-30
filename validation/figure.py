import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import networkx as nx
import numpy as np
import os
import re
import textwrap
from collections import defaultdict
from rdflib import Graph, Namespace

# --------------------------------------------------------------------------
# Predicados y Namespaces
# --------------------------------------------------------------------------
NS1 = Namespace("http://example.org/")
NS2 = Namespace("http://example.org/otv2:")

RESOURCE_PREDICATES = {
    str(NS2.hasTelemetry): "Telemetry",
    str(NS2.hasFMISimulation): "FMI",
    str(NS2.hasMLModel): "ML",
}

HIERARCHY_PREDICATE = str(NS2.hasChild)
ASSIGNED_TO_PREDICATE = str(NS2.assignedTo)

PROPERTY_PREDICATES = {
    str(NS1["collapsed.value"]): "coll",
    str(NS1["occupied.value"]): "occ",
    str(NS1["flying.value"]): "fly"
}


def short_id(uri):
    """Se queda con la parte final del URI (urn:test:Plane1 -> Plane1)."""
    return str(uri).split(":")[-1].split("/")[-1]


def is_domain(node_id):
    """Determina si un nodo es de dominio en base a su ID."""
    return any(k in node_id for k in ["Airport", "Terminal", "Gate", "Plane"])


def get_color(node_id, node_kind):
    """Colores IEEE-friendly, color-blind safe."""
    if node_kind == "resource":
        return "#C9B8E8"  # Lila
    if "Airport" in node_id:
        return "#D06D6D"
    elif "Terminal" in node_id:
        return "#B7D8A9"
    elif "Gate" in node_id:
        return "#F2C97D"
    elif "Plane" in node_id:
        return "#7DA3C8"
    return "#CCCCCC"


def pretty_label(raw_label, props=None):
    """Inserta saltos de línea e incluye las propiedades físicas."""
    label = re.sub(r"^(Gate|Plane|Terminal)([A-Z]?[0-9]+)$", r"\1 \2", raw_label)
    label = re.sub(r"^(Gate|Plane)([0-9]+)$", r"\1 \2", label)
    label = re.sub(r"^(Terminal|Gate|Plane)([A-Z])$", r"\1 \2", label)
    parts = label.split()
    
    if len(parts) == 2:
        final_label = f"{parts[0]}\n{parts[1]}"
    else:
        final_label = label
        
    if props:
        props_str = ", ".join([f"{k}: {v}" for k, v in props.items()])
        final_label += f"\n({props_str})"
        
    return final_label


def load_ttl(fname):
    g = Graph()
    g.parse(fname, format="turtle")

    nodes = {}
    hierarchy_edges = []
    resource_edges = set()
    assigned_edges = []

    for s in g.subjects(unique=True):
        s_id = str(s)
        kind = "domain" if is_domain(s_id) else "resource"
        nodes[s_id] = {"name": short_id(s_id), "kind": kind, "props": {}}

    for s, p, o in g:
        s_id = str(s)
        p_id = str(p)
        o_id = str(o)

        if p_id == str(NS1.name):
            nodes[s_id]["name"] = str(o)
            continue
            
        if p_id in PROPERTY_PREDICATES:
            prop_abbr = PROPERTY_PREDICATES[p_id]
            val = str(o).lower() if isinstance(o.toPython(), bool) else str(o)
            nodes[s_id]["props"][prop_abbr] = val
            continue

        if p_id == HIERARCHY_PREDICATE:
            hierarchy_edges.append((s_id, o_id))
            if o_id not in nodes:
                nodes[o_id] = {"name": short_id(o_id), "kind": "domain", "props": {}}
            continue
            
        if p_id == ASSIGNED_TO_PREDICATE:
            assigned_edges.append((s_id, o_id))
            continue

        if p_id in RESOURCE_PREDICATES:
            rtype = RESOURCE_PREDICATES[p_id]
            if is_domain(s_id) and not is_domain(o_id):
                resource_edges.add((s_id, o_id, rtype))
            elif is_domain(o_id) and not is_domain(s_id):
                resource_edges.add((o_id, s_id, rtype))

    return nodes, hierarchy_edges, list(resource_edges), assigned_edges


def hierarchy_pos(G, root, width=1.0, vert_gap=0.34, vert_loc=0, xcenter=0.0):
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
    H = nx.DiGraph()
    H.add_edges_from(hierarchy_edges)

    domain_ids = [n for n, attrs in nodes.items() if attrs["kind"] == "domain"]
    resource_ids = [n for n, attrs in nodes.items() if attrs["kind"] == "resource"]

    plane_ids = sorted([n for n in domain_ids if "Plane" in n], key=lambda x: short_id(x))
    tree_nodes = [n for n in domain_ids if n not in plane_ids]
    
    for n in tree_nodes:
        if n not in H:
            H.add_node(n)

    pos = {}
    roots = [n for n in tree_nodes if H.in_degree(n) == 0]
    root = roots[0] if roots else (tree_nodes[0] if tree_nodes else None)

    if root is not None:
        pos.update(hierarchy_pos(H, root, width=max(1.4, 0.6 * len(tree_nodes))))

    if pos:
        xs = [p[0] for p in pos.values()]
        x_min, x_max = min(xs), max(xs)
    else:
        x_min, x_max = -0.5, 0.5

    # Fila de aviones
    if plane_ids:
        n_planes = len(plane_ids)
        plane_width = max(x_max - x_min, 0.4)
        spacing = plane_width / max(n_planes - 1, 1) if n_planes > 1 else 0
        start_x = (x_min + x_max) / 2 - (plane_width / 2 if n_planes > 1 else 0)
        plane_y = (min(p[1] for p in pos.values()) if pos else 0) - 0.70
        for idx, pid in enumerate(plane_ids):
            px = start_x + idx * spacing if n_planes > 1 else (x_min + x_max) / 2
            pos[pid] = (px, plane_y)

    # Resource things
    if resource_ids:
        res_to_domains = defaultdict(list)
        for (s, r, _t) in resource_edges:
            res_to_domains[r].append(s)

        all_x = [p[0] for p in pos.values()] if pos else [0.0]
        right_edge = max(all_x) if all_x else 0.5

        level_counts = defaultdict(int)

        for rid in sorted(resource_ids, key=lambda x: short_id(x)):
            domains = [d for d in res_to_domains.get(rid, []) if d in pos]
            if domains:
                ry = (sum(pos[d][1] for d in domains) / len(domains)) - 0.35
            else:
                ry = (min(p[1] for p in pos.values()) if pos else 0) - 0.60
                
            if "ml" in rid.lower():
                ry += 0.25

            level_key = round(ry, 2)
            count = level_counts[level_key]
            rx = right_edge + 0.65 + count * 0.90
            pos[rid] = (rx, ry)
            level_counts[level_key] += 1

    return pos


def draw_scenario(ax, fname, idx):
    ax.set_facecolor("white")

    if not os.path.exists(fname):
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        # Ajuste de margen mínimo para casos "No data"
        ax.set_title(f"Scenario {idx + 1}", fontsize=15, pad=18, fontweight="bold")
        return

    nodes, hierarchy_edges, resource_edges, assigned_edges = load_ttl(fname)
    pos = build_layout(nodes, hierarchy_edges, resource_edges)

    G_draw = nx.DiGraph()
    G_draw.add_nodes_from(nodes.keys())
    G_draw.add_edges_from(hierarchy_edges)
    
    res_edge_list = [(s, r) for (s, r, _t) in resource_edges]
    G_draw.add_edges_from(res_edge_list)
    G_draw.add_edges_from(assigned_edges)

    node_shapes_domain = [n for n in G_draw.nodes if nodes[n]["kind"] == "domain"]
    node_shapes_resource = [n for n in G_draw.nodes if nodes[n]["kind"] == "resource"]

    labels = {}
    for n in G_draw.nodes:
        if nodes[n]["kind"] == "resource":
            labels[n] = textwrap.fill(nodes[n]["name"], width=10)
        else:
            labels[n] = pretty_label(nodes[n]["name"], nodes[n].get("props", {}))

    nx.draw_networkx_nodes(G_draw, pos, ax=ax, nodelist=node_shapes_domain,
                           node_color=[get_color(n, "domain") for n in node_shapes_domain],
                           node_shape="o", node_size=2300,
                           edgecolors="#666666", linewidths=1.5)
                           
    nx.draw_networkx_nodes(G_draw, pos, ax=ax, nodelist=node_shapes_resource,
                           node_color=[get_color(n, "resource") for n in node_shapes_resource],
                           node_shape="s", node_size=3200,
                           edgecolors="#444444", linewidths=1.5)

    nx.draw_networkx_edges(G_draw, pos, ax=ax, edgelist=hierarchy_edges,
                           arrows=True, arrowstyle="->", width=1.5,
                           alpha=0.8, edge_color="#333333")

    nx.draw_networkx_edges(G_draw, pos, ax=ax, edgelist=res_edge_list,
                           arrows=True, arrowstyle="->", width=1.4,
                           alpha=0.4, edge_color="#8866AA", style="solid",
                           connectionstyle="arc3,rad=0.08")
                           
    nx.draw_networkx_edges(G_draw, pos, ax=ax, edgelist=assigned_edges,
                           arrows=True, arrowstyle="-|>", width=2.0,
                           alpha=1.0, edge_color="#FF5500", style="solid",
                           connectionstyle="arc3,rad=-0.15")

    nx.draw_networkx_labels(G_draw, pos, labels={n: l for n, l in labels.items() if nodes[n]["kind"] == "domain"},
                            ax=ax, font_size=8.5, font_weight="bold")
    nx.draw_networkx_labels(G_draw, pos, labels={n: l for n, l in labels.items() if nodes[n]["kind"] == "resource"},
                            ax=ax, font_size=8.0, font_weight="bold")

    pos_values = np.array(list(pos.values()))
    ax.set_xlim(pos_values[:, 0].min() - 0.45, pos_values[:, 0].max() + 0.45)
    ax.set_ylim(pos_values[:, 1].min() - 0.45, pos_values[:, 1].max() + 0.45)

    if idx == 0:
        subtitle = "Expected: Not Collapsed   |   Reasoned: Not Collapsed"
    else:
        subtitle = "Expected: Collapsed   |   Reasoned: Collapsed"

    # --- AJUSTE AQUÍ: pad=18 para acercar el título general y y=1.012 para el subtítulo ---
    ax.set_title(f"Scenario {idx + 1}", fontsize=15, pad=18, fontweight="bold")
    ax.text(0.5, 1.012, subtitle, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=9.5, style="italic", color="#333333")
            
    for spine in ax.spines.values():
        spine.set_edgecolor("black")
        spine.set_linewidth(2)
    ax.set_xticks([])
    ax.set_yticks([])


def visualize_all_graphs_paper_ready():
    fig, axes = plt.subplots(3, 2, figsize=(14, 18), facecolor="white")
    axes_flat = axes.flatten()
    
    filenames = [f"output/esc{i}.ttl" for i in range(1, 6)]

    for i, fname in enumerate(filenames):
        draw_scenario(axes_flat[i], fname, i)

    legend_ax = axes_flat[5]
    legend_ax.axis("off")

    blank = mlines.Line2D([], [], color="none", label=" ")

    legend_handles = [
        mlines.Line2D([], [], color="none", label="Domain Things:"),
        mpatches.Patch(facecolor="#D06D6D", edgecolor="#666666", label="Airport"),
        mpatches.Patch(facecolor="#B7D8A9", edgecolor="#666666", label="Terminal"),
        mpatches.Patch(facecolor="#F2C97D", edgecolor="#666666", label="Gate"),
        mpatches.Patch(facecolor="#7DA3C8", edgecolor="#666666", label="Plane"),
        
        blank,
        
        mlines.Line2D([], [], color="none", label="Resource Things:"),
        mlines.Line2D([], [], marker="s", linestyle="None", markersize=14,
                       markerfacecolor="#C9B8E8", markeredgecolor="#444444",
                       label="Telemetry/FMI/ML"),
                       
        blank,
        
        mlines.Line2D([], [], color="none", label="Relations:"),
        mlines.Line2D([], [], color="#333333", linewidth=1.5, label="hasChild"),
        mlines.Line2D([], [], color="#8866AA", linewidth=1.4, linestyle="solid", alpha=0.4,
                       label="resource"),
        mlines.Line2D([], [], color="#FF5500", linewidth=2.0, linestyle="solid",
                       label="assignedTo"),
    ]
    
    legend = legend_ax.legend(handles=legend_handles, loc="center", ncol=1,
                              frameon=True, edgecolor="#333333", borderpad=1.5,
                              labelspacing=0.8, fontsize=12, handlelength=2.5)
                              
    header_labels = {"Domain Things:", "Resource Things:", "Relations:"}
    for text in legend.get_texts():
        if text.get_text() in header_labels:
            text.set_fontweight("bold")

    plt.tight_layout()
    plt.rcParams["text.usetex"] = False
    plt.rcParams["font.family"] = "sans-serif"
    
    plt.subplots_adjust(wspace=0.05, hspace=0.15)
    
    plt.savefig("output/graphs_paper.pdf", dpi=600,
                bbox_inches="tight", facecolor="white")
    print("[INFO] Image 'graphs_paper.pdf' successfully generated.")


if __name__ == "__main__":
    if not os.path.exists("output"):
        os.makedirs("output")
    visualize_all_graphs_paper_ready()