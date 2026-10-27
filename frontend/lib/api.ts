export type Character = {
  preset: "leaf_spirit" | "gardener" | "scientist" | "forest_guide" | "custom";
  name: string;
  primary_color: string;
  secondary_color: string;
  accessory: "leaf_crown" | "hat" | "glasses" | "basket" | "lantern" | "none";
  greeting: string;
};

export type User = {
  id: string;
  email: string | null;
  phone: string | null;
  display_name: string;
  role: string;
  privacy: "public" | "friends_only" | "private";
  character: Character;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type DashboardStats = {
  plants_identified: number;
  unique_species: number;
  photos_this_week: number;
  photos_this_month: number;
  daily_streak: number;
  today_task_complete: boolean;
  caring_rate: number;
  caring_badge: "Low" | "Medium" | "High" | "Excellent";
  people_online: number;
  phase: string;
  note: string;
};

const TOKEN_KEY = "plantmitra_token";

export function getApiUrl() {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setSession(token: string, user: User) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem("plantmitra_user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem("plantmitra_user");
}

export function readCachedUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("plantmitra_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${getApiUrl()}${path}`, { ...init, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Request failed";
    throw new Error(detail);
  }
  return data as T;
}

export const api = {
  signup: (body: {
    display_name: string;
    email?: string;
    phone?: string;
    password: string;
  }) => request<TokenResponse>("/auth/signup", { method: "POST", body: JSON.stringify(body) }),
  login: (identifier: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ identifier, password }),
    }),
  me: () => request<User>("/users/me"),
  updateMe: (body: { display_name?: string; privacy?: User["privacy"]; character?: Character }) =>
    request<User>("/users/me", { method: "PATCH", body: JSON.stringify(body) }),
  dashboard: () => request<DashboardStats>("/dashboard/me"),
  identifyPlant: (body: FormData) => request<PlantIdentification>("/api/ai/identify", { method: "POST", body }),
  observations: () => request<{ observations: import("@/lib/observations").PlantObservation[] }>("/api/observations"),
  saveObservation: (body: FormData) => request<import("@/lib/observations").PlantObservation>("/api/observations", { method: "POST", body }),
  deleteObservation: (id: number) => request<{ success: boolean }>(`/api/observations/${id}`, { method: "DELETE" }),
  referenceObservations: (scientificName: string) => request<ReferenceResponse>(`/api/reference-observations?scientific_name=${encodeURIComponent(scientificName)}`),
};

export type PlantInformation = {
  common_name: string;
  scientific_name: string;
  taxonomy_note?: string;
  family: string;
  description: string;
  plant_type: string;
  plant_parts: string[];
  habitat: string;
  distribution: string;
  traditional_uses: string[];
  sources: string[];
};

export type PlantIdentification = {
  success: boolean;
  supported: boolean;
  predicted_class: string | null;
  dataset_label: string | null;
  scientific_name: string | null;
  confidence: number;
  confidence_note: string;
  model_version: string;
  message: string | null;
  top_predictions: Array<{ class: string; confidence: number }>;
  plant_information?: PlantInformation | null;
};

export type ReferenceResponse = {
  source: string;
  source_url: string;
  observations: Array<{
    id: number;
    image: string;
    date: string | number | null;
    location: string;
    source: string;
    source_url: string;
    license: string;
    attribution: string;
    scientific_name: string;
  }>;
};
