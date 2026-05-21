"""
merge_graphs.py — Merge Path A (graphify) + Path B (nuextract3) into a unified knowledge graph.

Inputs:
    --graphify-json   Path A graph.json from graphify
    --nuextract-json  Path B nuextract-output.json from nuextract_pipeline.py
    --output-dir      Directory to write merged-graph.json, merged-graph.html, merged-graph-summary.md

Usage:
    python scripts/merge_graphs.py \\
        --graphify-json "C:/Users/kaanchan/AppData/Local/Temp/ralph-test-slice/graphify-out/graph.json" \\
        --nuextract-json "r&d/1-find-offline-semantic-tool/responses/nuextract-output.json" \\
        --output-dir "r&d/1-find-offline-semantic-tool/responses/"

GH issue: #7 (ref #8)
"""

import json
import re
import argparse
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from extract_config import clean_output


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Normalize a label to a stable snake_case ID for deduplication."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "unknown"


def dominant_slug(slug: str, graphify_ids: set[str]) -> str | None:
    """Return the graphify node ID that best matches this slug, or None."""
    if slug in graphify_ids:
        return slug
    # Partial match: graphify IDs often have path prefixes
    for gid in graphify_ids:
        if slug in gid or gid.endswith(f"_{slug}"):
            return gid
    return None


# ── Load inputs ───────────────────────────────────────────────────────────────

def load_graphify(path: str) -> tuple[list[dict], list[dict]]:
    with open(path, encoding="utf-8") as f:
        g = json.load(f)
    return g["nodes"], g["links"]


def load_nuextract(path: str) -> tuple[list[dict], list[dict]]:
    with open(path, encoding="utf-8") as f:
        docs = json.load(f)
    entities, relations = [], []
    for doc in docs:
        src = Path(doc.get("source_file", "")).name
        for e in doc.get("entities", []):
            if e.get("name"):
                entities.append({**e, "_source_doc": src})
        for r in doc.get("relations", []):
            if r.get("subject") and r.get("predicate") and r.get("object"):
                relations.append({**r, "_source_doc": src})
    return entities, relations


# ── Merge ─────────────────────────────────────────────────────────────────────

def merge(graphify_nodes, graphify_links, nu_entities, nu_relations):
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    graphify_ids = {n["id"] for n in graphify_nodes}

    # ── Ingest graphify nodes (Path A — code structure) ───────────────────────
    for n in graphify_nodes:
        nodes[n["id"]] = {
            "id":            n["id"],
            "label":         n.get("label", n["id"]),
            "type":          n.get("file_type", "code"),
            "community":     n.get("community", -1),
            "source":        "graphify",
            "source_file":   n.get("source_file", ""),
            "source_location": n.get("source_location", ""),
        }

    # ── Ingest graphify edges ─────────────────────────────────────────────────
    for lnk in graphify_links:
        edges.append({
            "source":    lnk["source"],
            "target":    lnk["target"],
            "relation":  lnk.get("relation", "related"),
            "weight":    lnk.get("weight", 1.0),
            "layer":     "code",
            "source_file": lnk.get("source_file", ""),
        })

    # ── Ingest nuextract3 entities (Path B — prose semantics) ─────────────────
    # Assign separate community IDs starting above graphify's max
    max_community = max((n.get("community", 0) for n in graphify_nodes), default=0)
    doc_community: dict[str, int] = {}
    next_community = max_community + 1

    nu_id_map: dict[str, str] = {}   # original name → node ID used in merged graph

    for e in nu_entities:
        name = e["name"]
        slug = slugify(name)

        # Check if a graphify node already represents this concept
        matched = dominant_slug(slug, graphify_ids)
        if matched:
            # Fuse: enrich existing graphify node with semantic metadata
            nodes[matched]["label_semantic"] = name
            nodes[matched]["entity_type"]    = e.get("type", "")
            nodes[matched]["source"]         = "merged"
            nu_id_map[name] = matched
            continue

        # New concept from prose — add as a nuextract node
        if slug not in nodes:
            src_doc = e.get("_source_doc", "")
            if src_doc not in doc_community:
                doc_community[src_doc] = next_community
                next_community += 1
            nodes[slug] = {
                "id":          slug,
                "label":       name,
                "type":        e.get("type", "concept"),
                "community":   doc_community[src_doc],
                "source":      "nuextract3",
                "source_file": src_doc,
            }
        nu_id_map[name] = slug

    # ── Ingest nuextract3 relations ───────────────────────────────────────────
    for r in nu_relations:
        src_id = nu_id_map.get(r["subject"],  slugify(r["subject"]))
        tgt_id = nu_id_map.get(r["object"],   slugify(r["object"]))

        # Ensure both endpoints exist (object may not have been in entity list)
        for nid, label in [(src_id, r["subject"]), (tgt_id, r["object"])]:
            if nid not in nodes:
                src_doc = r.get("_source_doc", "")
                if src_doc not in doc_community:
                    doc_community[src_doc] = next_community
                    next_community += 1
                nodes[nid] = {
                    "id":          nid,
                    "label":       label,
                    "type":        "concept",
                    "community":   doc_community.get(src_doc, next_community),
                    "source":      "nuextract3",
                    "source_file": src_doc,
                }

        edges.append({
            "source":    src_id,
            "target":    tgt_id,
            "relation":  r["predicate"],
            "weight":    1.0,
            "layer":     "semantic",
            "source_file": r.get("_source_doc", ""),
        })

    return list(nodes.values()), edges


