import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const BRIEF_LABEL = {
  pending: "Na fila",
  generating: "Gerando",
  generated: "Concluída",
  failed: "Falhou",
};
const BRIEF_CHIP = { pending: "cancelled", generating: "approved", generated: "published", failed: "failed" };

export default function Briefs({ accounts, onGenerated }) {
  const [briefs, setBriefs] = useState([]);
  const [theme, setTheme] = useState("");
  const [instructions, setInstructions] = useState("");
  const [count, setCount] = useState(3);
  const [accountId, setAccountId] = useState("");
  const [file, setFile] = useState(null);
  const fileInput = useRef(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = () => api.briefs().then(setBriefs).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    const t = setInterval(() => {
      load();
      onGenerated(); // atualiza contagens do pipeline enquanto gera
    }, 8000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!accountId && accounts.length) setAccountId(accounts[0].id);
  }, [accounts]);

  async function create() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.createBrief(
        {
          theme,
          instructions: instructions || null,
          posts_per_week: count,
          language: "pt-BR",
          linkedin_account_id: accountId,
        },
        file
      );
      setTheme("");
      setInstructions("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setNotice("Pauta enviada. A IA pesquisa o tema e os rascunhos aparecem em Rascunhos.");
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header>
        <h2>Pautas</h2>
        <p>Informe um tema; a IA pesquisa na web e escreve os rascunhos para sua revisão.</p>
      </header>
      {notice && <div className="notice">{notice}</div>}
      {error && <div className="notice err">{error}</div>}

      {accounts.length === 0 ? (
        <div className="empty">Conecte uma conta LinkedIn em “Conta” antes de criar pautas.</div>
      ) : (
        <div className="card">
          <div className="field">
            <label htmlFor="theme">Tema</label>
            <input
              id="theme"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder="ex.: tendências em Web3 no Brasil"
            />
          </div>
          <div className="field">
            <label htmlFor="instr">Instruções (tom de voz, CTA, persona) — opcional</label>
            <textarea
              id="instr"
              style={{ minHeight: 70 }}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="count">Quantidade de posts</label>
              <select id="count" value={count} onChange={(e) => setCount(Number(e.target.value))}>
                {[1, 2, 3, 4, 5, 6, 7].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="acc">Conta LinkedIn</label>
              <select id="acc" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.display_name || a.person_urn}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="source">Material de referência — opcional (PDF, DOCX, TXT, MD ou CSV, até 10 MB)</label>
            <input
              id="source"
              ref={fileInput}
              type="file"
              accept=".pdf,.docx,.txt,.md,.csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file && (
              <span className="mono" style={{ display: "block", marginTop: 4 }}>
                A IA vai basear os posts em: {file.name}
              </span>
            )}
          </div>
          <button className="btn primary" onClick={create} disabled={busy || theme.trim().length < 3}>
            {busy ? "Enviando…" : "Gerar rascunhos"}
          </button>
        </div>
      )}

      {briefs.map((b) => (
        <article key={b.id} className={`card ${BRIEF_CHIP[b.status] === "failed" ? "failed" : ""}`}>
          <div className="meta">
            <span className={`chip ${BRIEF_CHIP[b.status] || "cancelled"}`}>{BRIEF_LABEL[b.status] || b.status}</span>
            <span className="mono">{new Date(b.created_at).toLocaleString("pt-BR")}</span>
            <span className="mono">{b.posts_per_week} posts</span>
            {b.source_filename && <span className="mono">📎 {b.source_filename}</span>}
          </div>
          <p className="commentary" style={{ marginBottom: 0 }}><strong>{b.theme}</strong></p>
          {b.error && <div className="error" style={{ marginTop: 10 }}>{b.error}</div>}
        </article>
      ))}
    </>
  );
}
