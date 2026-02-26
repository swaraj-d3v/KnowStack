"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

type Citation = {
  document_id: string;
  document_name: string;
  page: number;
  section?: string | null;
  snippet: string;
};

type ChatResponse = {
  chat_id: string;
  answer: string;
  citations: Citation[];
};

type Message = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function callApi(path: string, init: RequestInit, userId: string) {
  const headers = new Headers(init.headers || {});
  headers.set("X-User-Id", userId);
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const text = await response.text();

  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }

  if (!response.ok) {
    throw new Error(typeof body === "object" ? JSON.stringify(body) : String(body));
  }
  return body;
}

export default function Page() {
  const [mounted, setMounted] = useState(false);
  const [userId, setUserId] = useState("swara");
  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState("Upload a document to begin.");
  const [readyDocumentId, setReadyDocumentId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const streamRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  const ready = useMemo(() => Boolean(readyDocumentId), [readyDocumentId]);

  async function uploadAndProcess(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setStatus("Uploading file...");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const upload = (await callApi(
        "/v1/documents/upload",
        { method: "POST", body: formData },
        userId,
      )) as { id: string; is_duplicate?: boolean };

      setStatus("Processing document...");
      await callApi(`/v1/documents/${upload.id}/process`, { method: "POST" }, userId);

      setReadyDocumentId(upload.id);
      setStatus(upload.is_duplicate ? "Document already existed and is ready." : "Document is ready. Ask anything.");
    } catch (err) {
      setStatus(`Error: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  async function askQuestion(value?: string) {
    const clean = (value ?? question).trim();
    if (!clean || !readyDocumentId || busy) return;

    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", text: clean }]);
    setQuestion("");
    setStatus("Thinking...");

    try {
      const response = (await callApi(
        "/v1/chat/ask",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: clean, document_id: readyDocumentId }),
        },
        userId,
      )) as ChatResponse;

      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: response.answer, citations: response.citations },
      ]);
      setStatus("Answer ready.");
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", text: `Error: ${String(err)}` }]);
      setStatus("Request failed.");
    } finally {
      setBusy(false);
    }
  }

  function onComposerKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void askQuestion();
    }
  }

  if (!mounted) {
    return (
      <main className="ks-root">
        <div className="ks-loading">Loading KnowStack...</div>
      </main>
    );
  }

  return (
    <main className="ks-root">
      <div className="ks-bg" aria-hidden="true" />

      <section className="ks-sidebar card-enter">
        <div>
          <h1>KnowStack</h1>
          <p className="muted">Upload your document, then chat naturally.</p>
        </div>

        <label className="field-label">User</label>
        <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="Your user id" />

        <form onSubmit={uploadAndProcess} className="upload-stack">
          <label className="field-label">Document</label>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <button disabled={!file || busy} type="submit" className="primary-btn">
            {busy ? "Working..." : "Upload and Prepare"}
          </button>
        </form>

        <div className={`status-pill ${ready ? "ok" : ""}`}>{status}</div>
        {ready && <div className="doc-chip">Document connected</div>}
      </section>

      <section className="ks-chat card-enter-delay">
        <header className="chat-topbar">
          <div>
            <h2>Document Assistant</h2>
            <p className="muted">Ask questions in plain language.</p>
          </div>
          <span className={`state-dot ${busy ? "busy" : "idle"}`}>{busy ? "Thinking" : "Ready"}</span>
        </header>

        <div className="chat-stream" ref={streamRef}>
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>Start with upload, then ask:</p>
              <div className="quick-row">
                <button className="ghost-chip" onClick={() => void askQuestion("Summarize this document in 5 points")} disabled={!ready || busy}>
                  Summarize in 5 points
                </button>
                <button className="ghost-chip" onClick={() => void askQuestion("What are the key topics?")} disabled={!ready || busy}>
                  Key topics
                </button>
                <button className="ghost-chip" onClick={() => void askQuestion("Explain this for a beginner")} disabled={!ready || busy}>
                  Beginner explanation
                </button>
              </div>
            </div>
          ) : (
            messages.map((m, idx) => (
              <article key={`${m.role}-${idx}`} className={`bubble ${m.role === "user" ? "you" : "ai"}`}>
                <div className="bubble-role">{m.role === "user" ? "You" : "KnowStack"}</div>
                <div className="bubble-text">{m.text}</div>

                {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                  <div className="cite-wrap">
                    {m.citations.map((c, ci) => (
                      <div className="cite-card" key={`${c.document_id}-${ci}`}>
                        <strong>{c.document_name} | Page {c.page}</strong>
                        <p>{c.snippet}</p>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            ))
          )}

          {busy && (
            <div className="typing">
              <span />
              <span />
              <span />
            </div>
          )}
        </div>

        <footer className="composer">
          <textarea
            placeholder={ready ? "Ask anything about your document..." : "Upload a document first..."}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onComposerKeyDown}
          />
          <button disabled={!ready || !question.trim() || busy} onClick={() => void askQuestion()} className="primary-btn">
            Send
          </button>
        </footer>
      </section>
    </main>
  );
}
