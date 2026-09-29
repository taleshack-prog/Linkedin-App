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
import Paywall from "./views/Paywall.jsx";
import Health from "./views/Health.jsx";
import Mesa from "./views/Mesa.jsx";
import Audit from "./views/Audit.jsx";

// Tela de abertura. "inicio" = Mesa (canvas de nós); "draft" = direto nos rascunhos.
const TELA_INICIAL = "inicio";

// A navegação É o pipeline: os estágios do post são os itens do menu.
const STAGES = [
  { key: "draft", label: "Rascunhos", subtitle: "Revise, edite e aprove antes de qualquer publicação." },
  { key: "approved", label: "Agendados", subtitle: "Aprovados, aguardando o horário de publicação." },
  { key: "published", label: "Publicados", subtitle: "Já no ar, com o URN do LinkedIn para auditoria." },
  { key: "failed", label: "Falhas", subtitle: "Publicações que precisam da sua atenção." },
];

const TITULOS = {
  inicio: "Mesa",
  perfil: "Perfil de marca",
  audit: "Auditoria",
  briefs: "Pautas",
  calendar: "Calendário",
  accounts: "Contas",
  billing: "Planos",
  health: "Saúde",
};

// Preferências locais (tema e lateral) — localStorage pode falhar em janela privada.
function lerPref(chave) {
  try { return localStorage.getItem(chave); } catch { return null; }
}
function gravarPref(chave, valor) {
  try { localStorage.setItem(chave, valor); } catch { /* sem persistência, segue */ }
}

function Ico({ d }) {
  return (
    <span className="ico" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
           strokeLinecap="round" strokeLinejoin="round">{d}</svg>
    </span>
  );
}

const ICONES = {
  inicio: <><rect x="4" y="4" width="7" height="7" /><rect x="13" y="4" width="7" height="7" /><rect x="4" y="13" width="7" height="7" /><rect x="13" y="13" width="7" height="7" /></>,
  perfil: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" /></>,
  briefs: <><path d="M5 4h11l3 3v13H5z" /><path d="M8 11h8M8 15h5" /></>,
  audit: <><circle cx="11" cy="11" r="6" /><path d="M20 20l-4.5-4.5M9 11h4M11 9v4" /></>,
  draft: <><path d="M4 20h16" /><path d="M14 4l6 6-9 9H5v-6z" /></>,
  approved: <><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></>,
  published: <><path d="M4 12.5l5 5L20 6.5" /></>,
  failed: <><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17h.01" /></>,
  calendar: <><rect x="4" y="5" width="16" height="15" /><path d="M4 10h16M9 3v4M15 3v4" /></>,
  accounts: <><rect x="3" y="5" width="18" height="14" /><path d="M7 9h4v7H7zM15 16v-4M15 13c0-1.5 3-1.5 3 0v3" /></>,
  billing: <><rect x="3" y="6" width="18" height="12" /><path d="M3 10h18" /></>,
  health: <><path d="M3 13h4l2-5 3 10 2.5-6 1.5 3h5" /></>,
};

function ItemNav({ chave, rotulo, contagem, quente, view, ir, recolhido }) {
  return (
    <button
      className={`nav ${view === chave ? "active" : ""}`}
      onClick={() => ir(chave)}
      title={recolhido ? rotulo : undefined}
    >
      <Ico d={ICONES[chave]} />
      <span className="rotulo">{rotulo}</span>
      {contagem !== undefined && (
        <span className={`count ${quente ? "hot" : ""}`}>{contagem}</span>
      )}
    </button>
  );
}

