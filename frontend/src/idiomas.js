/* Idiomas em que o Posthink escreve.

   Um lugar só: a pauta e a auditoria precisam usar os mesmos códigos, porque
   são os mesmos que o backend aceita (Brief.language e IDIOMAS do auditor).
   Código fora desta lista o backend ignora e cai no padrão — então acrescentar
   idioma aqui sem acrescentar lá não tem efeito. */

export const IDIOMAS = [
  { codigo: "pt-BR", rotulo: "Português (Brasil)" },
  { codigo: "en-US", rotulo: "English (US)" },
];

export const IDIOMA_PADRAO = "pt-BR";