# ── Output: JSON ──────────────────────────────────────────────────────────────

def write_json(nodes, edges, output_dir: Path):
    out = {
        "meta": {
            "node_count": len(nodes),
            "edge_count":  len(edges),
            "layers":      ["code", "semantic"],
            "sources":     ["graphify", "nuextract3"],
        },
        "nodes": nodes,
        "edges": edges,
    }
    p = output_dir / "merged-graph.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


# ── Output: HTML (self-contained D3 force graph) ──────────────────────────────

def write_html(nodes, edges, output_dir: Path):
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)

    SOURCE_COLORS = {
        "graphify":  "#4e9af1",   # blue  — code structure
        "nuextract3": "#f5a623",  # orange — prose semantics
        "merged":    "#7ed321",   # green  — fused nodes
    }
    color_map_js = json.dumps(SOURCE_COLORS)

    # Build HTML via substitution to avoid f-string conflicts with JS curly braces.
    # Also un-escape {{ and }} left over from the original f-string template.
    html = _HTML_TEMPLATE \
        .replace("__NODES_JSON__", nodes_json) \
        .replace("__EDGES_JSON__", edges_json) \
        .replace("__COLOR_MAP_JS__", color_map_js) \
        .replace("{{", "{") \
        .replace("}}", "}")

    p = output_dir / "merged-graph.html"
    p.write_text(html, encoding="utf-8")
    return p


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Merged Knowledge Graph</title>
<style>
  body {{ margin: 0; background: #0f1117; color: #e0e0e0; font-family: monospace; }}
  #graph {{ width: 100vw; height: 100vh; }}
  .tooltip {{
    position: absolute; background: rgba(0,0,0,0.85); color: #fff;
    padding: 8px 12px; border-radius: 6px; font-size: 12px;
    pointer-events: none; max-width: 280px; line-height: 1.5;
  }}
  #legend {{
    position: absolute; top: 16px; left: 16px;
    background: rgba(0,0,0,0.7); padding: 10px 14px; border-radius: 8px;
    font-size: 12px; line-height: 2;
  }}
  #stats {{
    position: absolute; top: 16px; right: 16px;
    background: rgba(0,0,0,0.7); padding: 10px 14px; border-radius: 8px;
    font-size: 12px; line-height: 1.8;
  }}
  .legend-dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }}
</style>
</head>
<body>
<div id="graph"></div>
<div class="tooltip" id="tooltip" style="display:none"></div>
<div id="legend">
  <b>Node Source</b><br>
  <span class="legend-dot" style="background:#4e9af1"></span>graphify (code)<br>
  <span class="legend-dot" style="background:#f5a623"></span>nuextract3 (prose)<br>
  <span class="legend-dot" style="background:#7ed321"></span>merged (both)<br>
  <br><b>Edge Layer</b><br>
  <span style="color:#4e9af1">━━</span> code structure<br>
  <span style="color:#f5a623">━━</span> semantic relation
</div>
<div id="stats" id="stats"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const nodes = __NODES_JSON__;
const edges = __EDGES_JSON__;
const colorMap = __COLOR_MAP_JS__;

