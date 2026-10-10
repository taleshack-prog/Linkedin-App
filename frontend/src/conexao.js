/* Estado da conexão com o LinkedIn.

   Existe porque a conexão MORRE sozinha: o LinkedIn não entrega refresh token
   fora do Marketing Developer Platform, então o token de acesso vence em ~60
   dias e só o dono do perfil reconecta. Sem aviso, a pessoa descobre pelo pior
   caminho — agendando posts que falham calados.

   Um lugar só para o critério, senão Mesa, Contas e a fila de aprovação
   divergem e o usuário vê três versões da mesma verdade. */

export const DIAS_AVISO = 10;

export function estadoConexao(conta) {
  if (!conta) return { chave: "ausente", dias: null };
  if (conta.status !== "active") return { chave: "morta", dias: null };
  const dias = Math.floor((new Date(conta.access_expires_at) - Date.now()) / 86400000);
  if (!Number.isFinite(dias)) return { chave: "ok", dias: null };
  if (dias < 0) return { chave: "morta", dias };
  if (dias <= DIAS_AVISO) return { chave: "expirando", dias };
  return { chave: "ok", dias };
}

/** A conta ainda estará viva na data marcada para publicar? */
export function viveAte(conta, quando) {
  if (!conta || !quando) return true;
  const fim = new Date(conta.access_expires_at);
  const alvo = new Date(quando);
  if (!Number.isFinite(fim.getTime()) || !Number.isFinite(alvo.getTime())) return true;
  return alvo <= fim;
}

/** Pior estado entre as contas — é o que a Mesa e a fila mostram no topo. */
export function piorEstado(accounts = []) {
  const ordem = { morta: 3, expirando: 2, ok: 1, ausente: 0 };
  let pior = { chave: "ausente", dias: null, conta: null };
  for (const c of accounts) {
    const e = estadoConexao(c);
    if (ordem[e.chave] > ordem[pior.chave]) pior = { ...e, conta: c };
  }
  return pior;
}
