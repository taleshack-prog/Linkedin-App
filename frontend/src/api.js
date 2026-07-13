// Cliente da API LinkPost.
// Auth: JWT (Authorization: Bearer) — com fallback legado por X-API-Key na transição.
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function getToken() {
  return localStorage.getItem("linkpost_token") || "";
}
export function setToken(t) {
  localStorage.setItem("linkpost_token", t);
}
export function getApiKey() {
  return localStorage.getItem("linkpost_api_key") || "";
}
export function setApiKey(key) {
  localStorage.setItem("linkpost_api_key", key);
}
export function clearAuth() {
  localStorage.removeItem("linkpost_token");
  localStorage.removeItem("linkpost_api_key");
}
export function isAuthed() {
  return Boolean(getToken() || getApiKey());
}
export function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : { "X-API-Key": getApiKey() };
}

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (resp.status === 401 && !path.startsWith("/auth/")) {
    clearAuth();
    window.location.reload();
    return null;
  }
  if (!resp.ok) {
    let detail = `Erro ${resp.status}`;
    try {
      const data = await resp.json();
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch { /* corpo não-JSON */ }
    throw new Error(detail);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

export const api = {
  health: () => request("/health"),
  // ---- auth ----
  register: (email, password, name, ref) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ email, password, name: name || null, ref: ref || null }) }),
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  loginGoogle: (credential, ref) =>
    request("/auth/google", { method: "POST", body: JSON.stringify({ credential, ref: ref || null }) }),
  setPassword: (password) =>
    request("/auth/set-password", { method: "POST", body: JSON.stringify({ password }) }),
  me: () => request("/auth/me"),
  billingStatus: () => request("/billing/status"),
  billingPlans: () => request("/billing/plans"),
  checkout: (plan) => request("/billing/checkout", { method: "POST", body: JSON.stringify({ plan }) }),
  billingPortal: () => request("/billing/portal", { method: "POST" }),
  // ---- app ----
  accounts: () => request("/accounts"),
  getProfile: () => request("/profile"),
  saveProfile: (payload) => request("/profile", { method: "PUT", body: JSON.stringify(payload) }),
  linkedinLogin: () => request("/auth/linkedin/login"),
  briefs: () => request("/briefs"),
  updateBrief: (id, payload) => request(`/briefs/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  regenerateBrief: (id) => request(`/briefs/${id}/regenerate`, { method: "POST" }),
  deleteBrief: (id) => request(`/briefs/${id}`, { method: "DELETE" }),
  createBrief: async (payload, file) => {
    const form = new FormData();
    Object.entries(payload).forEach(([k, v]) => v != null && form.append(k, v));
    if (file) form.append("source_file", file);
    const resp = await fetch(`${BASE}/briefs`, { method: "POST", headers: authHeaders(), body: form });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : `Erro ${resp.status}`);
    }
    return resp.json();
  },
  posts: (status) => request(`/posts${status ? `?status=${status}` : ""}`),
  editPost: (id, payload) => request(`/posts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  approvePost: (id, publishAt) =>
    request(`/posts/${id}/approve`, { method: "POST", body: JSON.stringify({ publish_at: publishAt }) }),
  cancelPost: (id) => request(`/posts/${id}/cancel`, { method: "POST" }),
  generatePostImage: (id, instructions) =>
    request(`/posts/${id}/generate-image`, { method: "POST", body: JSON.stringify({ instructions: instructions || null }) }),
  deletePostImage: (id) => request(`/posts/${id}/image`, { method: "DELETE" }),
  uploadPostImage: async (id, file) => {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${BASE}/posts/${id}/image`, { method: "POST", headers: authHeaders(), body: form });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.detail || `Erro ${resp.status}`);
    }
    return resp.json();
  },
  fetchPostImageBlob: async (id) => {
    const resp = await fetch(`${BASE}/posts/${id}/image`, { headers: authHeaders() });
    if (!resp.ok) throw new Error(`Erro ${resp.status}`);
    return resp.blob();
  },
};

export const STATUS_LABEL = {
  draft: "Rascunho",
  approved: "Agendado",
  publishing: "Publicando",
  published: "Publicado",
  failed: "Falhou",
  cancelled: "Cancelado",
};
