import { useEffect, useRef, useState } from "react";
import { api, STATUS_LABEL } from "../api.js";
import { applyStyle, checkSelection, stripStyles } from "../format.js";

const MAX = 3000;

function fmtDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

// datetime-local (fuso do navegador) -> ISO UTC exigido pela API
function localToIso(v) {
  return new Date(v).toISOString();
}

function PostImage({ postId, version }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url;
    api.fetchPostImageBlob(postId)
      .then((blob) => { url = URL.createObjectURL(blob); setSrc(url); })
      .catch(() => setSrc(null));
    return () => url && URL.revokeObjectURL(url);
  }, [postId, version]);
  if (!src) return null;
  return <img className="post-image" src={src} alt="Imagem anexada ao post" />;
}

function FormatBar({ textareaRef, value, onChange, onNotice }) {
  function format(style) {
    const el = textareaRef.current;
    if (!el) return;
    const { selectionStart: s, selectionEnd: e } = el;
    const selection = value.slice(s, e);
    const check = checkSelection(selection, value, style);
    if (!check.ok) return onNotice(check.error, "err");
    if (check.warning) onNotice(check.warning, "warn");
    const plain = stripStyles(selection);
    // Clicar no mesmo estilo com o texto já formatado desfaz
    const next = plain === selection ? applyStyle(plain, style) : plain;
    const updated = value.slice(0, s) + next + value.slice(e);
    onChange(updated);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(s, s + next.length);
    });
  }
  return (
    <div className="fmt-bar">
      <button type="button" className="fmt-btn" onClick={() => format("bold")} title="Negrito (seleção)">
        <strong>B</strong>
      </button>
      <button type="button" className="fmt-btn" onClick={() => format("italic")} title="Itálico (seleção)">
        <em>I</em>
      </button>
      <button type="button" className="fmt-btn mono" onClick={() => format("mono")} title="Monoespaçado (seleção)">
        M
      </button>
      <span className="fmt-hint">
        selecione o trecho · o LinkedIn não tem negrito real: usamos Unicode, que leitores de tela e a busca ignoram
      </span>
    </div>
  );
}

