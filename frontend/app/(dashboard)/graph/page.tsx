"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import {
  GitFork,
  Plus,
  Search,
  Filter,
  Maximize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Sparkles,
  Layers,
  Activity,
  Shield,
  Trash2,
  ExternalLink,
  ArrowRight,
  X,
  Code,
  FolderGit2,
  User,
  Building,
  Lightbulb,
  MapPin,
  Calendar,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

interface GraphNode {
  id: string;
  name: string;
  entity_type: string;
  description?: string | null;
  mention_count: number;
  degree: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  weight: number;
  source_name?: string | null;
  target_name?: string | null;
}

interface GraphAnalytics {
  total_entities: number;
  total_relationships: number;
  entity_type_breakdown?: Record<string, number>;
  entities_by_type?: Record<string, number>;
  top_central_entities: Array<{
    id: string;
    name: string;
    entity_type: string;
    degree: number;
    mention_count: number;
  }>;
}

const ENTITY_CONFIG: Record<
  string,
  { label: string; color: string; bg: string; border: string; icon: any }
> = {
  technology: {
    label: "Technology",
    color: "text-emerald-500",
    bg: "rgba(16, 185, 129, 0.12)",
    border: "#10b981",
    icon: Code,
  },
  project: {
    label: "Project",
    color: "text-[#014BAA]",
    bg: "rgba(1, 75, 170, 0.12)",
    border: "#014BAA",
    icon: FolderGit2,
  },
  person: {
    label: "Person",
    color: "text-amber-500",
    bg: "rgba(245, 158, 11, 0.12)",
    border: "#f59e0b",
    icon: User,
  },
  organization: {
    label: "Organization",
    color: "text-blue-600",
    bg: "rgba(37, 99, 235, 0.12)",
    border: "#2563eb",
    icon: Building,
  },
  concept: {
    label: "Concept",
    color: "text-indigo-600",
    bg: "rgba(79, 70, 229, 0.12)",
    border: "#4f46e5",
    icon: Lightbulb,
  },
  location: {
    label: "Location",
    color: "text-rose-500",
    bg: "rgba(244, 63, 94, 0.12)",
    border: "#f43f5e",
    icon: MapPin,
  },
  event: {
    label: "Event",
    color: "text-cyan-600",
    bg: "rgba(8, 145, 178, 0.12)",
    border: "#0891b2",
    icon: Calendar,
  },
};

