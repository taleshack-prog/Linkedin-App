import { useCallback, useEffect, useState } from "react";
import { api, clearAuth, isAuthed } from "./api.js";
import Login from "./views/Login.jsx";
import Queue from "./views/Queue.jsx";
import Calendar from "./views/Calendar.jsx";
import Briefs from "./views/Briefs.jsx";
import Accounts from "./views/Accounts.jsx";
import Profile from "./views/Profile.jsx";
import Billing from "./views/Billing.jsx";
import Privacy from "./views/Privacy.jsx";
import Landing from "./views/Landing.jsx";

// A navegação É o pipeline: os estágios do post são os itens do menu.
const STAGES = [
  { key: "draft", label: "Rascunhos", subtitle: "Revise, edite e aprove antes de qualquer publicação." },
  { key: "approved", label: "Agendados", subtitle: "Aprovados, aguardando o horário de publicação." },
  { key: "published", label: "Publicados", subtitle: "Já no ar, com o URN do LinkedIn para auditoria." },
  { key: "failed", label: "Falhas", subtitle: "Publicações que precisam da sua atenção." },
];

export default function App() {
  // Rotas públicas (sem login): política — exigida pelo LinkedIn e pela LGPD.
  if (typeof window !== "undefined" && window.location.pathname.startsWith("/privacidade")) {
    return <Privacy />;
  }

  const [authed, setAuthed] = useState(isAuthed());
  const [view, setView] = useState("draft");
  const [counts, setCounts] = useState({});
  const [accounts, setAccounts] = useState([]);
  const [features, setFeatures] = useState({});
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const [all, accs, st] = await Promise.all([api.posts(), api.accounts(), api.billingStatus().catch(() => ({}))]);
      const c = {};
      for (const p of all) c[p.status] = (c[p.status] || 0) + 1;
      setCounts(c);
      setAccounts(accs);
      setFeatures(st || {});
      setRefreshKey((k) => k + 1);
    } catch {
      /* 401 já redireciona via api.js */
    }
  }, []);

  useEffect(() => {
    if (authed) refresh();
  }, [authed, refresh]);

  if (!authed) {
    // Visitante na raiz vê a landing; /entrar leva ao login/cadastro.
    // Quem já tem sessão cai direto no app, sem passar pela landing.
    const path = typeof window !== "undefined" ? window.location.pathname : "/";
    if (path === "/" || path === "") return <Landing />;
    return <Login onLogin={() => { window.location.href = "/"; }} />;
  }

  const stage = STAGES.find((s) => s.key === view);

  return (
    <div className="layout">
      <nav className="rail" aria-label="Pipeline de publicação">
        <div className="brand">
          Posthink
          <small>mesa editorial</small>
        </div>

        <div className="stage-label">Produção</div>
        <button className={`nav ${view === "profile" ? "active" : ""}`} onClick={() => setView("profile")}>
          Perfil de marca
        </button>
        <button className={`nav ${view === "briefs" ? "active" : ""}`} onClick={() => setView("briefs")}>
          Pautas
        </button>

        <div className="stage-label">Pipeline</div>
        <div className="pipe">
          {STAGES.map((s) => (
            <button
              key={s.key}
              className={`nav ${view === s.key ? "active" : ""}`}
              onClick={() => { setView(s.key); refresh(); }}
            >
              {s.label}
              <span className={`count ${s.key === "draft" && counts.draft ? "hot" : ""}`}>
                {counts[s.key] || 0}
              </span>
            </button>
          ))}
        </div>

        <div className="stage-label">Visões</div>
        <button className={`nav ${view === "calendar" ? "active" : ""}`} onClick={() => setView("calendar")}>
          Calendário
        </button>
        <button className={`nav ${view === "accounts" ? "active" : ""}`} onClick={() => setView("accounts")}>
          Conta
        </button>
        <button className={`nav ${view === "billing" ? "active" : ""}`} onClick={() => setView("billing")}>
          Planos
        </button>

        <div className="foot">
          <button onClick={() => { clearAuth(); setAuthed(false); }}>Sair</button>
        </div>
      </nav>

      <main className="main">
        {stage && (
          <Queue
            status={stage.key}
            title={stage.label}
            subtitle={stage.subtitle}
            refreshKey={refreshKey}
            canFormat={Boolean(features.text_formatting)}
          />
        )}
        {view === "calendar" && <Calendar refreshKey={refreshKey} />}
        {view === "briefs" && <Briefs accounts={accounts} onGenerated={refresh} />}
        {view === "accounts" && <Accounts accounts={accounts} onChanged={refresh} />}
        {view === "profile" && <Profile />}
        {view === "billing" && <Billing />}
      </main>
    </div>
  );
}
