import { api, getToken } from "../api.js";
import { useEffect, useState } from "react";

export default function Accounts({ accounts, onChanged }) {
  const [error, setError] = useState("");
  const [me, setMe] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwNotice, setPwNotice] = useState("");

  useEffect(() => {
    api.me().then(setMe).catch(() => {});
  }, []);

  async function savePassword() {
    setPwBusy(true); setPwNotice(""); setError("");
    try {
      const updated = await api.setPassword(newPassword);
      setMe(updated);
      setNewPassword("");
      setPwNotice("Senha salva. A partir de agora, entre com e-mail e senha.");
    } catch (e) {
      setError(e.message);
    } finally {
      setPwBusy(false);
    }
  }

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
      <div className="card" style={{ marginBottom: 18 }}>
        <h3 style={{ fontSize: 16, marginBottom: 4 }}>Acesso</h3>
        {me && (
          <p className="mono" style={{ marginTop: 0 }}>
            {me.email} · plano {me.plan}
            {!me.has_password && getToken() === "" && " · sem senha definida (acesso por API key)"}
          </p>
        )}
        {pwNotice && <div className="notice">{pwNotice}</div>}
        <div className="row">
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="npw">{me?.has_password ? "Alterar senha" : "Definir senha (mín. 8 caracteres)"}</label>
            <input id="npw" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          </div>
        </div>
        <button className="btn primary" style={{ marginTop: 10 }} onClick={savePassword}
          disabled={pwBusy || newPassword.length < 8}>
          {pwBusy ? "Salvando…" : "Salvar senha"}
        </button>
      </div>

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
