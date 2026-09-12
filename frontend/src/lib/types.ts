// Mirrors the versioned JSON contracts in backend/schemas/contracts.py.
// Person 5 never imports another person's Python code — this is the TypeScript
// side of the same published contracts.

export interface Engagement {
  likes: number;
  shares: number;
  comments: number;
  views: number;
}

export interface CanonicalEvent {
  event_id: string;
  source: "x" | "telegram" | "reddit" | "instagram" | "other";
  source_post_id: string;
  author_id_hash: string;
  timestamp_utc: string;
  text: string;
  language: string;
  reply_to_id: string | null;
  parent_event_id: string | null;
  engagement: Engagement;
  entities: string[];
  metadata: { source_version: string; collected_at_utc: string };
}

export interface LabelConfidence {
  label: string;
  confidence: number;
}

export interface Stance {
  target: string | null;
  label: "support" | "oppose" | "neutral" | "unknown";
  confidence: number;
}

export interface NLPOutput {
  event_id: string;
  language: LabelConfidence;
  sentiment: LabelConfidence;
  emotion: LabelConfidence | null;
  stance: Stance;
  embedding_ref: string | null;
  evidence: { type: string; event_id: string }[];
  model: { name: string; version: string };
}

export interface Window {
  start: string;
  end: string;
}

export interface TopicMetrics {
  volume: number;
  unique_authors: number;
  engagement: number;
  trend_score: number;
  novelty: number;
  cross_community_spread: number;
}

export interface TopicTimelinePoint {
  bucket_start: string;
  volume: number;
  unique_authors: number;
  engagement: number;
  avg_sentiment: number;
}

export interface Audience {
  categories: Record<string, number>;
  unknown_share: number;
  sample_size: number;
  confidence: number;
}

export interface Topic {
  topic_id: string;
  name: string;
  window: Window;
  metrics: TopicMetrics;
  timeline: TopicTimelinePoint[];
  audience: Audience;
  evidence_event_ids: string[];
}

export interface TopicDetail extends Topic {
  evidence_events: CanonicalEvent[];
  nlp_outputs: NLPOutput[];
}

export interface GraphMetrics {
  nodes: number;
  edges: number;
  density: number;
}

export interface Community {
  community_id: string;
  size: number;
  central_nodes: string[];
}

export interface CommunityWithMembers extends Community {
  members: string[];
}

export interface Propagation {
  depth: number;
  cross_community_rate: number;
  key_nodes: string[];
}

export interface TopologyNode {
  id: string;
  community_id: string;
  centrality: number;
  role: string;
}

export interface TopologyEdge {
  source: string;
  target: string;
  weight: number;
  type: string;
}

export interface Topology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface NetworkOutput {
  window: Window;
  graph_metrics: GraphMetrics;
  communities: Community[];
  propagation: Propagation;
  evidence_event_ids: string[];
  topology: Topology;
}

export interface OverviewResponse {
  volume: number;
  sentiment_distribution: Record<string, number>;
  top_narratives: { topic_id: string; name: string; trend_score: number }[];
  active_communities: number;
  anomalies: { topic_id: string; name: string; trend_score: number; reason: string }[];
}

export interface TimelineResponse {
  series: { topic_id: string; name: string; points: TopicTimelinePoint[] }[];
}

export interface SentimentResponse {
  topic_id: string | null;
  sample_size: number;
  sentiment: Record<string, number>;
  emotion: Record<string, number>;
  stance: Record<string, number>;
}

export interface ModelInfo {
  name: string;
  version: string;
}

export interface Claim {
  claim: string;
  confidence: number;
  evidence_event_ids: string[];
}

export interface Investigation {
  investigation_id: string;
  query: { topic_id: string; start: string; end: string };
  finding: {
    narrative: Record<string, unknown>;
    nlp: Record<string, unknown>;
    audience: Record<string, unknown>;
    network: Record<string, unknown>;
  };
  claims: Claim[];
  models: ModelInfo[];
  generated_at_utc: string;
}

export interface Report {
  report_id: string;
  investigation_id: string;
  narrative_text: string;
  generated_by: { mode: string; model: string; fallback_reason?: string };
  audit: {
    inputs: { topic_id: string; window: Window; evidence_event_ids: string[] };
    models: ModelInfo[];
    generated_at_utc: string;
  };
}
