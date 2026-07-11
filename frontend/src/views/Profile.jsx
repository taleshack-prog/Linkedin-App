import { useEffect, useState } from "react";
import { api } from "../api.js";

const EMPTY = {
  entity_type: "", role: "", company: "", industry: "",
  audience: "", goal: "", tone: "", pillars: "", positioning: "",
};

export default function Profile() {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const isPJ = form.entity_type === "empresa";

  useEffect(() => {
    api.getProfile()
      .then((p) => setForm({ ...EMPTY, ...Object.fromEntries(
        Object.entries(p).filter(([k, v]) => k in EMPTY && v != null)
      )}))
      .catch((e) => setError(e.message));
  }, []);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  async function save() {
    setBusy(true); setNotice(""); setError("");
    try {
      await api.saveProfile(form);
      setNotice("Perfil salvo. As próximas pautas já serão geradas com esse contexto.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header>
        <h2>Perfil de marca</h2>
        <p>
          Quem você é, para quem escreve e o que quer construir. A IA usa este contexto
          em toda geração — posts alinhados a um objetivo, não posts soltos.
        </p>
      </header>
      {notice && <div className="notice">{notice}</div>}
      {error && <div className="notice err">{error}</div>}

      <div className="card">
        <div className="row">
          <div className="field">
            <label htmlFor="pf-type">Você atua como</label>
            <select id="pf-type" value={form.entity_type} onChange={set("entity_type")}>
              <option value="">— selecione —</option>
              <option value="autonomo">Autônomo(a) / freelancer</option>
              <option value="colaborador">Profissional em uma empresa</option>
              <option value="empresa">Empresa (PJ)</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="pf-goal">Objetivo principal no LinkedIn</label>
            <select id="pf-goal" value={form.goal} onChange={set("goal")}>
              <option value="">— selecione —</option>
              <option value="autoridade">Construir autoridade no tema</option>
              <option value="leads">Gerar leads / clientes</option>
              <option value="networking">Expandir networking</option>
              <option value="recrutamento">Atrair oportunidades / talentos</option>
              <option value="marca_empregadora">Marca empregadora</option>
            </select>
          </div>
        </div>
        <div className="row">
          <div className="field">
            <label htmlFor="pf-role">{isPJ ? "O que a empresa faz" : "Profissão / cargo"}</label>
            <input id="pf-role" value={form.role} onChange={set("role")}
              placeholder={isPJ ? "ex.: desenvolvimento de software sob demanda" : "ex.: engenheiro de software"} />
          </div>
          <div className="field">
            <label htmlFor="pf-company">{isPJ ? "Nome da empresa" : "Empresa onde trabalha (se houver)"}</label>
            <input id="pf-company" value={form.company} onChange={set("company")}
              placeholder="ex.: Hack Tech Farm" />
          </div>
        </div>
        <div className="row">
          <div className="field">
            <label htmlFor="pf-industry">Ramo / segmento</label>
            <input id="pf-industry" value={form.industry} onChange={set("industry")}
              placeholder="ex.: tecnologia, SaaS B2B" />
          </div>
          <div className="field">
            <label htmlFor="pf-audience">Público-alvo dos posts</label>
            <input id="pf-audience" value={form.audience} onChange={set("audience")}
              placeholder="ex.: fundadores de startups e gestores de marketing" />
          </div>
        </div>
        <div className="field">
          <label htmlFor="pf-tone">Tom de voz</label>
          <input id="pf-tone" value={form.tone} onChange={set("tone")}
            placeholder="ex.: direto, técnico mas acessível, com opinião" />
        </div>
        <div className="field">
          <label htmlFor="pf-pillars">Pilares de conteúdo (temas que você quer dominar)</label>
          <input id="pf-pillars" value={form.pillars} onChange={set("pillars")}
            placeholder="ex.: IA aplicada a negócios; automação; carreira em tech" />
        </div>
        <div className="field">
          <label htmlFor="pf-positioning">Posicionamento e visão de longo prazo</label>
          <textarea id="pf-positioning" style={{ minHeight: 90 }} value={form.positioning}
            onChange={set("positioning")}
            placeholder="Seus diferenciais, o que quer ser referência daqui a anos, causas que defende — o jogo infinito da sua marca." />
        </div>
        <button className="btn primary" onClick={save} disabled={busy}>
          {busy ? "Salvando…" : "Salvar perfil"}
        </button>
      </div>
    </>
  );
}
