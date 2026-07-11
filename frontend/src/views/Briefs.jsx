import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const BRIEF_LABEL = {
  pending: "Na fila",
  generating: "Gerando",
  generated: "Concluída",
  failed: "Falhou",
};
const BRIEF_CHIP = { pending: "cancelled", generating: "approved", generated: "published", failed: "failed" };

function BriefCard({ brief, onChanged, onRefreshPipeline }) {
  const [editing, setEditing] = useState(false);
  const [theme, setTheme] = useState(brief.theme);
  const [instructions, setInstructions] = useState(brief.instructions || "");
  const [count, setCount] = useState(brief.posts_per_week);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generating = brief.status === "generating" || brief.status === "pending";

  async function run(fn) {
    setBusy(true); setError("");
    try { await fn(); onChanged(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const saveEdit = () =>
    run(async () => {
      await api.updateBrief(brief.id, {
        theme, instructions: instructions || null, posts_per_week: count,
      });
      setEditing(false);
    });
  const regenerate = () =>
    run(async () => { await api.regenerateBrief(brief.id); onRefreshPipeline(); });
  const remove = () => {
    if (!window.confirm("Excluir esta pauta? Os posts já gerados por ela são preservados.")) return;
    run(() => api.deleteBrief(brief.id));
  };

  return (
    <article className={`card ${BRIEF_CHIP[brief.status] === "failed" ? "failed" : ""}`}>
      <div className="meta">
        <span className={`chip ${BRIEF_CHIP[brief.status] || "cancelled"}`}>{BRIEF_LABEL[brief.status] || brief.status}</span>
        <span className="mono">{new Date(brief.created_at).toLocaleString("pt-BR")}</span>
        <span className="mono">{brief.posts_per_week} posts</span>
        {brief.source_filename && <span className="mono">📎 {brief.source_filename}</span>}
      </div>
      {error && <div className="error">{error}</div>}

      {editing ? (
        <>
          <div className="field">
            <label htmlFor={`bt-${brief.id}`}>Tema</label>
            <input id={`bt-${brief.id}`} value={theme} onChange={(e) => setTheme(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`bi-${brief.id}`}>Instruções</label>
            <textarea id={`bi-${brief.id}`} style={{ minHeight: 60 }} value={instructions}
              onChange={(e) => setInstructions(e.target.value)} />
          </div>
          <div className="field" style={{ maxWidth: 200 }}>
            <label htmlFor={`bc-${brief.id}`}>Quantidade de posts</label>
            <select id={`bc-${brief.id}`} value={count} onChange={(e) => setCount(Number(e.target.value))}>
              {[1, 2, 3, 4, 5, 6, 7].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div className="actions">
            <button className="btn primary" onClick={saveEdit} disabled={busy || theme.trim().length < 3}>
              Salvar pauta
            </button>
            <button className="btn" onClick={() => setEditing(false)} disabled={busy}>Descartar</button>
          </div>
        </>
      ) : (
        <>
          <p className="commentary" style={{ marginBottom: 0 }}><strong>{brief.theme}</strong></p>
          {brief.instructions && (
            <p className="commentary" style={{ marginBottom: 0, color: "var(--ink-soft)", fontSize: 14 }}>
              {brief.instructions}
            </p>
          )}
          {brief.error && <div className="error" style={{ marginTop: 10 }}>{brief.error}</div>}
          <div className="actions" style={{ marginTop: 12 }}>
            <button className="btn" onClick={() => setEditing(true)} disabled={busy || generating}>Editar</button>
            <button className="btn" onClick={regenerate} disabled={busy || generating}>
              {brief.status === "failed" ? "Tentar novamente" : "Gerar novamente"}
            </button>
            <button className="btn danger" onClick={remove} disabled={busy || generating}>Excluir</button>
          </div>
        </>
      )}
    </article>
  );
}

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
            <label htmlFor="source">Material de referência — opcional (PDF, DOCX, TXT, MD ou CSV, até 25 MB)</label>
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
        <BriefCard key={b.id} brief={b} onChanged={load} onRefreshPipeline={onGenerated} />
      ))}
    </>
  );
}
