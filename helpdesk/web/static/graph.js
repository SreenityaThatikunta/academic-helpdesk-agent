// Force-directed document graph in the style of Quartz's graph view:
// small nodes sized by degree, labels that fade in with zoom, hover to light up a node's neighbourhood.
class GraphView {
  static CATEGORY_COLORS = {
    regulations: "#5b7fbf",
    office_order: "#c0634f",
    curriculum: "#4f9a7d",
    course_catalogue: "#8a6fc2",
    calendar: "#c99a3c",
    timetable: "#3f9bb0",
    exam_timetable: "#b9638f",
    exam_policy: "#d07a3a",
    registration: "#7d8a45",
  };

  constructor(el, { onClick, labels = false } = {}) {
    this.el = el;
    this.onClick = onClick;
    this.alwaysLabels = labels;
    this.positions = new Map(); // keep the layout stable between renders
    this.sim = null;
  }

  render(data, emptyText = "") {
    const el = this.el;
    if (!el.offsetWidth) return; // hidden tab: draw when shown
    this.sim?.stop();
    el.innerHTML = "";
    if (!data || !data.nodes.length) {
      if (emptyText) el.innerHTML = `<div class="graph-empty">${emptyText}</div>`;
      return;
    }
    const css = getComputedStyle(document.documentElement);
    const v = (n) => css.getPropertyValue(n).trim();
    const W = el.clientWidth, H = el.clientHeight;
    const nodes = data.nodes.map((n) => ({ ...n, ...(this.positions.get(n.id) || {}) }));
    const links = data.links.map((l) => ({ ...l }));
    const touched = data.touched || new Set();
    const pulse = data.pulse || new Set();
    // a node new to this view starts beside a neighbour that already has a place, so the layout grows instead of resetting
    const fresh = nodes.every((n) => n.x === undefined);
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const added = nodes.filter((n) => n.x === undefined);
    if (!fresh) {
      added.forEach((n) => {
        const l = links.find((l) => (l.source === n.id && byId.get(l.target)?.x !== undefined) || (l.target === n.id && byId.get(l.source)?.x !== undefined));
        const anchor = l && byId.get(l.source === n.id ? l.target : l.source);
        n.x = (anchor?.x ?? 0) + (Math.random() - 0.5) * 30;
        n.y = (anchor?.y ?? 0) + (Math.random() - 0.5) * 30;
      });
    }

    const degree = new Map();
    links.forEach((l) => {
      degree.set(l.source, (degree.get(l.source) || 0) + 1);
      degree.set(l.target, (degree.get(l.target) || 0) + 1);
    });
    const neighbours = new Map(nodes.map((n) => [n.id, new Set([n.id])]));
    links.forEach((l) => {
      neighbours.get(l.source)?.add(l.target);
      neighbours.get(l.target)?.add(l.source);
    });
    const radius = (n) => (n.type === "tag" ? 3.5 : n.type === "question" ? 5 : 2.5 + Math.sqrt(degree.get(n.id) || 1) * 1.4);
    const fill = (n) => {
      if (n.type === "question") return v("--accent");
      if (n.type === "tag") return v("--surface");
      return GraphView.CATEGORY_COLORS[n.category] || v("--node");
    };
    const linkColor = (l) => (l.kind === "amends" ? v("--danger") : l.kind === "cites" ? v("--accent") : v("--link"));

    const svg = d3.select(el).append("svg").attr("viewBox", [-W / 2, -H / 2, W, H]);
    const root = svg.append("g");
    const tooltip = d3.select(el).append("div").attr("class", "tooltip").style("opacity", 0);

    const link = root.append("g").selectAll("line").data(links).join("line")
      .attr("stroke", linkColor)
      .attr("stroke-width", (l) => (l.kind === "cites" || l.kind === "amends" ? 1.2 : 0.8))
      .attr("stroke-dasharray", (l) => (l.kind === "amends" ? "3 2" : l.kind === "retrieved" ? "1.5 2" : null))
      .attr("class", (l) => (l.source === "qlive" ? "flow" : null));

    const node = root.append("g").selectAll("g").data(nodes).join("g").style("cursor", "pointer");
    node.filter((n) => pulse.has(n.id)).append("circle")
      .attr("class", "pulse").attr("r", (n) => radius(n) + 2).attr("fill", "none").attr("stroke", v("--accent")).attr("stroke-width", 1.5);
    node.filter((n) => touched.has(n.id)).append("circle")
      .attr("r", (n) => radius(n) + 3).attr("fill", "none").attr("stroke", v("--accent")).attr("stroke-width", 1.2);
    node.append("circle")
      .attr("r", radius)
      .attr("fill", fill)
      .attr("stroke", (n) => (n.type === "tag" ? v("--tag") : n.status === "superseded" ? v("--faint") : "none"))
      .attr("stroke-width", (n) => (n.type === "tag" ? 1.5 : 1))
      .attr("opacity", (n) => (n.status === "superseded" ? 0.55 : 1));

    const short = (n) => {
      const t = n.type === "tag" ? `#${n.title}` : n.title;
      return t.length > 28 ? t.slice(0, 26) + "…" : t;
    };
    const label = root.append("g").selectAll("text").data(nodes).join("text")
      .attr("class", "label").attr("text-anchor", "middle")
      .attr("dy", (n) => radius(n) + 11)
      .text(short);

    // labels for the chat's questions and cited documents; the rest appear on zoom or hover (Quartz-style)
    const cited = new Set(links.filter((l) => l.kind === "cites").map((l) => l.target));
    const important = (n) => n.type === "question" || cited.has(n.id) || pulse.has(n.id);
    let zoomK = 1, hovered = null;
    const baseLabelOpacity = (n) => {
      if (this.alwaysLabels && (important(n) || n.type === "tag")) return 1;
      if (important(n)) return 0.9;
      return Math.max(0, Math.min(1, (zoomK - 1.4) * 1.5));
    };
    const paint = () => {
      const near = hovered ? neighbours.get(hovered.id) : null;
      node.attr("opacity", (n) => (!near || near.has(n.id) ? 1 : 0.15));
      link.attr("stroke-opacity", (l) => (!near ? 0.8 : l.source.id === hovered.id || l.target.id === hovered.id ? 1 : 0.08))
        .attr("stroke", (l) => (near && (l.source.id === hovered.id || l.target.id === hovered.id) && l.kind === "tag" ? v("--muted") : linkColor(l)));
      label.attr("opacity", (n) => (near ? (near.has(n.id) ? 1 : 0.05) : baseLabelOpacity(n)))
        .attr("font-size", (n) => (hovered && n.id === hovered.id ? 12 / Math.sqrt(zoomK) + 1 : 10 / Math.sqrt(zoomK)))
        .attr("font-weight", (n) => (hovered && n.id === hovered.id ? 600 : 400));
    };

    node.on("mouseenter", (e, n) => {
      hovered = n;
      paint();
      const sub = n.type === "doc" ? `${n.id} · ${n.category.replace("_", " ")} · ${n.date}${n.status === "superseded" ? " · superseded" : ""}`
        : n.type === "tag" ? `${(degree.get(n.id) || 0)} documents` : "question in this chat";
      tooltip.html(`<div>${n.type === "tag" ? "#" : ""}${escapeHtml(n.title)}</div><div class="t-sub">${sub}</div>`).style("opacity", 1);
    }).on("mousemove", (e) => {
      const [x, y] = d3.pointer(e, el);
      tooltip.style("left", Math.min(x + 12, W - 250) + "px").style("top", y + 12 + "px");
    }).on("mouseleave", () => {
      hovered = null;
      paint();
      tooltip.style("opacity", 0);
    }).on("click", (e, n) => this.onClick?.(n));

    let ticks = 0;
    this.sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id((n) => n.id).distance((l) => (l.kind === "tag" ? 50 : 80)).strength(0.5))
      .force("charge", d3.forceManyBody().strength(-260))
      .force("center", d3.forceCenter(0, 0).strength(0.3))
      .force("x", d3.forceX().strength(0.04))
      .force("y", d3.forceY().strength(0.04))
      .force("collide", d3.forceCollide((n) => radius(n) + 8))
      .alpha(fresh ? 1 : added.length ? 0.5 : 0.15)
      .on("tick", () => {
        link.attr("x1", (l) => l.source.x).attr("y1", (l) => l.source.y).attr("x2", (l) => l.target.x).attr("y2", (l) => l.target.y);
        node.attr("transform", (n) => `translate(${n.x},${n.y})`);
        label.attr("x", (n) => n.x).attr("y", (n) => n.y);
        nodes.forEach((n) => this.positions.set(n.id, { x: n.x, y: n.y }));
        if ((fresh || added.length) && ++ticks === 80) fit();
      });

    // once the layout has mostly settled, zoom so the whole graph fits (on a fresh layout or when nodes were added)
    const zoom = d3.zoom().scaleExtent([0.3, 5]).on("zoom", (e) => {
      zoomK = e.transform.k;
      root.attr("transform", e.transform);
      paint();
    });
    const fit = () => {
      const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
      const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      const k = Math.min(1.6, 0.85 / Math.max((x1 - x0 + 80) / W, (y1 - y0 + 60) / H));
      svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity.scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2));
    };

    node.call(d3.drag()
      .on("start", (e, n) => { if (!e.active) this.sim.alphaTarget(0.3).restart(); n.fx = n.x; n.fy = n.y; })
      .on("drag", (e, n) => { n.fx = e.x; n.fy = e.y; })
      .on("end", (e, n) => { if (!e.active) this.sim.alphaTarget(0); n.fx = null; n.fy = null; }));

    svg.call(zoom).on("dblclick.zoom", fit);
    paint();
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
