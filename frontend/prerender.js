import fs from "node:fs";
import path from "node:path";
import { render } from "./dist-ssr/entry-server.js";

const indexPath = path.resolve("dist/index.html");
let tpl = fs.readFileSync(indexPath, "utf-8");
if (!tpl.includes('<div id="root"></div>')) {
  console.error('prerender: <div id="root"></div> não encontrado');
  process.exit(1);
}
const html = render();
tpl = tpl.replace('<div id="root"></div>', `<div id="root">${html}</div>`);
fs.writeFileSync(indexPath, tpl);
console.log(`prerender: landing injetada no index.html (${html.length} chars)`);
fs.rmSync(path.resolve("dist-ssr"), { recursive: true, force: true });