// Stats panel
const bySource = {{}};
nodes.forEach(n => bySource[n.source] = (bySource[n.source]||0)+1);
const byLayer = {{}};
edges.forEach(e => byLayer[e.layer] = (byLayer[e.layer]||0)+1);
document.getElementById('stats').innerHTML =
  '<b>Graph Stats</b><br>' +
  'Nodes: ' + nodes.length + '<br>' +
  'Edges: ' + edges.length + '<br>' +
  Object.entries(bySource).map(function(kv){return '&nbsp;'+kv[0]+': '+kv[1];}).join('<br>') + '<br>' +
  Object.entries(byLayer).map(function(kv){return '&nbsp;'+kv[0]+' edges: '+kv[1];}).join('<br>');

const width = window.innerWidth, height = window.innerHeight;
const svg = d3.select('#graph').append('svg')
  .attr('width', width).attr('height', height);

// Arrow markers
const defs = svg.append('defs');
['code','semantic'].forEach(layer => {{
  defs.append('marker')
    .attr('id','arrow-'+layer)
    .attr('viewBox','0 -4 8 8').attr('refX',18).attr('refY',0)
    .attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto')
    .append('path').attr('d','M0,-4L8,0L0,4')
    .attr('fill', layer==='code' ? '#4e9af1' : '#f5a623').attr('opacity',0.7);
}});

const g = svg.append('g');

// Zoom
svg.call(d3.zoom().scaleExtent([0.1,6])
  .on('zoom', e => g.attr('transform', e.transform)));

// Degree map for node sizing
const degree = {{}};
edges.forEach(e => {{
  degree[e.source] = (degree[e.source]||0)+1;
  degree[e.target] = (degree[e.target]||0)+1;
}});

const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(edges).id(d=>d.id).distance(80).strength(0.4))
  .force('charge', d3.forceManyBody().strength(-180))
  .force('center', d3.forceCenter(width/2, height/2))
  .force('collision', d3.forceCollide().radius(d => nodeRadius(d)+4));

function nodeRadius(d) {{ return 5 + Math.min((degree[d.id]||0)*2, 20); }}

const link = g.append('g').selectAll('line').data(edges).join('line')
  .attr('stroke', d => d.layer==='code' ? '#4e9af1' : '#f5a623')
  .attr('stroke-opacity', 0.5).attr('stroke-width', 1.2)
  .attr('marker-end', d => 'url(#arrow-'+d.layer+')');

