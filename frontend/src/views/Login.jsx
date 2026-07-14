import { useEffect, useRef, useState } from "react";
import { api, setApiKey, setToken } from "../api.js";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

export default function Login({ onLogin }) {
  const [mode, setMode] = useState("login"); // login | register | apikey
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [apiKey, setKeyField] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const googleBtn = useRef(null);
  const ref = new URLSearchParams(window.location.search).get("ref");

  // Botão oficial do Google (Identity Services) — só se configurado
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => {
      window.google?.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async ({ credential }) => {
          setError("");
          try {
            const { token } = await api.loginGoogle(credential, ref);
            setToken(token);
            onLogin();
          } catch (e) {
            setError(e.message);
          }
        },
      });
      if (googleBtn.current) {
        window.google?.accounts.id.renderButton(googleBtn.current, {
          theme: "outline", size: "large", width: 340, text: "continue_with", locale: "pt-BR",
        });
      }
    };
    document.body.appendChild(s);
    return () => s.remove();
  }, []);

  async function submit() {
    setLoading(true);
    setError("");
    try {
      if (mode === "apikey") {
        setApiKey(apiKey.trim());
        await api.me(); // valida a chave
      } else if (mode === "register") {
        const { token } = await api.register(email, password, name, ref);
        setToken(token);
      } else {
        const { token } = await api.login(email, password);
        setToken(token);
      }
      onLogin();
    } catch (e) {
      setError(e.message || "Falha na autenticação");
    } finally {
      setLoading(false);
    }
  }

  const canSubmit =
    mode === "apikey" ? apiKey.trim().length > 10 : email.includes("@") && password.length >= 8;

  return (
    <div className="login">
      <div className="box">
        <h1>LinkPost AI</h1>
        <p>
          {mode === "register"
            ? "Crie sua conta para abrir a mesa editorial."
            : "Entre para abrir a mesa editorial."}
        </p>
        {ref && mode === "register" && (
          <div className="notice">Você foi indicado(a) — ao assinar, você ganha 15 dias extras de presente.</div>
        )}
        {error && <div className="notice err">{error}</div>}

        {mode !== "apikey" ? (
          <>
            {mode === "register" && (
              <div className="field">
                <label htmlFor="name">Nome</label>
                <input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Seu nome" />
              </div>
            )}
            <div className="field">
              <label htmlFor="email">E-mail</label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()} placeholder="voce@exemplo.com" autoFocus />
            </div>
            <div className="field">
              <label htmlFor="password">Senha {mode === "register" && "(mínimo 8 caracteres)"}</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()} />
            </div>
            <button className="btn primary" style={{ width: "100%" }} onClick={submit} disabled={!canSubmit || loading}>
              {loading ? "Aguarde…" : mode === "register" ? "Criar conta" : "Entrar"}
            </button>
            {GOOGLE_CLIENT_ID && (
              <div ref={googleBtn} style={{ marginTop: 12, display: "flex", justifyContent: "center" }} />
            )}
            <p className="login-alt">
              {mode === "register" ? (
                <>Já tem conta? <button onClick={() => setMode("login")}>Entrar</button></>
              ) : (
                <>Novo por aqui? <button onClick={() => setMode("register")}>Criar conta</button></>
              )}
              {" · "}
              <button onClick={() => setMode("apikey")}>Tenho uma API key</button>
            </p>
          </>
        ) : (
          <>
            <div className="field">
              <label htmlFor="apikey">API key (acesso legado)</label>
              <input id="apikey" type="password" value={apiKey} onChange={(e) => setKeyField(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()} autoFocus />
            </div>
            <button className="btn primary" style={{ width: "100%" }} onClick={submit} disabled={!canSubmit || loading}>
              {loading ? "Validando…" : "Entrar com API key"}
            </button>
            <p className="login-alt">
              <button onClick={() => setMode("login")}>Voltar para e-mail e senha</button>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
