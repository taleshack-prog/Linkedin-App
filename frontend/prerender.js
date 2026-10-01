import fs from "node:fs";
import path from "node:path";
import { render } from "./dist-ssr/entry-server.js";

const indexPath = path.resolve("dist/index.html");
const tplOriginal = fs.readFileSync(indexPath, "utf-8");
if (!tplOriginal.includes('<div id="root"></div>')) {
  console.error('prerender: <div id="root"></div> não encontrado');
  process.exit(1);
}

// 1. A landing entra pré-renderizada no index.html (SEO/IA leem sem JS).
const html = render();
fs.writeFileSync(
  indexPath,
  tplOriginal.replace('<div id="root"></div>', `<div id="root">${html}</div>`)
);
console.log(`prerender: landing injetada no index.html (${html.length} chars)`);

// 2. As rotas da SPA saem como arquivos reais (dist/<rota>/index.html).
//    Sem isso elas dependem do rewrite do vercel.json — e se a Vercel não
//    lê esse arquivo (Root Directory vazio, projeto migrado de time), a rota
//    devolve 404. Como diretório com index.html, servem em qualquer config.
//    Vão com o #root VAZIO: quem abre /entrar não deve ver o HTML da landing
//    piscando antes do React montar o Login.
const ROTAS = ["entrar", "privacidade"];
for (const rota of ROTAS) {
  const dir = path.resolve("dist", rota);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "index.html"), tplOriginal);
}
console.log(`prerender: rotas como arquivo real -> ${ROTAS.join(", ")}`);

// 3. Conserta as descrições faltantes na listagem do blog.
//    O gerador de conteúdo escreve <p></p> em parte dos artigos, mesmo tendo
//    gravado a meta description no próprio artigo. Resultado: a listagem
//    perde o resumo e o rastreador vê um parágrafo vazio. Como ele regenera
//    o blog/index.html, consertar o arquivo à mão não sobrevive — então o
//    reparo roda aqui, no build, depois dele. É idempotente: só preenche o
//    que está vazio, lendo a descrição do próprio artigo de destino.
const listaBlog = path.resolve("dist/blog/index.html");
if (fs.existsSync(listaBlog)) {
  let lista = fs.readFileSync(listaBlog, "utf-8");
  let preenchidas = 0;

  lista = lista.replace(
    /(<h2><a href="\/blog\/([^"]+)">.*?<\/a><\/h2>\s*<p>)(\s*)(<\/p>)/gs,
    (inteiro, abre, slug, _vazio, fecha) => {
      const artigo = path.resolve("dist/blog", `${slug}.html`);
      if (!fs.existsSync(artigo)) return inteiro;
      const fonte = fs.readFileSync(artigo, "utf-8");
      const m = fonte.match(/<meta name="description" content="([^"]+)"/);
      if (!m) return inteiro;
      preenchidas++;
      return `${abre}${m[1]}${fecha}`;
    }
  );

  if (preenchidas > 0) {
    fs.writeFileSync(listaBlog, lista);
    console.log(`prerender: descrições do blog preenchidas -> ${preenchidas}`);
  }
}

fs.rmSync(path.resolve("dist-ssr"), { recursive: true, force: true });
