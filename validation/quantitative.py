import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_api_fetch_metrics(output_dir):
    """
    Reads the performance_metrics.csv and generates a standalone bar chart
    showing the API Fetch Time.
    """
    csv_path = os.path.join(output_dir, "performance_metrics.csv")
    if not os.path.exists(csv_path):
        print(f"[WARNING] Metrics CSV not found at {csv_path}.")
        return

    df_raw = pd.read_csv(csv_path)
    
    # Group by scenario and calculate the mean of all runs
    df = df_raw.groupby(["Scenario_ID", "Expected_Scenario"]).mean(numeric_only=True).reset_index()
    
    # Use the grouped dataframe to generate labels
    x_labels = [f"Scen. {row['Scenario_ID']}\n({row['Expected_Scenario']})" for _, row in df.iterrows()]

    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Plot API Fetch Time
    ax.bar(x_labels, df["API_Fetch_Time_ms"], color='steelblue', edgecolor='black', alpha=0.85)
    
    # Custom title in English as requested
    ax.set_title("Knowledge Graph Retrieval Performance", fontsize=14, fontweight='bold')
    ax.set_ylabel("Average Latency (ms)", fontsize=12)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()
    
    output_img = os.path.join(output_dir, "performance_latency.pdf")
    plt.savefig(output_img, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"[INFO] API Fetch metrics figure generated successfully: {output_img}")

def plot_granular_sparql_metrics(output_dir):
    """
    Reads the performance_metrics.csv and generates a stacked bar chart
    showing the individual execution times of each SPARQL query, 
    overlaying the average graph size on a secondary axis.
    """
    csv_path = os.path.join(output_dir, "performance_metrics.csv")
    if not os.path.exists(csv_path):
        print(f"[WARNING] Metrics CSV not found at {csv_path}.")
        return

    df_raw = pd.read_csv(csv_path)

    # Group by scenario and calculate the mean of all runs
    df = df_raw.groupby(["Scenario_ID", "Expected_Scenario"]).mean(numeric_only=True).reset_index()

    # Filter columns that represent SPARQL query times
    sparql_cols = [c for c in df.columns if c.startswith("SPARQL_") and c.endswith("_ms")]
    if not sparql_cols:
        print("[WARNING] No individual SPARQL time columns found in CSV.")
        return

    # Use the grouped dataframe to generate labels
    x_labels = [f"Scen. {row['Scenario_ID']}\n({row['Expected_Scenario']})" for _, row in df.iterrows()]

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bottom_offsets = [0] * len(df)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'] # Default palette
    
    # Plot a stacked bar for each query type
    for idx, col in enumerate(sparql_cols):
        # Clean up column name for the legend (e.g., "SPARQL_aerial_ms" -> "Aerial")
        query_name = col.replace("SPARQL_", "").replace("_ms", "").capitalize()
        
        ax.bar(x_labels, df[col], bottom=bottom_offsets, label=f"{query_name} Query", 
               color=colors[idx % len(colors)], edgecolor='black', alpha=0.85)
        
        # Add the current bar's height to the bottom_offsets for the next layer
        bottom_offsets = [b + val for b, val in zip(bottom_offsets, df[col])]

    ax.set_title("SPARQL Performance per Query", fontsize=14, fontweight='bold')
    ax.set_ylabel("Average Latency (ms)", fontsize=12)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    # --- NEW: Secondary axis for Graph Size ---
    ax2 = ax.twinx()
    # Plotting line with markers for the graph size
    ax2.plot(x_labels, df["Graph_Triples_Count"], color='black', marker='o', 
             linestyle='-', linewidth=2, markersize=7, label='Graph Size (Triples)')
    ax2.set_ylabel("Average Graph Size (Triples)", fontsize=12)

    # --- Adjust limits to prevent data overlapping with the legend ---
    max_latency = max(bottom_offsets) if bottom_offsets else 1
    ax.set_ylim(0, max_latency * 1.35)  # 35% extra space on top for latency
    
    max_triples = df["Graph_Triples_Count"].max()
    ax2.set_ylim(0, max_triples * 1.35) # 35% extra space on top for triples

    # --- Combine legends from both axes ---
    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    
    # Place combined legend in the upper right
    ax.legend(handles1 + handles2, labels1 + labels2, loc='upper right', framealpha=0.95)

    plt.tight_layout()
    
    output_img = os.path.join(output_dir, "performance_sparql.pdf")
    plt.savefig(output_img, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"[INFO] Granular SPARQL metrics figure generated successfully: {output_img}")