export default function App() {
  // Rotas públicas (sem login): política — exigida pelo LinkedIn e pela LGPD.
  if (typeof window !== "undefined" && window.location.pathname.startsWith("/privacidade")) {
    return <Privacy />;
  }

  const [authed, setAuthed] = useState(isAuthed());
  const [view, setView] = useState(TELA_INICIAL);
  const [counts, setCounts] = useState({});
  const [accounts, setAccounts] = useState([]);
  const [features, setFeatures] = useState({});
  const [carregando, setCarregando] = useState(true);   // evita piscar o paywall p/ quem já paga
  const [refreshKey, setRefreshKey] = useState(0);
  const [isAdmin, setIsAdmin] = useState(false);
  const [recolhido, setRecolhido] = useState(() => lerPref("posthink_rail") === "1");
  const [auditoria, setAuditoria] = useState(null);
  const [tema, setTema] = useState(() => {
    const salvo = lerPref("posthink_tema");
    if (salvo === "claro" || salvo === "escuro") return salvo;
    if (typeof window !== "undefined" && window.matchMedia) {
      return window.matchMedia("(prefers-color-scheme: light)").matches ? "claro" : "escuro";
    }
    return "escuro";
  });

  // O tema vive no <html> para alcançar body, landing e páginas públicas.
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.dataset.tema = tema;
    gravarPref("posthink_tema", tema);
  }, [tema]);

  useEffect(() => { gravarPref("posthink_rail", recolhido ? "1" : "0"); }, [recolhido]);

  const refresh = useCallback(async () => {
    try {
      const [all, accs, st, me] = await Promise.all([api.posts(), api.accounts(), api.billingStatus().catch(() => ({})), api.me().catch(() => ({}))]);
      const c = {};
      for (const p of all) c[p.status] = (c[p.status] || 0) + 1;
      setCounts(c);
      setAccounts(accs);
      setFeatures(st || {});
      setIsAdmin(Boolean(me && me.is_admin));
      api.audit().then(setAuditoria).catch(() => {});
      setCarregando(false);
      setRefreshKey((k) => k + 1);
    } catch {
      /* 401 já redireciona via api.js */
      setCarregando(false);
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

  // Sem assinatura ativa, não há serviço: o núcleo custa API por uso.
  if (carregando) {
    return <div className="paywall"><div className="paywall-box confirmando"><p>Carregando…</p></div></div>;
  }
  if (features.plan === "free") {
    return <Paywall onAtivou={() => { setCarregando(true); refresh(); }} />;
  }

  const stage = STAGES.find((s) => s.key === view);
  const titulo = stage ? stage.label : (TITULOS[view] || "");

  const ir = (chave) => {
    setView(chave);
    if (STAGES.some((s) => s.key === chave)) refresh();
  };

  return (
    <div className={`layout ${recolhido ? "recolhido" : ""}`}>
      <nav className="rail" aria-label="Navegação do Posthink">
        <div className="rail-topo">
          <button className="brand" onClick={() => ir("inicio")} title="Mesa">
            Posthink
            <small>mesa editorial</small>
          </button>
          <button
            className="quadrado recolher"
            onClick={() => setRecolhido((v) => !v)}
            aria-label={recolhido ? "Expandir a barra lateral" : "Recolher a barra lateral"}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"
                 strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>
          </button>
        </div>

        <ItemNav view={view} ir={ir} recolhido={recolhido} chave="inicio" rotulo="Mesa" />

        <div className="stage-label">Produção</div>
        <ItemNav view={view} ir={ir} recolhido={recolhido} chave="perfil" rotulo="Perfil de marca" />
        <ItemNav view={view} ir={ir} recolhido={recolhido} chave="audit" rotulo="Auditoria" />
        <ItemNav view={view} ir={ir} recolhido={recolhido} chave="briefs" rotulo="Pautas" />

        <div className="stage-label">Pipeline</div>
        <div className="pipe">
          {STAGES.map((s) => (
            <ItemNav
              key={s.key}
              view={view} ir={ir} recolhido={recolhido}
              chave={s.key}
              rotulo={s.label}
              contagem={counts[s.key] || 0}
              quente={s.key === "draft" && Boolean(counts.draft)}
            />
          ))}
        </div>

        <div className="stage-label">Visões</div>
        <ItemNav view={view} ir={ir} recolhido={recolhido} chave="calendar" rotulo="Calendário" />
        <ItemNav view={view} ir={ir} recolhido={recolhido} chave="accounts" rotulo="Contas" contagem={accounts.length} />
        <ItemNav view={view} ir={ir} recolhido={recolhido} chave="billing" rotulo="Planos" />
        {isAdmin && <ItemNav view={view} ir={ir} recolhido={recolhido} chave="health" rotulo="Saúde" />}

        <div className="foot">
          <button onClick={() => { clearAuth(); setAuthed(false); }}>Sair</button>
        </div>
      </nav>

      <div className="pane">
        <header className="topbar">
          <nav className="trilha" aria-label="Você está em">
            {view === "inicio" ? (
              <span className="atual">Mesa</span>
            ) : (
              <>
                <button onClick={() => ir("inicio")}>Mesa</button>
                <span aria-hidden="true">/</span>
                <span className="atual">{titulo}</span>
              </>
            )}
          </nav>
          <button
            className="quadrado tema"
            onClick={() => setTema((t) => (t === "claro" ? "escuro" : "claro"))}
            aria-label={tema === "claro" ? "Usar tema escuro" : "Usar tema claro"}
            title={tema === "claro" ? "Tema escuro" : "Tema claro"}
          >
            {tema === "claro" ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
                   strokeLinecap="round" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z" /></svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
                   strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4" /></svg>
            )}
          </button>
        </header>

        <main className={`main ${view === "inicio" ? "larga" : ""}`}>
          {view === "inicio" && (
            <Mesa
              counts={counts}
              accounts={accounts}
              features={features}
              isAdmin={isAdmin}
              auditoria={auditoria}
              onAbrir={ir}
            />
          )}
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
          {view === "perfil" && <Profile />}
          {view === "audit" && <Audit />}
          {view === "billing" && <Billing />}
          {view === "health" && isAdmin && <Health />}
        </main>
      </div>
    </div>
  );
}
