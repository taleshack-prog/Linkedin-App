import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

/* Auditoria de marca.

   Alimentada por upload porque a API oficial do LinkedIn não entrega nem
   perfil nem métrica nos escopos self-serve. Os dois arquivos saem da conta
   do próprio usuário, em dois cliques cada. */

const SEVERIDADE = { alta: "failed", media: "draft", baixa: "muted" };
const IMPACTO = { alto: "failed", medio: "draft", baixo: "muted" };

function Medidor({ rotulo, valor }) {
  const vazio = valor == null;
  return (
    <div className="aud-medidor">
      <span className="aud-medidor-n">{vazio ? "—" : valor}</span>
      <span className="aud-medidor-rot">{rotulo}</span>
      {!vazio && (
        <span className="aud-barra" aria-hidden="true">
          <span style={{ width: `${Math.max(0, Math.min(100, valor))}%` }} />
        </span>
      )}
      {vazio && <span className="aud-medidor-na">sem material</span>}
    </div>
  );
}

export default function Audit() {
  const [auditoria, setAuditoria] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [rodando, setRodando] = useState(false);
  const [erro, setErro] = useState("");
  const [perfilPdf, setPerfilPdf] = useState(null);
  const [analyticsXlsx, setAnalyticsXlsx] = useState(null);
  const [imagens, setImagens] = useState([]);
  const [postsTexto, setPostsTexto] = useState("");
  const [comoFazer, setComoFazer] = useState(false);
  const refPdf = useRef(null);
  const refXlsx = useRef(null);
  const refImgs = useRef(null);

  useEffect(() => {
    api.audit()
      .then((a) => setAuditoria(a))
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, []);

  async function rodar() {
    setRodando(true); setErro("");
    try {
      const nova = await api.runAudit({ perfilPdf, analyticsXlsx, postsTexto, imagens });
      setAuditoria(nova);
      setPerfilPdf(null); setAnalyticsXlsx(null); setImagens([]); setPostsTexto("");
      if (refPdf.current) refPdf.current.value = "";
      if (refXlsx.current) refXlsx.current.value = "";
      if (refImgs.current) refImgs.current.value = "";
    } catch (e) {
      setErro(e.message);
    } finally {
      setRodando(false);
    }
  }

  const temMaterial = Boolean(perfilPdf || analyticsXlsx || postsTexto.trim() || imagens.length);
  const r = auditoria?.resultado || {};
  const score = r.score || {};

  return (
    <>
      <header>
        <h2>Auditoria de marca</h2>
        <p>
          O LinkedIn não abre seu perfil nem suas métricas para aplicativos. Mas você baixa os
          dois arquivos da sua própria conta em dois cliques — e aqui eles viram diagnóstico.
        </p>
      </header>

      {erro && <div className="notice err">{erro}</div>}

      <section className="aud-envio">
        <div className="aud-campos">
          <label className="aud-arquivo">
            <span className="aud-arquivo-rot">PDF do seu perfil</span>
            <input ref={refPdf} type="file" accept=".pdf" id="aud-pdf"
                   onChange={(e) => setPerfilPdf(e.target.files?.[0] || null)} />
            <span className="mono">{perfilPdf ? perfilPdf.name : "headline, sobre, experiência"}</span>
          </label>

          <label className="aud-arquivo">
            <span className="aud-arquivo-rot">Planilha de análises</span>
            <input ref={refXlsx} type="file" accept=".xlsx" id="aud-xlsx"
                   onChange={(e) => setAnalyticsXlsx(e.target.files?.[0] || null)} />
            <span className="mono">{analyticsXlsx ? analyticsXlsx.name : "impressões, público, publicações"}</span>
          </label>

          <label className="aud-arquivo">
            <span className="aud-arquivo-rot">Capturas do perfil <em>(opcional)</em></span>
            <input ref={refImgs} type="file" accept="image/*" multiple id="aud-imgs"
                   onChange={(e) => setImagens(Array.from(e.target.files || []).slice(0, 4))} />
            <span className="mono">{imagens.length ? `${imagens.length} imagem(ns)` : "use \"Ver como\" → visitante"}</span>
          </label>
        </div>

        <details className="aud-como" open={comoFazer} onToggle={(e) => setComoFazer(e.target.open)}>
          <summary>Onde baixar esses arquivos</summary>
          <ol>
            <li><strong>PDF do perfil:</strong> abra seu perfil no LinkedIn → botão <em>Mais</em> → <em>Salvar em PDF</em>.</li>
            <li><strong>Planilha:</strong> no seu perfil, seção <em>Análises</em> → <em>Impressões da publicação</em> → <em>Exportar</em>. Períodos personalizados só existem no aplicativo do celular; no computador ficam os períodos pré-definidos.</li>
            <li><strong>Capturas:</strong> abra seu perfil, clique em <em>Ver como</em> e capture a tela de visitante. A sua tela de dono tem botões e painéis que ninguém mais enxerga — capturá-la faz a análise comentar coisas que o público não vê.</li>
          </ol>
          <p className="mono">
            Endereço, telefone e e-mail são removidos do PDF antes de qualquer análise.
          </p>
        </details>

        <div className="field">
          <label htmlFor="aud-posts">Posts anteriores <span className="mono">(opcional — separe por uma linha com ---)</span></label>
          <textarea id="aud-posts" value={postsTexto} rows={4}
                    placeholder={"Cole aqui o texto de posts que você quer que entrem na análise.\n---\nOutro post."}
                    onChange={(e) => setPostsTexto(e.target.value)} />
        </div>

        <div className="aud-acoes">
          <button className="btn primary" onClick={rodar} disabled={!temMaterial || rodando}>
            {rodando ? "Analisando…" : auditoria ? "Auditar de novo" : "Auditar minha marca"}
          </button>
          {rodando && <span className="mono">a análise leva alguns segundos</span>}
          {!temMaterial && !rodando && (
            <span className="mono">envie ao menos um arquivo para começar</span>
          )}
        </div>
      </section>

      {carregando && <p className="mono">carregando…</p>}

      {!carregando && !auditoria && (
        <div className="empty">
          Nenhuma auditoria ainda. Suba o PDF do seu perfil para receber o primeiro diagnóstico.
        </div>
      )}

      {auditoria && (
        <section className="aud-resultado">
          <div className="aud-scores">
            <Medidor rotulo="Geral" valor={score.total} />
            <Medidor rotulo="Perfil" valor={score.perfil} />
            <Medidor rotulo="Conteúdo" valor={score.conteudo} />
            <Medidor rotulo="Consistência" valor={score.consistencia} />
          </div>
          {score.base && <p className="aud-base">{score.base}</p>}

          {Array.isArray(r.acoes) && r.acoes.length > 0 && (
            <>
              <h3 className="aud-titulo">O que fazer</h3>
              <ol className="aud-lista-acoes">
                {r.acoes.map((a, i) => (
                  <li key={i}>
                    <div className="aud-acao-topo">
                      <span className="aud-acao-n">{String(i + 1).padStart(2, "0")}</span>
                      <h4>{a.titulo}</h4>
                      <span className={`chip ${IMPACTO[a.impacto] || "muted"}`}>impacto {a.impacto}</span>
                    </div>
                    <p className="aud-porque">{a.porque}</p>
                    <p className="aud-como-fazer">{a.como}</p>
                  </li>
                ))}
              </ol>
            </>
          )}

          {Array.isArray(r.achados) && r.achados.length > 0 && (
            <>
              <h3 className="aud-titulo">Diagnóstico</h3>
              <div className="aud-achados">
                {r.achados.map((a, i) => (
                  <article key={i} className={`aud-achado ${a.severidade}`}>
                    <div className="aud-achado-topo">
                      <span className={`chip ${SEVERIDADE[a.severidade] || "muted"}`}>{a.area}</span>
                      <span className="mono">severidade {a.severidade}</span>
                    </div>
                    <p>{a.diagnostico}</p>
                    {a.evidencia && (
                      <p className="aud-evidencia"><span>base:</span> {a.evidencia}</p>
                    )}
                  </article>
                ))}
              </div>
            </>
          )}

          {Array.isArray(r.nao_avaliado) && r.nao_avaliado.length > 0 && (
            <>
              <h3 className="aud-titulo">O que não deu para avaliar</h3>
              <ul className="aud-faltou">
                {r.nao_avaliado.map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </>
          )}

          {r.para_geracao && (
            <div className="aud-geracao">
              <h3 className="aud-titulo">Já aplicado às suas próximas pautas</h3>
              <p className="mono">
                Isto foi gravado no seu perfil de marca e passa a direcionar a escrita automática.
              </p>
              {r.para_geracao.tom && <p><strong>Tom:</strong> {r.para_geracao.tom}</p>}
              {r.para_geracao.angulo && <p><strong>Ângulo:</strong> {r.para_geracao.angulo}</p>}
              {Array.isArray(r.para_geracao.priorizar) && r.para_geracao.priorizar.length > 0 && (
                <p><strong>Priorizar:</strong> {r.para_geracao.priorizar.join(" · ")}</p>
              )}
              {Array.isArray(r.para_geracao.evitar) && r.para_geracao.evitar.length > 0 && (
                <p><strong>Evitar:</strong> {r.para_geracao.evitar.join(" · ")}</p>
              )}
            </div>
          )}

          <p className="mono aud-rodape">
            Auditoria de {new Date(auditoria.created_at).toLocaleString("pt-BR")} ·
            {" "}material usado: {(auditoria.fontes || []).join(", ") || "—"}
          </p>
        </section>
      )}
    </>
  );
}
