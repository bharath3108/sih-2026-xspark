import type {
  Investigation,
  NetworkOutput,
  OverviewResponse,
  Report,
  SentimentResponse,
  TimelineResponse,
  Topic,
  TopicDetail,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(
      `Could not reach the analytics API at ${API_BASE}. Is the backend running?`,
      0
    );
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(detail, res.status);
  }

  return res.json() as Promise<T>;
}

export const api = {
  getOverview: () => request<OverviewResponse>("/api/overview"),

  getTimeline: (topicId?: string) =>
    request<TimelineResponse>(`/api/timeline${topicId ? `?topic_id=${encodeURIComponent(topicId)}` : ""}`),

  listTopics: () => request<{ topics: Topic[] }>("/api/topics"),

  getTopic: (topicId: string) => request<TopicDetail>(`/api/topics/${encodeURIComponent(topicId)}`),

  getSentiment: (topicId?: string) =>
    request<SentimentResponse>(`/api/sentiment${topicId ? `?topic_id=${encodeURIComponent(topicId)}` : ""}`),

  getAudience: (topicId?: string) =>
    request<import("./types").Audience>(
      `/api/audience${topicId ? `?topic_id=${encodeURIComponent(topicId)}` : ""}`
    ),

  getNetwork: () => request<NetworkOutput>("/api/network"),

  getNetworkCommunities: () =>
    request<{ communities: import("./types").CommunityWithMembers[] }>("/api/network/communities"),

  getEvent: (eventId: string) =>
    request<import("./types").CanonicalEvent & { nlp: import("./types").NLPOutput | null }>(
      `/api/events/${encodeURIComponent(eventId)}`
    ),

  createInvestigation: (topicId: string, start?: string, end?: string) =>
    request<Investigation>("/api/investigations", {
      method: "POST",
      body: JSON.stringify({ topic_id: topicId, start, end }),
    }),

  createReport: (investigation: Investigation) =>
    request<Report>("/api/reports", {
      method: "POST",
      body: JSON.stringify({ investigation }),
    }),
};
