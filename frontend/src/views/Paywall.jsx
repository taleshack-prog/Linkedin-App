import { useEffect, useState } from "react";
import { api, clearAuth } from "../api.js";

const brl = (cents) => (cents / 100).toFixed(2).replace(".", ",");

/** Tela obrigatória para quem não tem assinatura ativa.
 *  Não há plano gratuito: o núcleo do produto custa API por uso. */
export default function Paywall({ onAtivou }) {
  const [planos, setPlanos] = useState(null);
  const [ciclo, setCiclo] = useState("annual");
  const [busy, setBusy] = useState("");
  const [erro, setErro] = useState("");
  const [confirmando, setConfirmando] = useState(false);

  const params = new URLSearchParams(window.location.search);
  const voltouDoCheckout = params.get("billing") === "success";

  useEffect(() => {
    api.billingPlans().then(setPlanos).catch((e) => setErro(e.message));
  }, []);

  // Volta do Stripe: o webhook pode levar alguns segundos para provisionar.
  // Sem esta espera, o cliente que ACABOU de pagar veria o paywall de novo.
  useEffect(() => {
    if (!voltouDoCheckout) return;
    setConfirmando(true);
    let tentativas = 0;
    const t = setInterval(async () => {
      tentativas += 1;
      try {
        const st = await api.billingStatus();
        if (st && st.plan !== "free") {
          clearInterval(t);
          window.history.replaceState({}, "", "/");
          onAtivou();
          return;
        }
      } catch { /* segue tentando */ }
      if (tentativas >= 10) {          // ~20s
        clearInterval(t);
        setConfirmando(false);
        setErro(
          "Seu pagamento foi recebido, mas a liberação está demorando. " +
          "Atualize a página em instantes — se persistir, fale com o suporte."
        );
      }
    }, 2000);
    return () => clearInterval(t);
  }, [voltouDoCheckout]);

  async function assinar(plano) {
    setBusy(plano); setErro("");
    try {
      const { url } = await api.checkout(plano, ciclo);
      window.location.href = url;
    } catch (e) { setErro(e.message); setBusy(""); }
  }

  if (confirmando) {
    return (
      <div className="paywall">
        <div className="paywall-box confirmando">
          <h1>Confirmando seu pagamento…</h1>
          <p>Isso leva alguns segundos. Não feche a página.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="paywall">
      <div className="paywall-box">
        <header>
          <span className="lp-marca">Posthink</span>
          <button className="paywall-sair" onClick={() => { clearAuth(); window.location.href = "/"; }}>
            Sair
          </button>
        </header>

        <h1>Escolha seu plano para começar</h1>
        <p className="paywall-lede">
          Sua conta está criada. Falta escolher o plano — com{" "}
          <strong>garantia de 7 dias</strong>: não gostou, devolvemos o dinheiro.
        </p>
        {erro && <div className="notice err">{erro}</div>}

        <div className="cycle-toggle">
          <button className={ciclo === "monthly" ? "on" : ""} onClick={() => setCiclo("monthly")}>
            Mensal
          </button>
          <button className={ciclo === "annual" ? "on" : ""} onClick={() => setCiclo("annual")}>
            Anual <span className="cycle-badge">2 meses grátis</span>
          </button>
        </div>

        <div className="lp-planos">
          {planos?.plans?.map((p) => (
            <div key={p.key} className={`lp-plano ${p.key === "pro" ? "destaque" : ""}`}>
              {p.key === "pro" && <span className="lp-plano-tag">Mais escolhido</span>}
              <h3>{p.name}</h3>
              <div className="lp-preco">
                R$ {ciclo === "annual" ? brl(Math.round(p.price_cents_annual / 12)) : brl(p.price_cents)}
                <span>/mês</span>
              </div>
              <p className="lp-preco-sub">
                {ciclo === "annual"
                  ? `R$ ${brl(p.price_cents_annual)} por ano · economize R$ ${brl(p.annual_savings_cents)}`
                  : "cobrado mensalmente"}
              </p>
              <ul>
                <li>Posts ilimitados, com pesquisa</li>
                <li>Agendamento e publicação</li>
                <li>Upload de imagens</li>
                <li className={p.brand_profile ? "" : "nao"}>Perfil de marca</li>
                <li className={p.ai_images ? "" : "nao"}>Imagem por IA</li>
                <li className={p.doc_upload ? "" : "nao"}>Seus documentos como referência</li>
                <li className={p.text_formatting ? "" : "nao"}>Formatação de texto</li>
                <li>{p.linkedin_accounts} {p.linkedin_accounts > 1 ? "contas" : "conta"} do LinkedIn</li>
              </ul>
              <button
                className={`lp-btn ${p.key === "pro" ? "" : "ghost"} bloco`}
                onClick={() => assinar(p.key)}
                disabled={Boolean(busy)}
              >
                {busy === p.key ? "Abrindo pagamento…" : "Assinar"}
              </button>
            </div>
          ))}
          {!planos && <p className="lp-mono">carregando planos…</p>}
        </div>

        <p className="paywall-rodape">
          Pagamento seguro pela Stripe · Cancele quando quiser ·{" "}
          <a href="/privacidade" target="_blank" rel="noreferrer">Política de Privacidade</a>
        </p>
      </div>
    </div>
  );
}
