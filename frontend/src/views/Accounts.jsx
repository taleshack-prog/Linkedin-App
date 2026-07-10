import { api } from "../api.js";
import { useState } from "react";

export default function Accounts({ accounts, onChanged }) {
  const [error, setError] = useState("");

  async function connect() {
    setError("");
    try {
      const { authorize_url } = await api.linkedinLogin();
      window.open(authorize_url, "_blank", "noopener");
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <>
      <header>
        <h2>Conta</h2>
        <p>Contas LinkedIn autorizadas a publicar. Os tokens ficam criptografados no servidor.</p>
      </header>
      {error && <div className="notice err">{error}</div>}
      <div className="actions" style={{ marginBottom: 18 }}>
        <button className="btn primary" onClick={connect}>Conectar conta LinkedIn</button>
        <button className="btn" onClick={onChanged}>Atualizar lista</button>
      </div>
      {accounts.length === 0 && (
        <div className="empty">Nenhuma conta conectada. Conecte para começar a publicar.</div>
      )}
      {accounts.map((a) => {
        const days = Math.floor((new Date(a.access_expires_at) - Date.now()) / 86400000);
        const ok = a.status === "active";
        return (
          <article key={a.id} className={`card ${ok ? "published" : "failed"}`}>
            <div className="meta">
              <span className={`chip ${ok ? "published" : "failed"}`}>
                {ok ? "Ativa" : "Reautenticação necessária"}
              </span>
              <span className="mono">{a.person_urn}</span>
            </div>
            <p className="commentary" style={{ marginBottom: 4 }}>
              <strong>{a.display_name || "Sem nome"}</strong>
            </p>
            <span className="mono">
              {ok ? `token expira em ${days} dia${days === 1 ? "" : "s"}` : "reconecte pelo botão acima"}
            </span>
          </article>
        );
      })}
    </>
  );
}
