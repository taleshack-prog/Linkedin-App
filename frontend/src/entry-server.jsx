import { renderToStaticMarkup } from "react-dom/server";
import Landing from "./views/Landing.jsx";

// Renderiza a landing para HTML estático (SEO/IA leem sem precisar de JS).
export function render() {
  return renderToStaticMarkup(<Landing />);
}