export default function KnowledgeGraphPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [analytics, setAnalytics] = useState<GraphAnalytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // SVG Pan and Zoom
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const [startPan, setStartPan] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement | null>(null);

  // Modals
  const [isCreateEntityOpen, setIsCreateEntityOpen] = useState(false);
  const [isCreateRelOpen, setIsCreateRelOpen] = useState(false);
  const [isExtractOpen, setIsExtractOpen] = useState(false);

  // Form states
  const [newEntity, setNewEntity] = useState({
    name: "",
    entity_type: "technology",
    description: "",
  });
  const [newRel, setNewRel] = useState({
    source_entity_id: "",
    target_entity_id: "",
    relationship_type: "uses_technology",
    weight: 1.0,
  });
  const [extractText, setExtractText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Node layout coordinates
  const [nodePositions, setNodePositions] = useState<
    Record<string, { x: number; y: number }>
  >({});

  const fetchGraphData = async () => {
    setIsLoading(true);
    try {
      const [graphRes, analyticsRes] = await Promise.all([
        api.get<any>("/graph"),
        api.get<any>("/graph/analytics"),
      ]);

      if (graphRes.success && graphRes.data) {
        const fetchedNodes: GraphNode[] = graphRes.data.nodes || [];
        const fetchedEdges: GraphEdge[] = graphRes.data.edges || [];
        setNodes(fetchedNodes);
        setEdges(fetchedEdges);

        // Calculate positions using circular layout
        const positions: Record<string, { x: number; y: number }> = {};
        const count = fetchedNodes.length;
        const centerX = 450;
        const centerY = 320;
        const radius = Math.min(centerX - 80, centerY - 80, 260);

        fetchedNodes.forEach((node, i) => {
          if (count === 1) {
            positions[node.id] = { x: centerX, y: centerY };
          } else {
            const angle = (2 * Math.PI * i) / count;
            const r = radius * (0.8 + ((node.degree || 1) % 3) * 0.15);
            positions[node.id] = {
              x: centerX + r * Math.cos(angle),
              y: centerY + r * Math.sin(angle),
            };
          }
        });
        setNodePositions(positions);
      }

      if (analyticsRes.success && analyticsRes.data) {
        setAnalytics(analyticsRes.data);
      }
    } catch (err) {
      console.error("Failed to load graph data", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGraphData();
  }, [activeWorkspaceId]);

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    return nodes.filter((node) => {
      const matchesType =
        selectedType === "all" || node.entity_type === selectedType;
      const matchesSearch =
        searchQuery.trim() === "" ||
        node.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (node.description &&
          node.description.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesType && matchesSearch;
    });
  }, [nodes, selectedType, searchQuery]);

  const filteredNodeIds = useMemo(
    () => new Set(filteredNodes.map((n) => n.id)),
    [filteredNodes]
  );

  // Filtered edges
  const filteredEdges = useMemo(() => {
    return edges.filter(
      (edge) =>
        filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)
    );
  }, [edges, filteredNodeIds]);

  // Selected node relationships
  const selectedNodeRelationships = useMemo(() => {
    if (!selectedNode) return { outgoing: [], incoming: [] };
    const outgoing = edges.filter((e) => e.source === selectedNode.id);
    const incoming = edges.filter((e) => e.target === selectedNode.id);
    return { outgoing, incoming };
  }, [selectedNode, edges]);

  // Pan & Zoom handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    const targetTag = (e.target as Element).tagName.toLowerCase();
    if (targetTag === "svg" || targetTag === "g") {
      setIsPanning(true);
      setStartPan({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom((prev) => Math.min(Math.max(Number((prev + delta).toFixed(2)), 0.4), 2.5));
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPan({
        x: e.clientX - startPan.x,
        y: e.clientY - startPan.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const resetView = () => {
    setPan({ x: 0, y: 0 });
    setZoom(1);
  };

  // Node Dragging inside SVG
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);

  const handleNodeMouseDown = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDraggedNodeId(id);
  };

  const handleSvgMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      handleMouseMove(e);
      return;
    }
    if (draggedNodeId && svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const x = (e.clientX - rect.left - pan.x) / zoom;
      const y = (e.clientY - rect.top - pan.y) / zoom;
      setNodePositions((prev) => ({
        ...prev,
        [draggedNodeId]: { x, y },
      }));
    }
  };

  const handleSvgMouseUp = () => {
    setIsPanning(false);
    setDraggedNodeId(null);
  };

  // Handlers for Entity & Relationship Creation
  const handleCreateEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEntity.name.trim()) return;

    setIsSubmitting(true);
    try {
      const res = await api.post("/graph/entities", newEntity);
      if (res.success) {
        setIsCreateEntityOpen(false);
        setNewEntity({ name: "", entity_type: "technology", description: "" });
        await fetchGraphData();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateRelationship = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRel.source_entity_id || !newRel.target_entity_id) return;

    setIsSubmitting(true);
    try {
      const res = await api.post("/graph/relationships", newRel);
      if (res.success) {
        setIsCreateRelOpen(false);
        setNewRel({
          source_entity_id: "",
          target_entity_id: "",
          relationship_type: "uses_technology",
          weight: 1.0,
        });
        await fetchGraphData();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExtractGraph = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!extractText.trim()) return;

    setIsSubmitting(true);
    try {
      const res = await api.post("/graph/extract", { text: extractText });
      if (res.success) {
        setIsExtractOpen(false);
        setExtractText("");
        await fetchGraphData();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteEntity = async (entityId: string) => {
    if (!confirm("Are you sure you want to delete this entity and all its connections?")) return;
    try {
      const res = await api.delete(`/graph/entities/${entityId}`);
      if (res.success) {
        setSelectedNode(null);
        await fetchGraphData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const seedSampleGraph = async () => {
    setIsSubmitting(true);
    try {
      const sampleText =
        "AI-MemoryVerse is built with Next.js, FastAPI, PostgreSQL, and pgvector. " +
        "Met with Jane Doe to deploy on AWS. Project Apollo integrates with Redis and Celery.";
      await api.post("/graph/extract", { text: sampleText });
      await fetchGraphData();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#282B4A] dark:text-white flex items-center gap-2">
            <GitFork className="h-6 w-6 text-[#014BAA]" />
            Knowledge Graph
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Explore interconnected entities, technologies, projects, and relationships extracted across your memory vault.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsExtractOpen(true)}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold rounded-xl bg-[#014BAA]/10 text-[#014BAA] dark:text-[#F8F3F0] dark:bg-[#014BAA]/25 border border-[#014BAA]/30 hover:bg-[#014BAA]/20 transition-all shadow-sm"
          >
            <Sparkles className="h-4 w-4" />
            Extract from Text
          </button>
          <button
            onClick={() => setIsCreateRelOpen(true)}
            disabled={nodes.length < 2}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold rounded-xl bg-white dark:bg-navy-900 text-[#282B4A] dark:text-slate-200 border border-[#EEEBDA] dark:border-navy-800 hover:bg-slate-50 dark:hover:bg-navy-850 transition-all disabled:opacity-50 shadow-sm"
          >
            <Plus className="h-4 w-4 text-[#014BAA] dark:text-blue-400" />
            Add Connection
          </button>
          <button
            onClick={() => setIsCreateEntityOpen(true)}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold rounded-xl bg-[#014BAA] text-[#F8F3F0] hover:bg-[#014BAA]/90 transition-all shadow-md shadow-[#014BAA]/25"
          >
            <Plus className="h-4 w-4" />
            New Entity
          </button>
        </div>
      </div>

      {/* Analytics KPI Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/60 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Entities
            </span>
            <Layers className="h-4 w-4 text-[#014BAA]" />
          </div>
          <p className="text-2xl font-extrabold text-[#282B4A] dark:text-white mt-1">
            {analytics?.total_entities ?? nodes.length}
          </p>
        </div>

        <div className="p-4 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/60 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Connections
            </span>
            <GitFork className="h-4 w-4 text-[#014BAA]" />
          </div>
          <p className="text-2xl font-extrabold text-[#282B4A] dark:text-white mt-1">
            {analytics?.total_relationships ?? edges.length}
          </p>
        </div>

        <div className="p-4 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/60 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Entity Types
            </span>
            <Activity className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <p className="text-2xl font-extrabold text-[#282B4A] dark:text-white mt-1">
            {analytics?.entity_type_breakdown
              ? Object.keys(analytics.entity_type_breakdown).length
              : analytics?.entities_by_type
              ? Object.keys(analytics.entities_by_type).length
              : 0}
          </p>
        </div>

        <div className="p-4 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/60 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Key Hub
            </span>
            <Shield className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          </div>
          <p className="text-base font-bold text-[#014BAA] dark:text-amber-400 mt-1 truncate">
            {analytics?.top_central_entities?.[0]?.name || "None yet"}
          </p>
        </div>
      </div>

      {/* Main Interactive Graph Canvas & Controls */}
      <div className="relative rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-[#F8F3F0] dark:bg-navy-950/70 overflow-hidden min-h-[640px] flex flex-col shadow-sm">
        {/* Controls Bar */}
        <div className="p-3 border-b border-[#EEEBDA] dark:border-navy-800 flex flex-wrap items-center justify-between gap-3 bg-white/95 dark:bg-navy-900/80 backdrop-blur z-10 shadow-xs">
          <div className="flex items-center gap-2 flex-1 max-w-sm">
            <div className="relative w-full">
              <Search className="h-4 w-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search entities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-[#282B4A] dark:text-white placeholder-slate-400 focus:outline-none focus:border-[#014BAA]"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg px-2.5 py-1.5 text-xs text-[#282B4A] dark:text-slate-300 focus:outline-none focus:border-[#014BAA]"
            >
              <option value="all">All Entity Types</option>
              {Object.entries(ENTITY_CONFIG).map(([key, cfg]) => (
                <option key={key} value={key}>
                  {cfg.label}
                </option>
              ))}
            </select>

            <div className="h-4 w-px bg-[#EEEBDA] dark:bg-navy-800 mx-1" />

            <button
              onClick={() => setZoom((z) => Math.min(z + 0.2, 2.5))}
              className="p-1.5 rounded-lg bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 text-[#282B4A] dark:text-slate-300 hover:text-[#014BAA] hover:bg-white dark:hover:bg-navy-900 shadow-xs"
              title="Zoom In"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
            <button
              onClick={() => setZoom((z) => Math.max(z - 0.2, 0.4))}
              className="p-1.5 rounded-lg bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 text-[#282B4A] dark:text-slate-300 hover:text-[#014BAA] hover:bg-white dark:hover:bg-navy-900 shadow-xs"
              title="Zoom Out"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <button
              onClick={resetView}
              className="p-1.5 rounded-lg bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 text-[#282B4A] dark:text-slate-300 hover:text-[#014BAA] hover:bg-white dark:hover:bg-navy-900 shadow-xs"
              title="Reset View"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Canvas Area with Vanilla Canvas Dots */}
        <div className="relative flex-1 w-full h-full min-h-[560px] select-none bg-[radial-gradient(#d3cebe_1px,transparent_1px)] dark:bg-[radial-gradient(#34385C_1px,transparent_1px)] [background-size:20px_20px]">
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="h-8 w-8 text-[#014BAA] animate-spin" />
            </div>
          ) : nodes.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
              <div className="w-16 h-16 rounded-2xl bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center mb-4 text-[#014BAA]">
                <GitFork className="h-8 w-8" />
              </div>
              <h3 className="text-lg font-bold text-[#282B4A] dark:text-white">
                No Knowledge Graph Entities Yet
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mt-1 mb-6 leading-relaxed">
                Connect your memory entries into an interconnected graph. Automatically extract entities from texts or seed an initial architecture graph.
              </p>
              <button
                onClick={seedSampleGraph}
                disabled={isSubmitting}
                className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl bg-[#014BAA] text-[#F8F3F0] hover:bg-[#014BAA]/90 transition-all shadow-md shadow-[#014BAA]/25"
              >
                {isSubmitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                Extract Sample Tech Architecture
              </button>
            </div>
          ) : (
            <svg
              ref={svgRef}
              className="w-full h-full cursor-grab active:cursor-grabbing min-h-[560px]"
              onMouseDown={handleMouseDown}
              onMouseMove={handleSvgMouseMove}
              onMouseUp={handleSvgMouseUp}
              onMouseLeave={handleSvgMouseUp}
              onWheel={handleWheel}
            >
              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="8"
                  markerHeight="6"
                  refX="14"
                  refY="3"
                  orient="auto"
                >
                  <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
                </marker>
                <marker
                  id="arrowhead-active"
                  markerWidth="8"
                  markerHeight="6"
                  refX="14"
                  refY="3"
                  orient="auto"
                >
                  <polygon points="0 0, 8 3, 0 6" fill="#014BAA" />
                </marker>
              </defs>

              <g
                transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}
                className="transition-transform duration-75 ease-out"
              >
                {/* Graph Edges */}
                {filteredEdges.map((edge) => {
                  const srcPos = nodePositions[edge.source];
                  const tgtPos = nodePositions[edge.target];
                  if (!srcPos || !tgtPos) return null;

                  const isEdgeActive =
                    selectedNode &&
                    (selectedNode.id === edge.source ||
                      selectedNode.id === edge.target);

                  const midX = (srcPos.x + tgtPos.x) / 2;
                  const midY = (srcPos.y + tgtPos.y) / 2;

                  return (
                    <g key={edge.id} className="cursor-pointer">
                      <line
                        x1={srcPos.x}
                        y1={srcPos.y}
                        x2={tgtPos.x}
                        y2={tgtPos.y}
                        stroke={isEdgeActive ? "#014BAA" : "#94a3b8"}
                        strokeWidth={isEdgeActive ? 2.5 : 1.5}
                        markerEnd={
                          isEdgeActive
                            ? "url(#arrowhead-active)"
                            : "url(#arrowhead)"
                        }
                      />
                      <rect
                        x={midX - 35}
                        y={midY - 9}
                        width={70}
                        height={18}
                        rx={4}
                        fill="#FFFFFF"
                        stroke={isEdgeActive ? "#014BAA" : "#EEEBDA"}
                        strokeWidth={1}
                        className="dark:fill-[#181A2C] dark:stroke-[#34385C]"
                      />
                      <text
                        x={midX}
                        y={midY + 3.5}
                        textAnchor="middle"
                        fill={isEdgeActive ? "#014BAA" : "#282B4A"}
                        fontSize="9"
                        fontWeight="600"
                        className="select-none pointer-events-none dark:fill-[#F8F3F0]"
                      >
                        {edge.relationship_type.replace(/_/g, " ")}
                      </text>
                    </g>
                  );
                })}

                {/* Graph Nodes */}
                {filteredNodes.map((node) => {
                  const pos = nodePositions[node.id];
                  if (!pos) return null;

                  const cfg =
                    ENTITY_CONFIG[node.entity_type] || ENTITY_CONFIG.concept;
                  const isSelected = selectedNode?.id === node.id;
                  const radius = Math.min(30 + (node.degree || 1) * 2, 44);

                  return (
                    <g
                      key={node.id}
                      transform={`translate(${pos.x}, ${pos.y})`}
                      className="cursor-pointer group"
                      onMouseDown={(e) => handleNodeMouseDown(node.id, e)}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedNode(node);
                      }}
                    >
                      {/* Outer pulse when selected */}
                      {isSelected && (
                        <circle
                          r={radius + 8}
                          fill="none"
                          stroke={cfg.border}
                          strokeWidth={2}
                          strokeOpacity={0.6}
                          className="animate-pulse"
                        />
                      )}

                      {/* Main Node Circle */}
                      <circle
                        r={radius}
                        fill="#FFFFFF"
                        stroke={isSelected ? cfg.border : "#EEEBDA"}
                        strokeWidth={isSelected ? 3 : 1.5}
                        className="transition-colors group-hover:stroke-[#014BAA] shadow-md dark:fill-[#1e2238] dark:stroke-[#34385C]"
                      />
                      <circle
                        r={radius - 4}
                        fill={cfg.bg}
                        stroke="none"
                      />

                      {/* Text label */}
                      <text
                        y={-2}
                        textAnchor="middle"
                        fill="#282B4A"
                        fontSize="11"
                        fontWeight="bold"
                        className="pointer-events-none select-none dark:fill-[#F8F3F0]"
                      >
                        {node.name.length > 12
                          ? `${node.name.slice(0, 11)}…`
                          : node.name}
                      </text>
                      <text
                        y={12}
                        textAnchor="middle"
                        fill={cfg.border}
                        fontSize="8.5"
                        fontWeight="600"
                        className="pointer-events-none select-none"
                      >
                        {cfg.label}
                      </text>

                      {/* Degree Badge */}
                      {(node.degree || 0) > 0 && (
                        <g transform={`translate(${radius - 8}, ${-radius + 8})`}>
                          <circle r={8} fill="#014BAA" stroke="#FFFFFF" strokeWidth={1} />
                          <text
                            y={3}
                            textAnchor="middle"
                            fill="#F8F3F0"
                            fontSize="8"
                            fontWeight="bold"
                            className="pointer-events-none select-none"
                          >
                            {node.degree}
                          </text>
                        </g>
                      )}
                    </g>
                  );
                })}
              </g>
            </svg>
          )}

          {/* Selected Node Details Drawer */}
          {selectedNode && (
            <div className="absolute right-4 top-4 bottom-4 w-80 bg-white/95 dark:bg-navy-900/95 border border-[#EEEBDA] dark:border-navy-800 rounded-2xl p-5 shadow-2xl backdrop-blur-md flex flex-col z-30 animate-in fade-in slide-in-from-right duration-200">
              <div className="flex items-start justify-between pb-3 border-b border-[#EEEBDA] dark:border-navy-800">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{
                      backgroundColor:
                        ENTITY_CONFIG[selectedNode.entity_type]?.border ||
                        "#014BAA",
                    }}
                  />
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    {ENTITY_CONFIG[selectedNode.entity_type]?.label ||
                      selectedNode.entity_type}
                  </span>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-[#282B4A] dark:hover:text-white hover:bg-slate-100 dark:hover:bg-navy-800 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-4 flex-1 overflow-y-auto space-y-4 pr-1">
                <div>
                  <h3 className="text-lg font-bold text-[#282B4A] dark:text-white break-words">
                    {selectedNode.name}
                  </h3>
                  {selectedNode.description ? (
                    <p className="text-xs text-slate-600 dark:text-slate-400 mt-1.5 leading-relaxed">
                      {selectedNode.description}
                    </p>
                  ) : (
                    <p className="text-xs text-slate-400 italic mt-1.5">
                      No description provided.
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-center">
                  <div className="p-2.5 rounded-lg bg-[#F8F3F0] dark:bg-navy-950/60 border border-[#EEEBDA] dark:border-navy-800">
                    <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-medium">
                      Connections
                    </span>
                    <p className="text-lg font-bold text-[#282B4A] dark:text-white mt-0.5">
                      {selectedNode.degree}
                    </p>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#F8F3F0] dark:bg-navy-950/60 border border-[#EEEBDA] dark:border-navy-800">
                    <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-medium">
                      Mentions
                    </span>
                    <p className="text-lg font-bold text-[#014BAA] dark:text-cyan-400 mt-0.5">
                      {selectedNode.mention_count}
                    </p>
                  </div>
                </div>

                {/* Relationships list */}
                <div>
                  <h4 className="text-xs font-semibold text-[#282B4A] dark:text-slate-300 uppercase tracking-wider mb-2">
                    Direct Connections
                  </h4>

                  {selectedNodeRelationships.outgoing.length === 0 &&
                  selectedNodeRelationships.incoming.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">
                      No connections found.
                    </p>
                  ) : (
                    <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                      {selectedNodeRelationships.outgoing.map((rel) => {
                        const targetNode = nodes.find(
                          (n) => n.id === rel.target
                        );
                        return (
                          <div
                            key={rel.id}
                            className="p-2 rounded-lg bg-[#F8F3F0] dark:bg-navy-950/50 border border-[#EEEBDA] dark:border-navy-800/80 text-xs flex items-center justify-between"
                          >
                            <span className="text-[#014BAA] dark:text-cyan-400 font-semibold">
                              {rel.relationship_type.replace(/_/g, " ")}
                            </span>
                            <span className="text-[#282B4A] dark:text-white font-medium flex items-center gap-1">
                              <ArrowRight className="h-3 w-3 text-slate-400" />
                              {targetNode?.name || "Target"}
                            </span>
                          </div>
                        );
                      })}

                      {selectedNodeRelationships.incoming.map((rel) => {
                        const sourceNode = nodes.find(
                          (n) => n.id === rel.source
                        );
                        return (
                          <div
                            key={rel.id}
                            className="p-2 rounded-lg bg-[#F8F3F0] dark:bg-navy-950/50 border border-[#EEEBDA] dark:border-navy-800/80 text-xs flex items-center justify-between"
                          >
                            <span className="text-[#282B4A] dark:text-slate-300 font-medium flex items-center gap-1">
                              {sourceNode?.name || "Source"}
                              <ArrowRight className="h-3 w-3 text-slate-400" />
                            </span>
                            <span className="text-[#014BAA] dark:text-blue-400 font-semibold">
                              {rel.relationship_type.replace(/_/g, " ")}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-3 border-t border-[#EEEBDA] dark:border-navy-800">
                <button
                  onClick={() => handleDeleteEntity(selectedNode.id)}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold rounded-lg text-rose-600 bg-rose-50 border border-rose-200 hover:bg-rose-100 dark:text-rose-400 dark:bg-rose-500/10 dark:border-rose-500/20 dark:hover:bg-rose-500/20 transition-all"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete Entity
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* MODAL: New Entity */}
      {isCreateEntityOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-navy-900 border border-[#EEEBDA] dark:border-navy-800 rounded-2xl p-6 shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-[#EEEBDA] dark:border-navy-800">
              <h3 className="text-lg font-bold text-[#282B4A] dark:text-white flex items-center gap-2">
                <Plus className="h-5 w-5 text-[#014BAA]" />
                Add Knowledge Entity
              </h3>
              <button
                onClick={() => setIsCreateEntityOpen(false)}
                className="text-slate-400 hover:text-[#282B4A] dark:hover:text-white transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateEntity} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 mb-1">
                  Entity Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Next.js, Project Apollo, Jane Doe"
                  value={newEntity.name}
                  onChange={(e) =>
                    setNewEntity({ ...newEntity, name: e.target.value })
                  }
                  className="w-full bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg px-3 py-2 text-sm text-[#282B4A] dark:text-white focus:outline-none focus:border-[#014BAA]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 mb-1">
                  Entity Type *
                </label>
                <select
                  value={newEntity.entity_type}
                  onChange={(e) =>
                    setNewEntity({ ...newEntity, entity_type: e.target.value })
                  }
                  className="w-full bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg px-3 py-2 text-sm text-[#282B4A] dark:text-white focus:outline-none focus:border-[#014BAA]"
                >
                  {Object.entries(ENTITY_CONFIG).map(([key, cfg]) => (
                    <option key={key} value={key}>
                      {cfg.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 mb-1">
                  Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Brief note or summary about this entity..."
                  value={newEntity.description}
                  onChange={(e) =>
                    setNewEntity({ ...newEntity, description: e.target.value })
                  }
                  className="w-full bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg px-3 py-2 text-sm text-[#282B4A] dark:text-white focus:outline-none focus:border-[#014BAA] resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateEntityOpen(false)}
                  className="px-4 py-2 text-sm text-slate-500 hover:text-[#282B4A] dark:text-slate-400 dark:hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !newEntity.name.trim()}
                  className="px-4 py-2 text-sm font-semibold rounded-xl bg-[#014BAA] text-[#F8F3F0] hover:bg-[#014BAA]/90 disabled:opacity-50 transition-all shadow-md shadow-[#014BAA]/25"
                >
                  {isSubmitting ? "Creating..." : "Create Entity"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: New Relationship */}
      {isCreateRelOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-navy-900 border border-[#EEEBDA] dark:border-navy-800 rounded-2xl p-6 shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-[#EEEBDA] dark:border-navy-800">
              <h3 className="text-lg font-bold text-[#282B4A] dark:text-white flex items-center gap-2">
                <GitFork className="h-5 w-5 text-[#014BAA]" />
                Add Connection Edge
              </h3>
              <button
                onClick={() => setIsCreateRelOpen(false)}
                className="text-slate-400 hover:text-[#282B4A] dark:hover:text-white transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateRelationship} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 mb-1">
                  Source Entity *
                </label>
                <select
                  required
                  value={newRel.source_entity_id}
                  onChange={(e) =>
                    setNewRel({ ...newRel, source_entity_id: e.target.value })
                  }
                  className="w-full bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg px-3 py-2 text-sm text-[#282B4A] dark:text-white focus:outline-none focus:border-[#014BAA]"
                >
                  <option value="">Select source entity...</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name} ({n.entity_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 mb-1">
                  Relationship Type *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. uses_technology, depends_on, collaborates_with"
                  value={newRel.relationship_type}
                  onChange={(e) =>
                    setNewRel({
                      ...newRel,
                      relationship_type: e.target.value,
                    })
                  }
                  className="w-full bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg px-3 py-2 text-sm text-[#282B4A] dark:text-white focus:outline-none focus:border-[#014BAA]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 mb-1">
                  Target Entity *
                </label>
                <select
                  required
                  value={newRel.target_entity_id}
                  onChange={(e) =>
                    setNewRel({ ...newRel, target_entity_id: e.target.value })
                  }
                  className="w-full bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg px-3 py-2 text-sm text-[#282B4A] dark:text-white focus:outline-none focus:border-[#014BAA]"
                >
                  <option value="">Select target entity...</option>
                  {nodes
                    .filter((n) => n.id !== newRel.source_entity_id)
                    .map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.name} ({n.entity_type})
                      </option>
                    ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateRelOpen(false)}
                  className="px-4 py-2 text-sm text-slate-500 hover:text-[#282B4A] dark:text-slate-400 dark:hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    isSubmitting ||
                    !newRel.source_entity_id ||
                    !newRel.target_entity_id
                  }
                  className="px-4 py-2 text-sm font-semibold rounded-xl bg-[#014BAA] text-[#F8F3F0] hover:bg-[#014BAA]/90 disabled:opacity-50 transition-all shadow-md shadow-[#014BAA]/25"
                >
                  {isSubmitting ? "Connecting..." : "Add Connection"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Extract from Text */}
      {isExtractOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-navy-900 border border-[#EEEBDA] dark:border-navy-800 rounded-2xl p-6 shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-[#EEEBDA] dark:border-navy-800">
              <h3 className="text-lg font-bold text-[#282B4A] dark:text-white flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-[#014BAA]" />
                Extract Knowledge Graph from Text
              </h3>
              <button
                onClick={() => setIsExtractOpen(false)}
                className="text-slate-400 hover:text-[#282B4A] dark:hover:text-white transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleExtractGraph} className="mt-4 space-y-4">
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                Paste any unstructured notes, meeting logs, or architectural descriptions. Our AI extractor detects technologies, projects, people, and their relationships automatically.
              </p>

              <div>
                <textarea
                  rows={6}
                  required
                  placeholder="e.g. AI-MemoryVerse uses FastAPI, Next.js, PostgreSQL, and Redis. Met with Alex to build the search engine. Project Orion depends on Celery..."
                  value={extractText}
                  onChange={(e) => setExtractText(e.target.value)}
                  className="w-full bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-800 rounded-lg p-3 text-sm text-[#282B4A] dark:text-white focus:outline-none focus:border-[#014BAA] resize-none font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsExtractOpen(false)}
                  className="px-4 py-2 text-sm text-slate-500 hover:text-[#282B4A] dark:text-slate-400 dark:hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !extractText.trim()}
                  className="flex items-center gap-2 px-5 py-2 text-sm font-semibold rounded-xl bg-[#014BAA] text-[#F8F3F0] hover:bg-[#014BAA]/90 disabled:opacity-50 transition-all shadow-md shadow-[#014BAA]/25"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Extracting...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Extract & Ingest
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