function PostCard({ post, onChanged, canFormat }) {
  const [editing, setEditing] = useState(false);
  const [commentary, setCommentary] = useState(post.commentary);
  const [hashtags, setHashtags] = useState(post.hashtags.join(" "));
  const [publishAt, setPublishAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef(null);
  const commentaryRef = useRef(null);
  const [fmtNotice, setFmtNotice] = useState(null);
  const [imgVersion, setImgVersion] = useState(0);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiInstructions, setAiInstructions] = useState("");
  const [generating, setGenerating] = useState(false);

  const tagList = hashtags.split(/\s+/).filter(Boolean).map((h) => (h.startsWith("#") ? h : `#${h}`));
  const total = commentary.length + (tagList.length ? 2 + tagList.join(" ").length : 0);
  const editable = post.status === "draft" || post.status === "approved";

  async function run(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const saveEdit = () =>
    run(async () => {
      await api.editPost(post.id, {
        commentary,
        hashtags: tagList.map((h) => h.slice(1)),
      });
      setEditing(false);
    });

  const approve = () => run(() => api.approvePost(post.id, localToIso(publishAt)));
  const cancel = () => run(() => api.cancelPost(post.id));

  const uploadImage = (file) =>
    run(async () => {
      await api.uploadPostImage(post.id, file);
      setImgVersion((v) => v + 1);
    });
  const removeImage = () =>
    run(async () => {
      await api.deletePostImage(post.id);
      setImgVersion((v) => v + 1);
    });

  async function generateAiImage() {
    setGenerating(true);
    setError("");
    try {
      await api.generatePostImage(post.id, aiInstructions.trim() || null);
      setImgVersion((v) => v + 1);
      setAiOpen(false);
      setAiInstructions("");
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <article className={`card ${post.status}`}>
      <div className="meta">
        <span className={`chip ${post.status}`}>{STATUS_LABEL[post.status] || post.status}</span>
        {post.publish_at && post.status === "approved" && (
          <span className="mono">agendado p/ {fmtDate(post.publish_at)}</span>
        )}
        {post.published_at && <span className="mono">publicado em {fmtDate(post.published_at)}</span>}
        {post.linkedin_post_urn && <span className="mono">{post.linkedin_post_urn}</span>}
      </div>

      {post.last_error && <div className="error">{post.last_error}</div>}
      {error && <div className="error">{error}</div>}

      {editing ? (
        <>
          <div className="field">
            <label htmlFor={`c-${post.id}`}>Texto do post</label>
            {canFormat && (
              <FormatBar
                textareaRef={commentaryRef}
                value={commentary}
                onChange={setCommentary}
                onNotice={(msg, kind) => {
                  setFmtNotice({ msg, kind });
                  setTimeout(() => setFmtNotice(null), 6000);
                }}
              />
            )}
            {fmtNotice && (
              <div className={`notice ${fmtNotice.kind === "err" ? "err" : ""}`} style={{ marginBottom: 8 }}>
                {fmtNotice.msg}
              </div>
            )}
            <textarea
              id={`c-${post.id}`}
              ref={commentaryRef}
              value={commentary}
              onChange={(e) => setCommentary(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor={`h-${post.id}`}>Hashtags (separadas por espaço)</label>
            <input id={`h-${post.id}`} value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
          </div>
          <div className={`charcount ${total > MAX ? "over" : ""}`}>
            {total} / {MAX} caracteres (texto + hashtags)
          </div>
          <div className="actions">
            <button className="btn primary" onClick={saveEdit} disabled={busy || total > MAX || !commentary.trim()}>
              Salvar edição
            </button>
            <button className="btn" onClick={() => setEditing(false)} disabled={busy}>
              Descartar
            </button>
          </div>
        </>
      ) : (
        <>
          {post.has_image && <PostImage postId={post.id} version={imgVersion} />}
          <p className="commentary">{post.commentary}</p>
          {post.hashtags.length > 0 && (
            <div className="tags">{post.hashtags.map((h) => (h.startsWith("#") ? h : `#${h}`)).join(" ")}</div>
          )}
          <div className="actions">
            {editable && (
              <button className="btn" onClick={() => setEditing(true)} disabled={busy}>
                Editar
              </button>
            )}
            {editable && (
              <>
                <input
                  ref={fileInput}
                  type="file"
                  accept="image/jpeg,image/png,image/gif"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadImage(f);
                    e.target.value = "";
                  }}
                />
                <button className="btn" onClick={() => fileInput.current?.click()} disabled={busy}>
                  {post.has_image ? "Trocar imagem" : "Adicionar imagem"}
                </button>
                {post.has_image && (
                  <button className="btn danger" onClick={removeImage} disabled={busy}>
                    Remover imagem
                  </button>
                )}
                <button className="btn" onClick={() => setAiOpen((o) => !o)} disabled={busy || generating}>
                  {generating ? "Gerando imagem…" : "Gerar imagem (IA)"}
                </button>
              </>
            )}
            {post.status === "draft" && (
              <>
                <input
                  type="datetime-local"
                  aria-label="Data e hora de publicação"
                  style={{ width: "auto" }}
                  value={publishAt}
                  onChange={(e) => setPublishAt(e.target.value)}
                />
                <button className="btn primary" onClick={approve} disabled={busy || !publishAt}>
                  Aprovar e agendar
                </button>
              </>
            )}
            {editable && (
              <button className="btn danger" onClick={cancel} disabled={busy}>
                Cancelar post
              </button>
            )}
          </div>
          {aiOpen && (
            <div className="ai-form">
              <input
                value={aiInstructions}
                onChange={(e) => setAiInstructions(e.target.value)}
                placeholder="Instruções opcionais (ex.: tons de azul, estilo isométrico)"
                maxLength={500}
                onKeyDown={(e) => e.key === "Enter" && !generating && generateAiImage()}
              />
              <button className="btn primary" onClick={generateAiImage} disabled={generating}>
                {generating ? "Gerando…" : "Gerar"}
              </button>
            </div>
          )}
        </>
      )}
    </article>
  );
}

export default function Queue({ status, title, subtitle, refreshKey, canFormat }) {
  const [posts, setPosts] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      setPosts(await api.posts(status));
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    setPosts(null);
    load();
  }, [status, refreshKey]);

  return (
    <>
      <header>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </header>
      {error && <div className="notice err">{error}</div>}
      {posts === null && <div className="empty">Carregando…</div>}
      {posts && posts.length === 0 && (
        <div className="empty">
          Nada por aqui. {status === "draft" ? "Crie uma pauta para gerar rascunhos." : ""}
        </div>
      )}
      {posts && posts.map((p) => <PostCard key={p.id} post={p} onChanged={load} canFormat={canFormat} />)}
    </>
  );
}