const node = g.append('g').selectAll('circle').data(nodes).join('circle')
  .attr('r', nodeRadius)
  .attr('fill', d => colorMap[d.source] || '#888')
  .attr('stroke', '#fff').attr('stroke-width', 0.5)
  .attr('cursor','pointer')
  .call(d3.drag()
    .on('start', (e,d) => {{ if(!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
    .on('drag',  (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
    .on('end',   (e,d) => {{ if(!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }}));

const label = g.append('g').selectAll('text').data(nodes).join('text')
  .text(d => d.label.length > 20 ? d.label.slice(0,18)+'…' : d.label)
  .attr('font-size', 9).attr('fill','#ccc').attr('text-anchor','middle')
  .attr('dy', d => -nodeRadius(d)-3).attr('pointer-events','none');

const tooltip = document.getElementById('tooltip');
node.on('mouseover', (e,d) => {{
  const inEdges  = edges.filter(l => l.target===d.id||l.target?.id===d.id);
  const outEdges = edges.filter(l => l.source===d.id||l.source?.id===d.id);
  tooltip.innerHTML =
    '<b>' + d.label + '</b><br>' +
    'type: ' + (d.type||'') + '<br>' +
    'source: ' + d.source + '<br>' +
    (d.source_file ? 'file: ' + d.source_file + '<br>' : '') +
    (d.entity_type ? 'entity_type: ' + d.entity_type + '<br>' : '') +
    'connections: ' + (degree[d.id]||0);
  tooltip.style.display='block';
}})
.on('mousemove', e => {{
  tooltip.style.left=(e.pageX+14)+'px'; tooltip.style.top=(e.pageY-28)+'px';
}})
.on('mouseout', () => tooltip.style.display='none');

simulation.on('tick', () => {{
  link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
      .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  node.attr('cx',d=>d.x).attr('cy',d=>d.y);
  label.attr('x',d=>d.x).attr('y',d=>d.y);
}});
</script>
</body>
</html>"""


# ── Output: Markdown summary ──────────────────────────────────────────────────

def write_summary(nodes, edges, output_dir: Path):
    by_source = defaultdict(list)
    for n in nodes:
        by_source[n["source"]].append(n)

    by_layer = defaultdict(list)
    for e in edges:
        by_layer[e["layer"]].append(e)

    merged_nodes = [n for n in nodes if n["source"] == "merged"]
    top_degree = sorted(nodes, key=lambda n: sum(
        1 for e in edges if e["source"] == n["id"] or e["target"] == n["id"]
    ), reverse=True)[:10]

    lines = [
        "# Merged Knowledge Graph — Summary",
        "",
        "## Overview",
        f"- **Total nodes:** {len(nodes)}",
        f"- **Total edges:** {len(edges)}",
        f"- **graphify nodes** (code structure): {len(by_source['graphify'])}",
        f"- **nuextract3 nodes** (prose semantics): {len(by_source['nuextract3'])}",
        f"- **Merged nodes** (concept appeared in both layers): {len(merged_nodes)}",
        f"- **Code structure edges:** {len(by_layer['code'])}",
        f"- **Semantic relation edges:** {len(by_layer['semantic'])}",
        "",
        "## Fused Nodes (same concept in code + prose)",
    ]
    if merged_nodes:
        for n in merged_nodes:
            lines.append(f"- `{n['id']}` — {n['label']} ({n.get('entity_type','')})")
    else:
        lines.append("- None — no direct overlaps detected between code symbols and prose entities.")

    lines += [
        "",
        "## Most Connected Nodes",
    ]
    for n in top_degree:
        deg = sum(1 for e in edges if e["source"] == n["id"] or e["target"] == n["id"])
        lines.append(f"- **{n['label']}** (`{n['id']}`) — {deg} connections — source: {n['source']}")

    lines += [
        "",
        "## Sample Semantic Relations (from nuextract3)",
    ]
    for e in [e for e in edges if e["layer"] == "semantic"][:15]:
        lines.append(f"- {e['source']} **{e['relation']}** {e['target']}")

    lines += [
        "",
        "## Sample Code Relations (from graphify)",
    ]
    for e in [e for e in edges if e["layer"] == "code"][:15]:
        lines.append(f"- `{e['source']}` **{e['relation']}** `{e['target']}` ({e.get('source_file','')})")

    lines += [
        "",
        "## All Nodes",
        "| id | label | type | source | file |",
        "|---|---|---|---|---|",
    ]
    for n in sorted(nodes, key=lambda x: x["source"]):
        lines.append(f"| `{n['id']}` | {n['label']} | {n.get('type','')} | {n['source']} | {n.get('source_file','')} |")

    p = output_dir / "merged-graph-summary.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Merge graphify + nuextract3 outputs into a unified knowledge graph")
    parser.add_argument("--graphify-json",  required=True)
    parser.add_argument("--nuextract-json", required=True)
    parser.add_argument("--output-dir",     default="r&d/1-find-offline-semantic-tool/responses/")
    parser.add_argument(
        "--clean", action="store_true",
        help="Delete existing merged-graph.* output files before running (prompts for confirmation)"
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Skip confirmation prompt when used with --clean"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.clean:
        output_files = [
            output_dir / "merged-graph.json",
            output_dir / "merged-graph.html",
            output_dir / "merged-graph-summary.md",
        ]
        if not clean_output(output_files, yes=args.yes):
            return

    print("Loading graphify output...")
    g_nodes, g_links = load_graphify(args.graphify_json)
    print(f"  {len(g_nodes)} nodes, {len(g_links)} edges")

    print("Loading nuextract3 output...")
    nu_entities, nu_relations = load_nuextract(args.nuextract_json)
    print(f"  {len(nu_entities)} entities, {len(nu_relations)} relations")

    print("Merging...")
    nodes, edges = merge(g_nodes, g_links, nu_entities, nu_relations)

    merged_count = sum(1 for n in nodes if n["source"] == "merged")
    print(f"  Result: {len(nodes)} nodes ({merged_count} fused), {len(edges)} edges")

    json_path = write_json(nodes, edges, output_dir)
    html_path = write_html(nodes, edges, output_dir)
    md_path   = write_summary(nodes, edges, output_dir)

    print()
    print("=" * 60)
    print("MERGE COMPLETE")
    print(f"  JSON:    {json_path}")
    print(f"  HTML:    {html_path}")
    print(f"  Summary: {md_path}")
    print()
    print("Open merged-graph.html in a browser to visualise.")
    print("merged-graph-summary.md is readable by humans and AI agents.")
    print("=" * 60)


if __name__ == "__main__":
    main()
