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

fs.rmSync(path.resolve("dist-ssr"), { recursive: true, force: true });
