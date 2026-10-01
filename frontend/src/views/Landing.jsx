import { useEffect, useState } from "react";
import { api } from "../api.js";

const brl = (cents) => (cents / 100).toFixed(2).replace(".", ",");

// Rascunho de exemplo — o visitante exerce o papel de editor antes de ter conta.
const RASCUNHO = `Passei 3 anos achando que "não ter tempo" era o meu problema com o LinkedIn.

Não era. O problema era começar do zero toda vez.

A página em branco cobra um pedágio que ninguém contabiliza: você abre, encara, adia. E adia de novo. No fim do mês, zero posts — e a sensação de que todo mundo está construindo alguma coisa, menos você.

O que destravou não foi acordar mais cedo. Foi separar as duas coisas que eu estava tentando fazer ao mesmo tempo: pensar no assunto e escrever o texto.

Hoje eu só faço a primeira.`;

// Perguntas: respostas factuais do produto. Trocar pelas dúvidas reais dos clientes.
const PERGUNTAS = [
  {
    q: "A IA publica sozinha no meu perfil?",
    a: "Não. Ela gera rascunhos. Nenhum post vai ao ar sem você ler, aprovar e marcar o horário — é um passo obrigatório do fluxo, não uma configuração que dá para desligar.",
  },
  {
    q: "Isso põe minha conta do LinkedIn em risco?",
    a: "Não. A publicação passa pela API oficial do LinkedIn, autorizada por você via OAuth. Não usamos extensão de navegador, robô nem raspagem — que é o que costuma derrubar conta na plataforma.",
  },
  {
    q: "Como vocês auditam meu perfil, se o LinkedIn não dá esse acesso?",
    a: "Quem entrega os dados é você, não a plataforma. O LinkedIn deixa você exportar o PDF do próprio perfil e a planilha de análises, em dois cliques cada — é isso que você sobe aqui. Não há extensão, robô nem raspagem, e a gente não entra na sua conta para olhar nada. Endereço, telefone e e-mail são removidos do PDF antes de qualquer análise.",
  },
  {
    q: "O que conta como “post gerado por mês”?",
    a: "Cada rascunho criado pela IA. A cota renova todo dia 1º. Agendar, editar e publicar não têm limite — você pode reaproveitar e republicar o que já gerou à vontade.",
  },
  {
    q: "Posso cancelar quando quiser?",
    a: "Sim, pelo próprio painel, sem ligação nem e-mail de retenção. E há garantia de 7 dias: se não gostar, devolvemos o valor integral.",
  },
];

