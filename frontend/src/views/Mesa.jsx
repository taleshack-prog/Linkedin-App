import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { piorEstado } from "../conexao.js";

/* Mesa — o canvas de nós. Cada nó é uma tela; os fios são o caminho real
   do post (pauta -> rascunho -> agendado -> publicado, com falha ramificando).
   Calendário, Planos e Saúde ficam sem fio: são visões, não etapas. */

const ARESTAS = [
  ["audit", "perfil"],
  ["perfil", "briefs"],
  ["briefs", "draft"],
  ["draft", "approved"],
  ["approved", "published"],
  ["approved", "failed"],
  ["accounts", "published"],
];

export default function Mesa({ counts = {}, accounts = [], features = {}, isAdmin, auditoria, onAbrir }) {
  const grafoRef = useRef(null);
  const nosRef = useRef({});
  const [fios, setFios] = useState([]);
  const [medidas, setMedidas] = useState({ w: 0, h: 0 });

  const registrar = (chave) => (el) => { nosRef.current[chave] = el; };

  const desenhar = useCallback(() => {
    const grafo = grafoRef.current;
    if (!grafo || typeof window === "undefined") return;
    const base = grafo.getBoundingClientRect();
    setMedidas((v) => (v.w === base.width && v.h === base.height ? v : { w: base.width, h: base.height }));
    if (window.innerWidth <= 1040) { setFios([]); return; }

    const novos = [];
    for (const [a, b] of ARESTAS) {
      const ea = nosRef.current[a];
      const eb = nosRef.current[b];
      if (!ea || !eb) continue;
      const ra = ea.getBoundingClientRect();
      const rb = eb.getBoundingClientRect();
      const horizontal = Math.abs(rb.left - ra.left) > Math.abs(rb.top - ra.top);
      let x1, y1, x2, y2, curva;
      if (horizontal) {
        x1 = ra.right - base.left; y1 = ra.top + ra.height / 2 - base.top;
        x2 = rb.left - base.left;  y2 = rb.top + rb.height / 2 - base.top;
        const m = Math.max(18, (x2 - x1) * 0.5);
        curva = `C ${x1 + m} ${y1} ${x2 - m} ${y2}`;
      } else {
        x1 = ra.left + ra.width / 2 - base.left; y1 = ra.bottom - base.top;
        x2 = rb.left + rb.width / 2 - base.left; y2 = rb.top - base.top;
        const m = Math.max(16, (y2 - y1) * 0.5);
        curva = `C ${x1} ${y1 + m} ${x2} ${y2 - m}`;
      }
      novos.push({ id: `${a}-${b}`, d: `M ${x1} ${y1} ${curva} ${x2} ${y2}`, cx: x2, cy: y2 });
    }
    setFios(novos);
  }, []);

  useLayoutEffect(() => { desenhar(); }, [desenhar, counts, accounts, isAdmin]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.addEventListener("resize", desenhar);
    let ro;
    if (window.ResizeObserver && grafoRef.current) {
      ro = new ResizeObserver(desenhar);
      ro.observe(grafoRef.current);
    }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(desenhar);
    return () => {
      window.removeEventListener("resize", desenhar);
      if (ro) ro.disconnect();
    };
  }, [desenhar]);

  const n = (k) => counts[k] || 0;
  const naFila = n("approved") + n("publishing");
  const problema = accounts.filter((a) => a.status && a.status !== "active");
  // A conexão morre sozinha em ~60 dias (ver conexao.js). Avisar só quando já
  // morreu é avisar tarde: a essa altura a pessoa já agendou no vazio.
  const conexao = piorEstado(accounts);
  const expirando = !problema.length && conexao.chave === "expirando";
  const plano = features.plan_name || features.plan || null;

  return (
    <section className="mesa">
      <header className="mesa-cabeca">
        <div>
          <h2>Mesa</h2>
          <p>O estado da operação agora. Um clique em qualquer nó abre a tela.</p>
        </div>
        <div className="mesa-legenda">
          <span><i className="ponto draft" />aguardando você</span>
          <span><i className="ponto approved" />na fila</span>
          <span><i className="ponto published" />ok</span>
          <span><i className="ponto failed" />atenção</span>
        </div>
      </header>

      <div className="grafo" ref={grafoRef}>
        <svg className="fios" aria-hidden="true" viewBox={`0 0 ${medidas.w} ${medidas.h}`}>
          {fios.map((f) => (
            <g key={f.id}>
              <path d={f.d} />
              <circle cx={f.cx} cy={f.cy} r="2.5" />
            </g>
          ))}
        </svg>

        <div className="nos">
          <No chave="audit" classe="no-audit" refEl={registrar("audit")} onAbrir={onAbrir}
              tipo={auditoria ? "diagnóstico" : "nunca auditado"}
              cor={auditoria ? "published" : "muted"}
              alerta={!auditoria}
              titulo="Auditoria" numero={auditoria?.score_total ?? undefined}
              estado={auditoria
                ? "Score do seu perfil e do seu conteúdo, com o que fazer a seguir."
                : "Suba o PDF do seu perfil e receba o diagnóstico da sua marca."}
              pe={auditoria
                ? `de ${new Date(auditoria.created_at).toLocaleDateString("pt-BR")}`
                : "nenhuma auditoria ainda"} />

          <No chave="perfil" classe="no-perfil" refEl={registrar("perfil")} onAbrir={onAbrir}
              tipo="define o ângulo" titulo="Perfil de marca"
              estado="Para quem você escreve e o que quer construir." />

          <No chave="accounts" classe="no-accounts" refEl={registrar("accounts")} onAbrir={onAbrir}
              tipo={problema.length ? "ação necessária" : expirando ? "expira em breve" : "autoriza a publicação"}
              alerta={problema.length > 0 || Boolean(expirando)}
              cor={problema.length ? "failed" : expirando ? "draft" : "published"}
              titulo="Contas LinkedIn" numero={accounts.length}
              estado={problema.length
                ? `${problema.length === 1 ? "Uma conta precisa" : `${problema.length} contas precisam`} reconectar — o token expirou e só o dono renova.`
                : expirando
                  ? `A conexão expira em ${conexao.dias} dia${conexao.dias === 1 ? "" : "s"}. Depois disso as publicações param até você reconectar.`
                  : "Publicamos pelo canal oficial, com a sua autorização."}
              pe={accounts.length ? `${accounts.length - problema.length} de ${accounts.length} ativas` : "nenhuma conta conectada"} />

          {isAdmin && (
            <No chave="health" classe="no-health" refEl={registrar("health")} onAbrir={onAbrir}
                tipo="admin" cor="published" titulo="Saúde"
                estado="Banco, migrações, Redis, worker, beat e fila." />
          )}

          <No chave="briefs" classe="no-briefs" refEl={registrar("briefs")} onAbrir={onAbrir}
              tipo="entrada" titulo="Pautas"
              estado="O tema que você dá. Aceita PDF e relatório como material." />

          <No chave="draft" classe="no-draft" refEl={registrar("draft")} onAbrir={onAbrir}
              tipo="aguardando você" cor="draft" titulo="Rascunhos" numero={n("draft")}
              estado="Escritos pela IA, esperando revisão e horário." />

          <No chave="approved" classe="no-approved" refEl={registrar("approved")} onAbrir={onAbrir}
              tipo="na fila" cor="approved" titulo="Agendados" numero={naFila}
              estado="Aprovados por você, aguardando o horário." />

          <No chave="published" classe="no-published" refEl={registrar("published")} onAbrir={onAbrir}
              tipo="no ar" cor="published" titulo="Publicados" numero={n("published")}
              estado="No LinkedIn, com URN para auditoria." />

          <No chave="calendar" classe="no-calendar" refEl={registrar("calendar")} onAbrir={onAbrir}
              tipo="visão" titulo="Calendário"
              estado="A semana inteira, com o que já está marcado." />

          <No chave="failed" classe="no-failed" refEl={registrar("failed")} onAbrir={onAbrir}
              tipo={n("failed") ? "atenção" : "sem falhas"}
              cor={n("failed") ? "failed" : "muted"}
              alerta={n("failed") > 0}
              titulo="Falhas" numero={n("failed")}
              estado={n("failed") ? "Publicação recusada pelo LinkedIn." : "Nada recusado pelo LinkedIn."} />

          <No chave="billing" classe="no-billing" refEl={registrar("billing")} onAbrir={onAbrir}
              tipo="ativo" cor="published" titulo="Planos"
              estado="Cota de geração, contas e recursos do seu plano."
              pe={plano ? `plano ${plano}` : null} />
        </div>
      </div>
    </section>
  );
}

function No({ chave, classe, refEl, onAbrir, tipo, cor, titulo, numero, estado, pe, alerta }) {
  return (
    <button
      type="button"
      ref={refEl}
      className={`no ${classe}${alerta ? " alerta" : ""}`}
      onClick={() => onAbrir(chave)}
    >
      <span className="no-topo">
        <span className={`ponto ${cor || "muted"}`} />
        <span className="no-tipo">{tipo}</span>
      </span>
      <span className="no-corpo">
        <span className="no-titulo">{titulo}</span>
        {numero !== undefined && <span className={`no-n${numero ? "" : " zero"}`}>{numero}</span>}
      </span>
      <span className="no-estado">{estado}</span>
      {pe && <span className="no-pe">{pe}</span>}
    </button>
  );
}
