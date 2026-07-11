// Cliente da API LinkPost. Auth: header X-API-Key (guardada em localStorage).
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function getApiKey() {
  return localStorage.getItem("linkpost_api_key") || "";
}
export function setApiKey(key) {
  localStorage.setItem("linkpost_api_key", key);
}
export function clearApiKey() {
  localStorage.removeItem("linkpost_api_key");
}

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "X-API-Key": getApiKey(),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (resp.status === 401) {
    clearApiKey();
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
  return resp.json();
}

export const api = {
  health: () => request("/health"),
  accounts: () => request("/accounts"),
  linkedinLogin: () => request("/auth/linkedin/login"),
  briefs: () => request("/briefs"),
  createBrief: (payload) => request("/briefs", { method: "POST", body: JSON.stringify(payload) }),
  posts: (status) => request(`/posts${status ? `?status=${status}` : ""}`),
  editPost: (id, payload) => request(`/posts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  approvePost: (id, publishAt) =>
    request(`/posts/${id}/approve`, { method: "POST", body: JSON.stringify({ publish_at: publishAt }) }),
  cancelPost: (id) => request(`/posts/${id}/cancel`, { method: "POST" }),
  uploadPostImage: async (id, file) => {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${BASE}/posts/${id}/image`, {
      method: "POST",
      headers: { "X-API-Key": getApiKey() },   // sem Content-Type: o browser define o boundary
      body: form,
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.detail || `Erro ${resp.status}`);
    }
    return resp.json();
  },
  deletePostImage: (id) => request(`/posts/${id}/image`, { method: "DELETE" }),
  fetchPostImageBlob: async (id) => {
    const resp = await fetch(`${BASE}/posts/${id}/image`, { headers: { "X-API-Key": getApiKey() } });
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
