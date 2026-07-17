import { useEffect, useState } from "react";
import { api } from "../api.js";

const brl = (cents) => (cents / 100).toFixed(2).replace(".", ",");

// Rascunho de exemplo — o visitante exerce o papel de editor antes de ter conta.
const RASCUNHO = `Passei 3 anos achando que "não ter tempo" era o meu problema com o LinkedIn.

Não era. O problema era começar do zero toda vez.

A página em branco cobra um pedágio que ninguém contabiliza: você abre, encara, adia. E adia de novo. No fim do mês, zero posts — e a sensação de que todo mundo está construindo alguma coisa, menos você.

O que destravou não foi acordar mais cedo. Foi separar as duas coisas que eu estava tentando fazer ao mesmo tempo: pensar no assunto e escrever o texto.

Hoje eu só faço a primeira.`;

export default function Landing() {
  const [aprovado, setAprovado] = useState(false);
  const [planos, setPlanos] = useState(null);
  const [ciclo, setCiclo] = useState("annual");

  const params = new URLSearchParams(window.location.search);
  const ref = params.get("ref");
  const entrar = (criar) => {
    const p = new URLSearchParams();
    if (criar) p.set("criar", "1");
    if (ref) p.set("ref", ref);
    const q = p.toString();
    return `/entrar${q ? "?" + q : ""}`;
  };

  useEffect(() => {
    api.billingPlans().then((d) => setPlanos(d)).catch(() => {});
  }, []);

  return (
    <div className="lp">
      <header className="lp-nav">
        <span className="lp-marca">Posthink</span>
        <nav>
          <a href="#como">Como funciona</a>
          <a href="#planos">Planos</a>
          <a href="#indique">Indique e ganhe</a>
          <a className="lp-btn ghost" href={entrar(false)}>Entrar</a>
          <a className="lp-btn" href={entrar(true)}>Criar conta</a>
        </nav>
      </header>

      {/* ===== Hero: a tese ===== */}
      <section className="lp-hero">
        <div className="lp-hero-texto">
          <p className="lp-slug">Mesa editorial · LinkedIn</p>
          <h1>
            A IA escreve.<br />
            Você continua<br />
            sendo o autor.
          </h1>
          <p className="lp-lede">
            O Posthink pesquisa o tema, escreve no seu tom e publica no horário que você
            marcar — pela API oficial do LinkedIn. <strong>Nada vai ao ar sem você aprovar.</strong>
          </p>
          <div className="lp-cta">
            <a className="lp-btn grande" href={entrar(true)}>Criar conta</a>
            <a className="lp-btn ghost grande" href="#planos">Ver planos</a>
          </div>
          {ref && (
            <p className="lp-ref-aviso">
              🎁 Você chegou pelo convite de um assinante — ao assinar qualquer plano, ganha{" "}
              <strong>15 dias extras</strong>, por conta dele.
            </p>
          )}
        </div>

        {/* ===== Assinatura: o visitante aprova um rascunho ===== */}
        <div className="lp-mesa">
          <div className={`lp-card ${aprovado ? "no-ar" : ""}`}>
            <div className="lp-card-topo">
              <span className={`lp-chip ${aprovado ? "pub" : "rasc"}`}>
                {aprovado ? "Publicado" : "Rascunho"}
              </span>
              <span className="lp-mono">
                {aprovado ? "urn:li:share:7218…" : "pauta: constância no LinkedIn"}
              </span>
            </div>
            <p className="lp-post">{RASCUNHO}</p>
            <div className="lp-tags">#escrita #linkedin #constância</div>

            {aprovado ? (
              <div className="lp-publicado">
                <span className="lp-carimbo">Aprovado por você</span>
                <p>
                  Foi assim: você leu, decidiu e o post foi. É esse o passo que o Posthink
                  nunca faz sozinho.
                </p>
                <button className="lp-desfazer" onClick={() => setAprovado(false)}>
                  Ver o rascunho de novo
                </button>
              </div>
            ) : (
              <div className="lp-acoes">
                <button className="lp-btn" onClick={() => setAprovado(true)}>
                  Aprovar e agendar
                </button>
                <span className="lp-mono dica">experimente — você é o editor</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ===== O percurso: é uma sequência real, por isso numerada ===== */}
      <section className="lp-secao" id="como">
        <p className="lp-slug">O percurso de um post</p>
        <h2>Quatro estágios. Você manda em dois.</h2>
        <ol className="lp-etapas">
          <li>
            <span className="lp-num">01</span>
            <h3>Pauta</h3>
            <p>
              Você diz o tema — “reforma tributária para pequenas empresas”. Pode anexar um
              PDF, um relatório, uma apresentação sua: os posts saem do <em>seu</em> material.
            </p>
            <span className="lp-quem voce">você</span>
          </li>
          <li>
            <span className="lp-num">02</span>
            <h3>Rascunho</h3>
            <p>
              A IA pesquisa o assunto na web, cruza com o seu perfil de marca e escreve os
              posts — com gancho, dados e um ângulo que serve ao seu objetivo.
            </p>
            <span className="lp-quem ia">IA</span>
          </li>
          <li>
            <span className="lp-num">03</span>
            <h3>Aprovação</h3>
            <p>
              Você lê, edita à vontade, troca a imagem, marca dia e hora. Ou joga fora. É o
              estágio que não tem atalho: sem o seu sim, o post morre aqui.
            </p>
            <span className="lp-quem voce">você</span>
          </li>
          <li>
            <span className="lp-num">04</span>
            <h3>Publicado</h3>
            <p>
              No horário marcado, o post vai ao ar pela API oficial do LinkedIn. Você recebe
              o link e o registro — mesmo dormindo.
            </p>
            <span className="lp-quem sist">automático</span>
          </li>
        </ol>
      </section>

      {/* ===== Diferenciais como afirmações, não cards de ícone ===== */}
      <section className="lp-secao lp-fundo">
        <p className="lp-slug">Por que não é mais um gerador de post</p>
        <div className="lp-teses">
          <article>
            <h3>Pesquisa antes de escrever</h3>
            <p>
              A IA busca na web o que aconteceu esta semana no seu tema. Post com dado de
              ontem, não com generalidade de sempre.
            </p>
          </article>
          <article>
            <h3>Seu perfil manda no ângulo</h3>
            <p>
              Você diz para quem escreve e o que quer construir. O tema define o assunto; o
              seu perfil define o ângulo, o tom e a chamada.
            </p>
          </article>
          <article>
            <h3>API oficial, conta protegida</h3>
            <p>
              Publicamos pelo canal oficial do LinkedIn, com sua autorização. Sem extensão,
              sem robô no navegador, sem raspagem — o que derruba conta por lá.
            </p>
          </article>
          <article>
            <h3>Seus documentos viram post</h3>
            <p>
              Suba um relatório ou uma apresentação e os posts nascem do seu conteúdo, com
              seus números — não do que a IA imagina sobre o assunto.
            </p>
          </article>
        </div>
      </section>

      {/* ===== Planos ===== */}
      <section className="lp-secao" id="planos">
        <p className="lp-slug">Planos</p>
        <h2>Escolha o ritmo. Cancele quando quiser.</h2>
        <p className="lp-sub-secao">
          Garantia de 7 dias: não gostou, devolvemos o dinheiro.
        </p>

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
                <li>Agendamento e publicação automática</li>
                <li>Upload de imagens</li>
                <li className={p.brand_profile ? "" : "nao"}>Perfil de marca</li>
                <li className={p.ai_images ? "" : "nao"}>Imagem por IA</li>
                <li className={p.doc_upload ? "" : "nao"}>Seus documentos como referência</li>
                <li className={p.text_formatting ? "" : "nao"}>Formatação de texto</li>
                <li>
                  {p.linkedin_accounts} {p.linkedin_accounts > 1 ? "contas" : "conta"} do LinkedIn
                </li>
              </ul>
              <a className={`lp-btn ${p.key === "pro" ? "" : "ghost"} bloco`} href={entrar(true)}>
                Começar
              </a>
            </div>
          ))}
          {!planos && <p className="lp-mono">carregando planos…</p>}
        </div>

      </section>

      {/* ===== Indicação: aqui é o lugar — depois do preço, quando a conta está sendo feita ===== */}
      <section className="lp-secao lp-fundo" id="indique">
        <p className="lp-slug">Indique e ganhe</p>
        <h2>O Posthink pode se pagar sozinho.</h2>
        <p className="lp-sub-secao">
          Assinantes recebem um link pessoal. A cada amigo que assina por ele, você sobe na
          escada — e quem entra pelo seu convite ganha 15 dias extras de presente.
        </p>
        <div className="lp-escada">
          <div className="lp-degrau">
            <span className="lp-degrau-n">3</span>
            <span className="lp-degrau-label">amigos assinantes</span>
            <strong>1 mês grátis</strong>
          </div>
          <div className="lp-degrau">
            <span className="lp-degrau-n">10</span>
            <span className="lp-degrau-label">amigos assinantes</span>
            <strong>6 meses grátis</strong>
          </div>
          <div className="lp-degrau alto">
            <span className="lp-degrau-n">16</span>
            <span className="lp-degrau-label">amigos assinantes</span>
            <strong>1 ano inteiro</strong>
          </div>
        </div>
        <p className="lp-escada-nota">
          Só conta amigo que vira assinante de verdade — nada de cadastro fantasma.
        </p>
      </section>

      <section className="lp-fechamento">
        <h2>A página em branco não vai se escrever sozinha.</h2>
        <p>Mas ela também não precisa mais ser sua.</p>
        <a className="lp-btn grande" href={entrar(true)}>Criar conta</a>
      </section>

      <footer className="lp-rodape">
        <span className="lp-marca">Posthink</span>
        <span className="lp-mono">Hack Tech Farm · Porto Alegre, RS</span>
        <nav>
          <a href="/privacidade">Política de Privacidade</a>
          <a href={entrar(false)}>Entrar</a>
        </nav>
      </footer>
    </div>
  );
}
