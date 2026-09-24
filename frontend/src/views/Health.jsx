import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

const grid = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 12, marginBottom: 18 };
const tile = { padding: "14px 16px", textAlign: "center" };
const cap = { fontSize: 12, opacity: 0.7, marginTop: 4 };
const h3s = { fontSize: 15, margin: "18px 0 10px", opacity: 0.85 };

function fmtWhen(iso) {
  try { return new Date(iso).toLocaleString("pt-BR"); } catch { return iso; }
}

function Stat({ n, c, bad }) {
  return (
    <div className="card" style={tile}>
      <div style={{ fontSize: 26, fontWeight: 700, color: bad ? "#dc2626" : "inherit" }}>{n}</div>
      <div style={cap}>{c}</div>
    </div>
  );
}

export default function Health() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await api.healthAdmin());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  if (loading && !data) {
    return (<><header><h2>Saúde do sistema</h2></header><p className="mono">Carregando…</p></>);
  }

  return (
    <>
      <header>
        <h2>Saúde do sistema</h2>
        <p>Monitoramento de geração e publicação — atualiza sozinho a cada minuto.</p>
      </header>
      {error && <div className="notice err">{error}</div>}
      {data && (
        <>
          {data.alerts.length === 0 ? (
            <div className="notice" style={{ borderLeft: "4px solid #16a34a" }}>Tudo saudável — nenhum alerta agora.</div>
          ) : (
            data.alerts.map((a, i) => (
              <div key={i} className="notice err" style={{ borderLeft: `4px solid ${a.level === "high" ? "#dc2626" : "#d97706"}` }}>
                {a.level === "high" ? "🔴 " : "🟠 "}{a.msg}
              </div>
            ))
          )}

          <h3 style={h3s}>Sinais de alerta</h3>
          <div style={grid}>
            <Stat n={data.signals.stuck_publishing} c="Presos publicando" bad={data.signals.stuck_publishing > 0} />
            <Stat n={data.signals.overdue_scheduled} c="Agendados vencidos" bad={data.signals.overdue_scheduled > 0} />
            <Stat n={data.signals.gen_failed_24h} c="Gerações falhas 24h" bad={data.signals.gen_failed_24h > 0} />
            <Stat n={data.signals.publish_failed_24h} c="Publicações falhas 24h" bad={data.signals.publish_failed_24h > 0} />
            <Stat n={data.signals.anthropic_credit_alert ? "ALERTA" : "OK"} c="Saldo Anthropic" bad={data.signals.anthropic_credit_alert} />
          </div>

          <h3 style={h3s}>Volume</h3>
          <div style={grid}>
            <Stat n={data.volume.published_24h} c="Publicados 24h" />
            <Stat n={data.volume.published_7d} c="Publicados 7d" />
            <Stat n={data.volume.gen_ok_24h} c="Gerados 24h" />
            <Stat n={data.volume.gen_success_rate_pct == null ? "—" : data.volume.gen_success_rate_pct + "%"} c="Sucesso geração 24h" />
          </div>

          <h3 style={h3s}>Fila e serviços</h3>
          <div style={grid}>
            {Object.entries(data.queue).map(([k, n]) => <Stat key={k} n={n} c={k} />)}
            <Stat n={data.services.postgres ? "OK" : "OFF"} c="Postgres" bad={!data.services.postgres} />
            <Stat n={data.services.redis ? "OK" : "OFF"} c="Redis" bad={!data.services.redis} />
          </div>

          <h3 style={h3s}>Últimas falhas</h3>
          <div className="card">
            <strong>Publicação</strong>
            {data.recent_failures.publishing.length === 0
              ? <p className="mono" style={{ opacity: 0.6 }}>Nenhuma.</p>
              : <ul>{data.recent_failures.publishing.map((f, i) => (
                  <li key={i}><span className="mono">{fmtWhen(f.when)}</span> · {f.http_status} · {f.error}</li>
                ))}</ul>}
            <strong>Geração</strong>
            {data.recent_failures.generation.length === 0
              ? <p className="mono" style={{ opacity: 0.6 }}>Nenhuma.</p>
              : <ul>{data.recent_failures.generation.map((f, i) => (
                  <li key={i}><span className="mono">{fmtWhen(f.when)}</span> · {f.theme} · {f.error}</li>
                ))}</ul>}
          </div>
        </>
      )}
    </>
  );
}