export default function Landing() {
  const [aprovado, setAprovado] = useState(false);
  const [planos, setPlanos] = useState(null);
  const [ciclo, setCiclo] = useState("annual");

  const params = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
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
      {/* ===== Cabeçalho: fio fino, marca em serifa, uma única ação em destaque ===== */}
      <header className="lp-topo">
        <div className="lp-topo-int">
          <a className="lp-marca" href="/">Posthink</a>
          <nav className="lp-menu">
            <a href="#como">Como funciona</a>
            <a href="#auditoria">Auditoria</a>
            <a href="#planos">Planos</a>
            <a href="#perguntas">Perguntas</a>
            {/* Link real (não âncora): é por aqui que o rastreador chega ao
                blog. Só pelo sitemap, os artigos ficam órfãos. */}
            <a href="/blog">Blog</a>
          </nav>
          <div className="lp-topo-acoes">
            <a className="lp-link-acao" href={entrar(false)}>Entrar</a>
            <a className="lp-btn" href={entrar(true)}>Criar conta</a>
          </div>
        </div>
      </header>

      {/* ===== Dateline: a linha de expediente da publicação ===== */}
      <div className="lp-expediente">
        <div className="lp-expediente-int">
          <span>Mesa editorial de LinkedIn</span>
          <span className="lp-sep" aria-hidden="true" />
          <span>Auditoria · Pesquisa · Redação · Agendamento</span>
          <span className="lp-sep" aria-hidden="true" />
          <span>API oficial do LinkedIn</span>
        </div>
      </div>

      {/* ===== Hero: a tese ===== */}
      <section className="lp-hero">
        <div className="lp-hero-int">
          <div className="lp-hero-texto">
            <p className="lp-slug">A tese</p>
            <h1>
              Primeiro entende<br />
              o seu perfil.<br />
              <em>Depois escreve.</em>
            </h1>
            <p className="lp-lede">
              A maioria das ferramentas escreve no escuro. O Posthink audita o seu perfil e o
              desempenho dos seus posts, descobre o que está travando a sua autoridade — e só
              então pesquisa, escreve no seu tom e publica pela API oficial do LinkedIn.{" "}
              <strong>Nada vai ao ar sem você aprovar.</strong>
            </p>
            <div className="lp-cta">
              <a className="lp-btn grande" href={entrar(true)}>Criar conta</a>
              <a className="lp-link-seta" href="#planos">Ver planos</a>
            </div>
            {ref && (
              <p className="lp-ref-aviso">
                Você chegou pelo convite de um assinante — ao assinar qualquer plano, ganha{" "}
                <strong>15 dias extras</strong>, por conta dele.
              </p>
            )}
            <ul className="lp-provas">
              <li>Auditoria de marca incluída</li>
              <li>Aprovação humana obrigatória</li>
              <li>Cancele quando quiser</li>
            </ul>
          </div>

          {/* ===== Assinatura: o visitante aprova um rascunho ===== */}
          <div className="lp-mesa">
            <figure className={`lp-card ${aprovado ? "no-ar" : ""}`}>
              <figcaption className="lp-card-topo">
                <span className={`lp-chip ${aprovado ? "pub" : "rasc"}`}>
                  {aprovado ? "Publicado" : "Rascunho"}
                </span>
                <span className="lp-mono">
                  {aprovado ? "urn:li:share:7218…" : "pauta: constância no LinkedIn"}
                </span>
              </figcaption>
              <p className="lp-post">{RASCUNHO}</p>
              <p className="lp-tags">#escrita #linkedin #constância</p>

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
            </figure>
          </div>
        </div>
      </section>

      {/* ===== Auditoria: o diferencial que nenhum gerador tem ===== */}
      <section className="lp-secao lp-fundo" id="auditoria">
        <div className="lp-secao-int">
          <header className="lp-cabeca">
            <p className="lp-slug">Auditoria de marca</p>
            <h2>Antes de escrever, descobrir o que está errado.</h2>
            <p className="lp-sub-secao">
              O LinkedIn não abre seu perfil nem suas métricas para aplicativos — nenhum deles,
              nem o nosso. Mas você baixa dois arquivos da sua própria conta, em dois cliques
              cada, e aqui eles viram diagnóstico.
            </p>
          </header>

          <div className="lp-aud">
            <article>
              <p className="lp-aud-n">Você envia</p>
              <h3>Dois arquivos que já são seus</h3>
              <p>
                O PDF do seu perfil e a planilha de análises, ambos exportados pelo próprio
                LinkedIn. Endereço, telefone e e-mail são removidos antes de qualquer análise.
              </p>
            </article>
            <article>
              <p className="lp-aud-n">Você recebe</p>
              <h3>Um diagnóstico com a prova junto</h3>
              <p>
                Nota do perfil, do conteúdo e da coerência entre os dois. Cada apontamento vem
                com o trecho ou o número que o sustenta — para você poder discordar item a item.
                Sem métrica, a nota fica em branco: nada é estimado.
              </p>
            </article>
            <article>
              <p className="lp-aud-n">E então</p>
              <h3>A escrita muda junto</h3>
              <p>
                O que a auditoria descobre passa a direcionar os próximos posts: o tom que
                funciona para você, o ângulo do seu posicionamento e os vícios a evitar. Ela
                também propõe pautas — cada uma nascida de um achado do seu diagnóstico.
              </p>
            </article>
          </div>

          <p className="lp-aud-nota">
            Disponível em todos os planos pagos. A frequência varia conforme o plano.
          </p>
        </div>
      </section>

      {/* ===== Faixa: separador editorial, usado uma única vez ===== */}
      <div className="lp-faixa" id="como">
        <span className="lp-faixa-lado">O percurso de um post</span>
        <h2>Quatro estágios. Você manda em dois.</h2>
        <a className="lp-faixa-lado dir" href="#planos">Ver planos →</a>
      </div>

      {/* ===== O percurso: sequência real, por isso numerada ===== */}
      <section className="lp-secao lp-secao-etapas">
        <ol className="lp-etapas">
          <li className="voce">
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
          <li className="voce">
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
        <div className="lp-secao-int">
          <header className="lp-cabeca">
            <p className="lp-slug">Por que não é mais um gerador de post</p>
            <h2>Quatro decisões que mudam o resultado.</h2>
          </header>
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
        </div>
      </section>

      {/* ===== Planos ===== */}
      <section className="lp-secao" id="planos">
        <div className="lp-secao-int">
          <header className="lp-cabeca centro">
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
          </header>

          <div className="lp-planos">
            {planos?.plans?.map((p) => (
              <div key={p.key} className={`lp-plano ${p.key === "pro" ? "destaque" : ""}`}>
                {p.key === "pro" && <span className="lp-plano-tag">Mais escolhido</span>}
                <h3>{p.name}</h3>
                <div className="lp-preco">
                  <span className="lp-preco-moeda">R$</span>
                  {ciclo === "annual" ? brl(Math.round(p.price_cents_annual / 12)) : brl(p.price_cents)}
                  <span className="lp-preco-mes">/mês</span>
                </div>
                <p className="lp-preco-sub">
                  {ciclo === "annual"
                    ? `R$ ${brl(p.price_cents_annual)} por ano · economize R$ ${brl(p.annual_savings_cents)}`
                    : "cobrado mensalmente"}
                </p>
                <ul>
                  <li>{p.max_posts < 0 ? "Geração ilimitada de posts" : `${p.max_posts} posts gerados por mês`}, com pesquisa</li>
                  <li>Agendamento e publicação automática</li>
                  <li>Upload de imagens</li>
                  <li className={p.brand_profile ? "" : "nao"}>Perfil de marca</li>
                  <li className={p.ai_images ? "" : "nao"}>Imagem por IA</li>
                  <li className={p.video ? "" : "nao"}>Upload de vídeo</li>
                  <li className={p.doc_upload ? "" : "nao"}>Seus documentos como referência</li>
                  <li className={p.max_audits ? "" : "nao"}>
                    {p.max_audits === 1
                      ? "Auditoria de marca, 1 por mês"
                      : p.max_audits > 1
                        ? `Auditoria de marca, ${p.max_audits} por mês`
                        : "Auditoria de marca"}
                  </li>
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
            {!planos && <p className="lp-mono lp-planos-carregando">carregando planos…</p>}
          </div>

          <p className="lp-nota-planos">
            &ldquo;posts gerados por mês&rdquo; = rascunhos criados pela IA (renova todo dia 1º).
            Agendar e publicar não têm limite.
          </p>
        </div>
      </section>

      {/* ===== Perguntas: objeções respondidas antes da decisão ===== */}
      <section className="lp-secao lp-fundo" id="perguntas">
        <div className="lp-secao-int">
          <header className="lp-cabeca">
            <p className="lp-slug">Perguntas</p>
            <h2>O que perguntam antes de assinar.</h2>
          </header>
          <dl className="lp-faq">
            {PERGUNTAS.map((item) => (
              <div className="lp-faq-item" key={item.q}>
                <dt>{item.q}</dt>
                <dd>{item.a}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* ===== Indicação: depois do preço, quando a conta está sendo feita ===== */}
      <section className="lp-secao" id="indique">
        <div className="lp-secao-int">
          <header className="lp-cabeca">
            <p className="lp-slug">Indique e ganhe</p>
            <h2>O Posthink pode se pagar sozinho.</h2>
            <p className="lp-sub-secao">
              Assinantes recebem um link pessoal. A cada amigo que assina por ele, você sobe na
              escada — e quem entra pelo seu convite ganha 15 dias extras de presente.
            </p>
          </header>
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
        </div>
      </section>

      <section className="lp-fechamento">
        <p className="lp-slug">Última linha</p>
        <h2>A página em branco não vai<br />se escrever sozinha.</h2>
        <p className="lp-fechamento-sub">Mas ela também não precisa mais ser sua.</p>
        <a className="lp-btn grande claro" href={entrar(true)}>Criar conta</a>
      </section>

      <footer className="lp-rodape">
        <div className="lp-rodape-int">
          <div className="lp-rodape-marca">
            <span className="lp-marca">Posthink</span>
            <p className="lp-mono">Hack Tech Farm · Porto Alegre, RS</p>
          </div>
          <nav>
            <a href="#como">Como funciona</a>
            <a href="#auditoria">Auditoria</a>
            <a href="#planos">Planos</a>
            <a href="#perguntas">Perguntas</a>
            <a href="/blog">Blog</a>
            <a href="/privacidade">Política de Privacidade</a>
            <a href={entrar(false)}>Entrar</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
