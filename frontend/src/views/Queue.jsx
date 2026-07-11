import { useEffect, useRef, useState } from "react";
import { api, STATUS_LABEL } from "../api.js";

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

function PostCard({ post, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [commentary, setCommentary] = useState(post.commentary);
  const [hashtags, setHashtags] = useState(post.hashtags.join(" "));
  const [publishAt, setPublishAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef(null);
  const [imgVersion, setImgVersion] = useState(0);

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
            <textarea id={`c-${post.id}`} value={commentary} onChange={(e) => setCommentary(e.target.value)} />
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
        </>
      )}
    </article>
  );
}

export default function Queue({ status, title, subtitle, refreshKey }) {
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
      {posts && posts.map((p) => <PostCard key={p.id} post={p} onChanged={load} />)}
    </>
  );
}
