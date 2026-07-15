import { useEffect, useMemo, useState } from "react";
import { api, STATUS_LABEL } from "../api.js";

const DOW = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"];

function monthGrid(year, month) {
  const first = new Date(year, month, 1);
  const start = new Date(first);
  start.setDate(1 - ((first.getDay() + 6) % 7)); // semana começa na segunda
  const days = [];
  const d = new Date(start);
  for (let i = 0; i < 42; i++) {
    days.push(new Date(d));
    d.setDate(d.getDate() + 1);
  }
  return days;
}

export default function Calendar({ refreshKey }) {
  const today = new Date();
  const [cursor, setCursor] = useState({ y: today.getFullYear(), m: today.getMonth() });
  const [posts, setPosts] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.posts()
      .then((all) => setPosts(all.filter((p) => p.publish_at || p.published_at)))
      .catch((e) => setError(e.message));
  }, [refreshKey]);

  const byDay = useMemo(() => {
    const map = {};
    for (const p of posts) {
      const d = new Date(p.published_at || p.publish_at);
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
      (map[key] ||= []).push(p);
    }
    return map;
  }, [posts]);

  const days = monthGrid(cursor.y, cursor.m);
  const monthName = new Date(cursor.y, cursor.m).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
  const move = (delta) => {
    const d = new Date(cursor.y, cursor.m + delta);
    setCursor({ y: d.getFullYear(), m: d.getMonth() });
  };
  const goToday = () => setCursor({ y: today.getFullYear(), m: today.getMonth() });
  const isCurrentMonth = cursor.y === today.getFullYear() && cursor.m === today.getMonth();

  return (
    <>
      <header>
        <h2>Calendário editorial</h2>
        <p>Posts agendados e publicados, no fuso do seu navegador.</p>
      </header>
      {error && <div className="notice err">{error}</div>}
      <div className="cal-head">
        <button className="btn" onClick={() => move(-1)} aria-label="Mês anterior">←</button>
        <h3>{monthName}</h3>
        <button className="btn" onClick={() => move(1)} aria-label="Próximo mês">→</button>
        {!isCurrentMonth && (
          <button className="btn primary" onClick={goToday}>Hoje</button>
        )}
        <span className="spacer" />
        <span className="mono">{posts.length} {posts.length === 1 ? "post" : "posts"} no total</span>
      </div>
      <div className="cal-grid">
        {DOW.map((d) => (
          <div key={d} className="cal-dow">{d}</div>
        ))}
        {days.map((d) => {
          const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
          const out = d.getMonth() !== cursor.m;
          const isToday = d.toDateString() === today.toDateString();
          return (
            <div key={key} className={`cal-day ${out ? "out" : ""} ${isToday ? "today" : ""}`}>
              <div className="n">{d.getDate()}</div>
              {(byDay[key] || []).map((p) => {
                const time = new Date(p.published_at || p.publish_at).toLocaleTimeString("pt-BR", {
                  hour: "2-digit",
                  minute: "2-digit",
                });
                return (
                  <span
                    key={p.id}
                    className={`cal-post ${p.status}`}
                    title={`${STATUS_LABEL[p.status]} · ${p.commentary.slice(0, 160)}`}
                  >
                    {time} {p.commentary.split("\n")[0]}
                  </span>
                );
              })}
            </div>
          );
        })}
      </div>
    </>
  );
}
