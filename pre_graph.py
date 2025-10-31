from graphviz import Digraph

# Create directed graph
dot = Digraph(comment="LangGraph Workflow", format="pdf")

# Dynamic graph size
dot.attr(size="12,12")  # width,height in inches
dot.attr(ratio="expand")  # expand the canvas to fit nodes
dot.attr(splines="ortho")  # nicer edges
dot.attr(nodesep="0.8")  # space between nodes
dot.attr(ranksep="1.2")  # vertical space between ranks

# Top-to-bottom layout
# dot.attr(rankdir="TB", splines="ortho", nodesep="0.8", ranksep="1.2")
# =====================
# Clusters
# =====================


# Start node pinned at top
with dot.subgraph() as s:
    s.attr(rank="source")  # rank=source puts it at top
    s.node("__START__", shape="box", style="filled", color="lightgreen")

# End node pinned at bottom
with dot.subgraph() as e:
    e.attr(rank="sink")  # rank=sink puts it at bottom
    e.node("__END__", shape="box", style="filled", color="lightcoral")


# Cluster: PLANNER_AGENT (all nodes connecting to PLANNER_AGENT)
with dot.subgraph(
    name="cluster_PLANNER_AGENT"
) as PLANNER_AGENT:  # <-- must start with cluster_
    PLANNER_AGENT.attr(label="PLANNER", style="filled", color="lightyellow")

    # Main PLANNER_AGENT node
    PLANNER_AGENT.node("PLANNER_PIPE", "PLANNER_PIPE")
    PLANNER_AGENT.node("PLANNER_AGENT", "PLANNER_AGENT")

    grey_nodes = [
        "_ncompl_",
        "_hcut_",
        "_scut_",
        "_int_p_",
        "_dir_",
        "_ultdir_",
        "_nint_p",
    ]
    for n in grey_nodes:
        PLANNER_AGENT.node(
            n, label=n.strip("_"), style="filled", fillcolor="lightgrey"
        )

    # Other nodes (optional)
    PLANNER_AGENT.node("lphrase", "lphrase")
    PLANNER_AGENT.node("accumulate", "accumulate")


# Pipeline cluster
with dot.subgraph(name="cluster_pipeline") as pipeline:
    pipeline.attr(
        label="PIPELINE", style="filled", color="lightgreen", labelloc="t"
    )
    pipeline.node(
        "MULTIAGENT", "MULTIAGENT", style="filled", fillcolor="white"
    )
    pipeline.node("PEER", "PEER", style="filled", fillcolor="white")
    pipeline.node("PIPE", "PIPE", style="filled", fillcolor="white")
    pipeline.node("AMNGR", "AMNGR", style="filled", fillcolor="white")
    pipeline.node(
        "*MEMORY*", "*MEMORY*", style="filled", fillcolor="lightblue"
    )
    pipeline.node(
        "ORCHESTRATOR", "ORCHESTRATOR", style="filled", fillcolor="lightblue"
    )

# TTS cluster
with dot.subgraph(name="cluster_TTS") as TTS:
    # TTS.attr(label="TTS", style="filled", color="lightpink", labelloc="t")
    TTS.node("TTS", "TTS", style="filled", fillcolor="white")
    TTS.node(
        "TTS Manager", "TTS Manager", style="filled", fillcolor="lightblue"
    )

    TTS.node("Player", "Player", style="filled", fillcolor="lightblue")

# STT cluster
with dot.subgraph(name="cluster_STT") as STT:
    # STT.attr(label="STT", style="filled", color="lightblue", labelloc="t")
    STT.node(
        "STT", "STT", style="filled", fillcolor="white"
    )  # node background
    # STT.node("STT Manager", "STT Manager", style="filled", fillcolor="white")
# =====================
# Edges
# =====================


# __START__ conditional edges
dot.edge("__START__", "PEER", color="red")
# dot.edge(
#     "STT",
#     "*MEMORY*",
#     style="dashed",
# )

# Edges PIPE

dot.edge("PEER", "STT", color="red")
dot.edge("ORCHESTRATOR", "*MEMORY*")
dot.edge("MULTIAGENT", "TTS Manager", color="red")

dot.edge("PIPE", "AMNGR")
dot.edge("PIPE", "ORCHESTRATOR", color="red")

dot.edge("ORCHESTRATOR", "AMNGR", color="red")
dot.edge("AMNGR", "MULTIAGENT", color="red")
dot.edge("PIPE", "PEER", dir="both")
dot.edge("PIPE", "STT")
dot.edge("STT", "PIPE", color="red")
dot.edge("PIPE", "TTS Manager", dir="both")

dot.edge("ORCHESTRATOR", "PLANNER_AGENT", color="red")


####

dot.edge("TTS Manager", "TTS", color="red")
dot.edge("TTS Manager", "Player", dir="both")

# Edges inside agent cluster
dot.edge("_nint_p", "lphrase")
dot.edge("lphrase", "AMNGR")
dot.edge("_scut_", "lphrase")
dot.edge("_hcut_", "__START__")
dot.edge("_ncompl_", "accumulate")
dot.edge("_int_p_", "accumulate")
dot.edge("accumulate", "*MEMORY*")
dot.edge("*MEMORY*", "PLANNER_AGENT")
dot.edge("_ultdir_", "AMNGR")
dot.edge("_dir_", "lphrase")
dot.edge("lphrase", "TTS Manager")

# PLANNER_AGENT conditional edges
dot.edge("PLANNER_PIPE", "PLANNER_AGENT")
dot.edge("PLANNER_AGENT", "_hcut_")
dot.edge("PLANNER_AGENT", "_scut_")
dot.edge("PLANNER_AGENT", "_ncompl_")
dot.edge("PLANNER_AGENT", "_int_p_")
dot.edge("PLANNER_AGENT", "_dir_")
dot.edge("PLANNER_AGENT", "_ultdir_")
dot.edge("PLANNER_AGENT", "_nint_p")

# AGENT -> __END__
dot.edge("TTS", "Player")
dot.edge("Player", "__END__", color="red")
dot.edge("__END__", "__START__", color="red")

# =====================
# Export to PDF
# =====================
dot.render("langgraph_clustered", view=True)
