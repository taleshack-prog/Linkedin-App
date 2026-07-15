import { useEffect, useState } from "react";
import { api } from "../api.js";

const FEATURES = [
  ["Geração de texto ilimitada", () => true],
  ["Agendamento e publicação", () => true],
  ["Upload de imagens", () => true],
  ["Perfil de marca", (p) => p.brand_profile],
  ["Imagem por IA", (p) => p.ai_images],
  ["Material de referência (docs)", (p) => p.doc_upload],
  ["Formatação de texto (negrito/itálico)", (p) => p.text_formatting],
  ["Contas LinkedIn", (p) => p.linkedin_accounts],
];

export default function Billing() {
  const [plans, setPlans] = useState(null);
  const [status, setStatus] = useState(null);
  const [tiers, setTiers] = useState([]);
  const [guaranteeDays, setGuaranteeDays] = useState(7);
  const [bonusDays, setBonusDays] = useState(15);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.billingPlans().then((d) => { setPlans(d.plans); setTiers(d.referral_tiers); setGuaranteeDays(d.guarantee_days); setBonusDays(d.referred_bonus_days); }).catch((e) => setError(e.message));
    api.billingStatus().then(setStatus).catch(() => {});
  }, []);

  async function subscribe(plan) {
    setBusy(plan); setError("");
    try {
      const { url } = await api.checkout(plan);
      window.location.href = url;
    } catch (e) { setError(e.message); setBusy(""); }
  }
  async function manage() {
    setBusy("portal"); setError("");
    try {
      const { url } = await api.billingPortal();
      window.location.href = url;
    } catch (e) { setError(e.message); setBusy(""); }
  }

  const refLink = status?.referral_code
    ? `${window.location.origin}/?ref=${status.referral_code}`
    : null;
  const isPaid = status && status.plan !== "free";

  return (
    <>
      <header>
        <h2>Planos e indicação</h2>
        <p>
          Assine para publicar sem limites — com garantia de {guaranteeDays} dias:
          não gostou, devolvemos seu dinheiro. Indique e ganhe meses grátis.
        </p>
      </header>
      {error && <div className="notice err">{error}</div>}

      {status && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="meta">
            <span className={`chip ${isPaid ? "published" : "cancelled"}`}>Plano {status.plan_name}</span>
            {status.plan_until && (
              <span className="mono">válido até {new Date(status.plan_until).toLocaleDateString("pt-BR")}</span>
            )}
          </div>
          {isPaid && (
            <button className="btn" onClick={manage} disabled={busy === "portal"}>
              {busy === "portal" ? "Abrindo…" : "Gerenciar assinatura"}
            </button>
          )}
        </div>
      )}

      <div className="plans-grid">
        {plans?.map((p) => (
          <div key={p.key} className={`plan-card ${p.key === "pro" ? "featured" : ""}`}>
            {p.key === "pro" && <span className="plan-badge">Mais popular</span>}
            <h3>{p.name}</h3>
            <div className="plan-price">R$ {(p.price_cents / 100).toFixed(2).replace(".", ",")}<span>/mês</span></div>
            <ul className="plan-features">
              {FEATURES.map(([label, fn]) => {
                const v = fn(p);
                return (
                  <li key={label} className={v ? "on" : "off"}>
                    {label === "Contas LinkedIn" ? `${v} conta${v > 1 ? "s" : ""} LinkedIn` : label}
                  </li>
                );
              })}
            </ul>
            <button className="btn primary" style={{ width: "100%" }} onClick={() => subscribe(p.key)}
              disabled={busy === p.key || (isPaid && status.plan === p.key)}>
              {isPaid && status.plan === p.key ? "Plano atual" : busy === p.key ? "Redirecionando…" : "Assinar agora"}
            </button>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 22 }}>
        <h3 style={{ fontSize: 18, marginBottom: 6 }}>Indique e ganhe</h3>
        {isPaid ? (
          <>
            <p style={{ marginTop: 0, color: "var(--ink-soft)" }}>
              Compartilhe seu link: quem assinar por ele <strong>ganha {bonusDays} dias extras</strong> —
              e a cada amigo assinante, você sobe na escada:
            </p>
            <div className="ref-ladder">
              {tiers.map((t) => (
                <div key={t.referrals} className={`ref-step ${status.active_referrals >= t.referrals ? "reached" : ""}`}>
                  <div className="ref-n">{t.referrals}</div>
                  <div className="ref-m">{t.months} {t.months === 1 ? "mês" : "meses"} grátis</div>
                </div>
              ))}
            </div>
            <p className="mono" style={{ marginTop: 12 }}>
              Você tem <strong>{status.active_referrals}</strong> indicados assinantes · {status.months_earned} {status.months_earned === 1 ? "mês creditado" : "meses creditados"}
            </p>
            <div className="ai-form">
              <input readOnly value={refLink} onFocus={(e) => e.target.select()} />
              <button className="btn primary" onClick={() => { navigator.clipboard.writeText(refLink); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
                {copied ? "Copiado!" : "Copiar link"}
              </button>
            </div>
          </>
        ) : (
          <p style={{ marginTop: 0, color: "var(--ink-soft)" }}>
            O programa de indicação fica disponível para assinantes. Assine um plano acima para receber seu link e começar a ganhar meses grátis.
          </p>
        )}
      </div>
    </>
  );
}
