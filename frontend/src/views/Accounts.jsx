import { api, clearAuth, getToken } from "../api.js";
import { useEffect, useState } from "react";

export default function Accounts({ accounts, onChanged }) {
  const [error, setError] = useState("");
  const [me, setMe] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwNotice, setPwNotice] = useState("");
  const [confirmDel, setConfirmDel] = useState("");
  const [delOpen, setDelOpen] = useState(false);
  const [delBusy, setDelBusy] = useState(false);

  async function exportData() {
    setError("");
    try {
      const data = await api.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `posthink-meus-dados-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    }
  }

  async function deleteAccount() {
    setDelBusy(true); setError("");
    try {
      await api.deleteAccount(confirmDel);
      clearAuth();
      window.location.href = "/";
    } catch (e) {
      setError(e.message);
      setDelBusy(false);
    }
  }

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

      <div className="card" style={{ marginTop: 22 }}>
        <h3 style={{ fontSize: 16, marginBottom: 4 }}>Seus dados</h3>
        <p style={{ marginTop: 0, color: "var(--ink-soft)", fontSize: 14 }}>
          Você é dono dos seus dados. Leve-os embora ou apague tudo, quando quiser —
          veja a <a href="/privacidade" target="_blank" rel="noreferrer">Política de Privacidade</a>.
        </p>
        <div className="actions">
          <button className="btn" onClick={exportData}>Exportar meus dados (JSON)</button>
          <button className="btn danger" onClick={() => setDelOpen((o) => !o)}>
            Excluir minha conta
          </button>
        </div>

        {delOpen && (
          <div className="danger-zone">
            <p style={{ marginTop: 0 }}>
              <strong>Isto é definitivo.</strong> Apagamos sua conta, pautas, posts, imagens e
              perfil; revogamos o acesso ao seu LinkedIn e cancelamos sua assinatura.
              Posts já publicados permanecem no seu LinkedIn — só você pode removê-los por lá.
            </p>
            <div className="ai-form">
              <input
                value={confirmDel}
                onChange={(e) => setConfirmDel(e.target.value)}
                placeholder="Digite EXCLUIR para confirmar"
              />
              <button className="btn danger" onClick={deleteAccount}
                disabled={delBusy || confirmDel.trim().toUpperCase() !== "EXCLUIR"}>
                {delBusy ? "Excluindo…" : "Excluir definitivamente"}
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}