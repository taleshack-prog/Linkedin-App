// Formatação de texto para LinkedIn via Unicode.
//
// O feed do LinkedIn NÃO suporta rich text: não há negrito/itálico/cor reais.
// O que existe é trocar cada letra por um caractere Unicode que PARECE formatado
// (ex.: "a" -> 𝗮, Mathematical Sans-Serif Bold Small A).
//
// Custos reais (por isso os guarda-corpos abaixo):
// - Leitores de tela leem errado ou PULAM esses caracteres;
// - A busca do LinkedIn NÃO indexa texto assim (keyword formatada = invisível);
// - Cada caractere ocupa mais bytes no limite de 3.000.
//
// Usamos os blocos SANS-SERIF de propósito: os blocos serifados/script têm
// "buracos" no Unicode (ex.: itálico serifado não tem 'h') que quebrariam a conversão.

const A = 0x41, Z = 0x5a, a = 0x61, z = 0x7a, D0 = 0x30, D9 = 0x39;

const STYLES = {
  // 𝗻𝗲𝗴𝗿𝗶𝘁𝗼 — Mathematical Sans-Serif Bold
  bold: { upper: 0x1d5d4, lower: 0x1d5ee, digit: 0x1d7ec },
  // 𝘪𝘵á𝘭𝘪𝘤𝘰 — Mathematical Sans-Serif Italic (sem dígitos no bloco)
  italic: { upper: 0x1d608, lower: 0x1d622, digit: null },
  // 𝚖𝚘𝚗𝚘 — Mathematical Monospace
  mono: { upper: 0x1d670, lower: 0x1d68a, digit: 0x1d7f6 },
};

/** Aplica um estilo a um texto simples. Acentos e símbolos ficam intactos
 *  (não existem variantes Unicode para "ã", "ç" etc.). */
export function applyStyle(text, style) {
  const map = STYLES[style];
  if (!map) return text;
  return Array.from(text)
    .map((ch) => {
      const c = ch.codePointAt(0);
      if (c >= A && c <= Z) return String.fromCodePoint(map.upper + (c - A));
      if (c >= a && c <= z) return String.fromCodePoint(map.lower + (c - a));
      if (map.digit && c >= D0 && c <= D9) return String.fromCodePoint(map.digit + (c - D0));
      return ch;
    })
    .join("");
}

/** Converte texto estilizado de volta para letras normais (desfazer). */
export function stripStyles(text) {
  return Array.from(text)
    .map((ch) => {
      const c = ch.codePointAt(0);
      for (const map of Object.values(STYLES)) {
        if (c >= map.upper && c < map.upper + 26) return String.fromCharCode(A + (c - map.upper));
        if (c >= map.lower && c < map.lower + 26) return String.fromCharCode(a + (c - map.lower));
        if (map.digit && c >= map.digit && c < map.digit + 10)
          return String.fromCharCode(D0 + (c - map.digit));
      }
      return ch;
    })
    .join("");
}

export function isStyled(text) {
  return stripStyles(text) !== text;
}

/** Quantos caracteres do texto estão estilizados (para o alerta de excesso). */
export function styledRatio(text) {
  const chars = Array.from(text).filter((ch) => /\S/.test(ch));
  if (!chars.length) return 0;
  const styled = chars.filter((ch) => isStyled(ch)).length;
  return styled / chars.length;
}

export const MAX_STYLED_RATIO = 0.2;

/** Guarda-corpos: valida a seleção antes de formatar.
 *  Retorna { ok, error } ou { ok, warning }. */
export function checkSelection(selection, fullText, style) {
  if (!selection.trim()) {
    return { ok: false, error: "Selecione o trecho que deseja formatar." };
  }
  // 1) Hashtags precisam ser indexáveis — formatá-las as torna invisíveis na busca
  if (/#\S/.test(selection)) {
    return {
      ok: false,
      error: "Hashtags não podem ser formatadas — elas precisam continuar pesquisáveis no LinkedIn.",
    };
  }
  // 2) Acentos não têm variante Unicode — "ação" viraria "𝗮çã𝗼" (aparência remendada)
  if (/[à-üÀ-Üçñ]/i.test(selection)) {
    return {
      ok: true,
      warning:
        'Atenção: letras acentuadas não têm versão formatada no Unicode — "ação" fica "𝗮çã𝗼". Prefira formatar trechos sem acento.',
    };
  }
  // 3) Excesso de formatação prejudica leitura e acessibilidade
  const styledAfter = styledRatio(
    fullText.replace(selection, applyStyle(stripStyles(selection), style))
  );
  if (styledAfter > MAX_STYLED_RATIO) {
    return {
      ok: true,
      warning:
        "Mais de 20% do post ficaria formatado. Use ênfase em 1-2 trechos: leitores de tela ignoram texto assim e a busca do LinkedIn não o indexa.",
    };
  }
  return { ok: true };
}
