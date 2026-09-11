"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Answer } from "@/lib/api";
import { Button, Notice, Spinner } from "./ui";

const SUGGESTIONS = [
  "Which values are outside the normal range?",
  "What does this report say about my kidneys?",
  "Is anything here urgent?",
  "What should I ask my doctor about?",
];

export function AskPanel({ reportId, enabled, onAnswered }: { reportId: string; enabled: boolean; onAnswered?: (count: number) => void }) {
  const [history, setHistory] = useState<Answer[] | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openSources, setOpenSources] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    api.qaHistory(reportId)
      .then((h) => {
        if (cancelled) return;
        setHistory(h);
        onAnswered?.(h.length);
      })
      .catch(() => !cancelled && setHistory([]));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [history?.length, busy]);

  async function ask(q: string) {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    setQuestion("");
    try {
      const answer = await api.ask(reportId, text);
      setHistory((h) => {
        const next = [...(h ?? []), answer];
        onAnswered?.(next.length);
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not get an answer");
      setQuestion(text);
    } finally {
      setBusy(false);
    }
  }

  if (!enabled) {
    return (
      <Notice kind="info">Questions become available once the report text has been extracted.</Notice>
    );
  }

  return (
    <div className="grid lg:grid-cols-[minmax(0,1fr)_260px] gap-10 items-start">
      <div className="flex flex-col border border-border rounded-xl bg-muted/10 overflow-hidden shadow-sm h-[600px]">
        {/* Chat History Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {history === null && <div className="text-muted-foreground flex items-center justify-center h-full gap-2"><Spinner /> Loading chat history</div>}
          
          {history?.length === 0 && !busy && (
            <div className="flex flex-col items-center justify-center h-full text-center max-w-sm mx-auto">
              <div className="w-12 h-12 bg-primary/10 text-primary rounded-full flex items-center justify-center mb-4">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              </div>
              <p className="text-foreground font-semibold text-lg mb-2">Ask Medisense AI</p>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Ask about any value or phrase in the clinical report. Answers are synthesized only from the report text and cite the passages used for medical accuracy.
              </p>
            </div>
          )}

          {history?.map((a) => (
            <div key={a.id} className="space-y-6">
              {/* User Message Bubble */}
              <div className="flex justify-end">
                <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-5 py-3 max-w-[85%] shadow-sm">
                  <p className="font-medium text-[15px] leading-snug">{a.question}</p>
                </div>
              </div>

              {/* AI Response Bubble */}
              <div className="flex justify-start">
                <div className="bg-background border border-border rounded-2xl rounded-tl-sm px-6 py-5 max-w-[90%] shadow-sm">
                  <div className="text-foreground leading-relaxed prose-answer whitespace-pre-line text-[15px]">
                    {a.answer}
                  </div>
                  
                  {a.sources.length > 0 && (
                    <div className="mt-5 pt-4 border-t border-border">
                      <button
                        onClick={() => setOpenSources(openSources === a.id ? null : a.id)}
                        className="text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                        aria-expanded={openSources === a.id}
                      >
                        {openSources === a.id ? "Hide" : "Show"} {a.sources.length} clinical {a.sources.length === 1 ? "reference" : "references"}
                      </button>
                      {openSources === a.id && (
                        <ol className="mt-3 space-y-3">
                          {a.sources.map((s, i) => (
                            <li key={i} className="text-sm bg-muted/50 border border-border rounded-lg p-4 text-muted-foreground whitespace-pre-line font-mono text-[13px] leading-relaxed">
                              <span className="text-foreground font-semibold mr-2">[{i + 1}]</span>
                              {s.text}
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex justify-end">
              <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-5 py-3 max-w-[85%] shadow-sm opacity-70">
                <p className="font-medium text-[15px] leading-snug">{question}</p>
              </div>
            </div>
          )}
          {busy && (
            <div className="flex justify-start">
              <div className="bg-background border border-border rounded-2xl rounded-tl-sm px-5 py-4 max-w-[90%] shadow-sm flex items-center gap-3">
                <Spinner /> <span className="text-primary font-medium text-sm">Analyzing clinical records...</span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-background border-t border-border">
          {error && <div className="mb-4"><Notice>{error}</Notice></div>}
          <form
            onSubmit={(e) => { e.preventDefault(); ask(question); }}
            className="flex gap-3 relative"
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Message Medisense AI..."
              aria-label="Your question"
              className="flex-1 h-14 pl-5 pr-24 rounded-full border-2 border-input bg-background text-foreground placeholder:text-muted-foreground focus:border-primary focus:ring-0 transition-colors shadow-sm text-[15px]"
              maxLength={2000}
              disabled={busy}
            />
            <div className="absolute right-2 top-2 bottom-2">
              <Button type="submit" busy={busy} disabled={!question.trim()} className="h-full rounded-full px-6">Send</Button>
            </div>
          </form>
        </div>
      </div>

      <aside className="bg-muted/30 border border-border rounded-xl p-6 shadow-sm">
        <p className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-4">Suggested Queries</p>
        <ul className="space-y-3">
          {SUGGESTIONS.map((s) => (
            <li key={s}>
              <button
                onClick={() => ask(s)}
                disabled={busy}
                className="text-left text-[15px] font-medium text-primary hover:text-primary/80 transition-colors disabled:opacity-50 leading-snug"
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
