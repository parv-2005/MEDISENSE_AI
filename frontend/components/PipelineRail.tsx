"use client";

/**
 * The flowchart, made live: Upload -> Extract -> Analyze -> Ask.
 * The fill advances as each stage finishes; the active stage pulses.
 */
export type Stage = "upload" | "extract" | "analyze" | "ask";

export interface RailState {
  done: Stage[];
  active: Stage | null;
  failed: Stage | null;
  detail?: Partial<Record<Stage, string>>;
}

const STAGES: { key: Stage; label: string; blurb: string }[] = [
  { key: "upload", label: "Upload", blurb: "File saved, metadata in MongoDB" },
  { key: "extract", label: "Extract text", blurb: "PyMuPDF for digital PDFs, Tesseract OCR for scans" },
  { key: "analyze", label: "AI analysis", blurb: "Gemini reads every value and explains it" },
  { key: "ask", label: "Ask", blurb: "Follow-up questions answered from the report" },
];

export function PipelineRail({ state }: { state: RailState }) {
  const doneCount = state.done.length;
  const activeIndex = state.active ? STAGES.findIndex((s) => s.key === state.active) : -1;
  // Fill to the midpoint of the active stage, or to the end of the last done stage.
  const progress = activeIndex >= 0 ? (activeIndex + 0.5) / STAGES.length : doneCount / STAGES.length;

  return (
    <div className="bg-background border border-border rounded-xl p-6 shadow-sm">
      <div className="relative h-2 rounded-full bg-muted overflow-hidden" aria-hidden="true">
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-in-out ${state.failed ? "bg-status-critical" : "bg-primary"}`}
          style={{ width: `${Math.min(100, progress * 100)}%` }}
        />
      </div>
      <ol className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
        {STAGES.map((s, i) => {
          const isDone = state.done.includes(s.key);
          const isActive = state.active === s.key;
          const isFailed = state.failed === s.key;
          const tone = isFailed ? "text-status-critical" : isDone ? "text-foreground" : isActive ? "text-primary" : "text-muted-foreground";
          return (
            <li key={s.key} className="min-w-0">
              <div className={`flex items-center gap-2.5 text-sm font-semibold tracking-tight ${tone}`}>
                <StageMark done={isDone} active={isActive} failed={isFailed} index={i + 1} />
                {s.label}
              </div>
              <p className="text-xs text-muted-foreground mt-1.5 leading-snug">{state.detail?.[s.key] ?? s.blurb}</p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StageMark({ done, active, failed, index }: { done: boolean; active: boolean; failed: boolean; index: number }) {
  const base = "inline-flex h-6 w-6 rounded-full items-center justify-center text-[11px] font-bold shrink-0 transition-colors";
  if (failed) return <span className={`${base} bg-status-critical text-status-critical-bg`} aria-label="failed">!</span>;
  if (done)
    return (
      <span className={`${base} bg-foreground text-background`} aria-label="done">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M2.5 6.5l2.3 2.3L9.5 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  if (active) return <span className={`${base} bg-primary text-primary-foreground animate-pulse shadow-sm shadow-primary/30`} aria-label="in progress">{index}</span>;
  return <span className={`${base} border-2 border-muted text-muted-foreground`}>{index}</span>;
}
