import { useState } from "react";
import { api, setApiKey } from "../api.js";

export default function Login({ onLogin }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError("");
    setApiKey(key.trim());
    try {
      await api.accounts(); // valida a chave contra um endpoint autenticado
      onLogin();
    } catch (e) {
      setError(e.message || "Não foi possível validar a chave.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login">
      <div className="box">
        <h1>LinkPost AI</h1>
        <p>Cole sua API key para abrir a mesa editorial.</p>
        {error && <div className="notice err">{error}</div>}
        <div className="field">
          <label htmlFor="apikey">API key</label>
          <input
            id="apikey"
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && key && submit()}
            placeholder="chave gerada no setup do backend"
            autoFocus
          />
        </div>
        <button className="btn primary" onClick={submit} disabled={!key || loading}>
          {loading ? "Validando…" : "Entrar"}
        </button>
      </div>
    </div>
  );
}
