"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Analysis, type Report } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { AnalysisView } from "@/components/AnalysisView";
import { AskPanel } from "@/components/AskPanel";
import { PipelineRail, type RailState, type Stage } from "@/components/PipelineRail";
import { Button, Notice, Shell, Spinner, formatBytes, formatDate } from "@/components/ui";

type Tab = "analysis" | "text" | "ask";

export default function ReportPage() {
  const { user, loading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const id = params.id;

  const [report, setReport] = useState<Report | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("analysis");
  const [working, setWorking] = useState<Stage | null>(null);
  const [questionsAsked, setQuestionsAsked] = useState(0);
  const autoRan = useRef(false);

  const load = useCallback(async () => {
    try {
      const r = await api.getReport(id);
      setReport(r);
      if (r.has_analysis) {
        setAnalysis(await api.getAnalysis(id));
      } else {
        setAnalysis(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the report");
    }
  }, [id]);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  const runExtract = useCallback(async (): Promise<Report | null> => {
    setWorking("extract");
    setError(null);
    try {
      const r = await api.extract(id);
      setReport(r);
      setAnalysis(null);
      return r;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Extraction failed");
      await load();
      return null;
    } finally {
      setWorking(null);
    }
  }, [id, load]);

  const runAnalyze = useCallback(async () => {
    setWorking("analyze");
    setError(null);
    try {
      const a = await api.analyze(id);
      setAnalysis(a);
      setReport((r) => (r ? { ...r, status: "analyzed", has_analysis: true } : r));
      setTab("analysis");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed");
      await load();
    } finally {
      setWorking(null);
    }
  }, [id, load]);

  // Fresh upload from the dashboard: run the whole pipeline once.
  useEffect(() => {
    if (!report || autoRan.current || search.get("run") !== "1") return;
    autoRan.current = true;
    router.replace(`/reports/${id}`);
    (async () => {
      const extracted = report.extracted_text ? report : await runExtract();
      if (extracted?.extracted_text) await runAnalyze();
    })();
  }, [report, search, router, id, runExtract, runAnalyze]);

  if (loading || !user || (!report && !error)) {
    return (
      <div className="min-h-screen grid place-items-center text-muted"><Spinner /></div>
    );
  }

  const rail = buildRail(report, analysis, working, questionsAsked);
  const canAsk = Boolean(report?.extracted_text);

  return (
    <Shell>
      <nav className="text-sm font-medium text-muted-foreground mb-6 flex items-center gap-2">
        <Link href="/dashboard" className="hover:text-foreground transition-colors">Reports</Link>
        <span>/</span>
        <span className="text-foreground">{report?.original_filename ?? "Report"}</span>
      </nav>

      {report && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-6 mb-8">
            <div className="min-w-0">
              <h1 className="text-3xl font-bold tracking-tight text-foreground truncate">{report.original_filename}</h1>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm font-medium text-muted-foreground mt-2">
                <span>{formatBytes(report.size_bytes)}</span>
                {report.page_count && (
                  <>
                    <span>&middot;</span>
                    <span>{report.page_count} {report.page_count === 1 ? "page" : "pages"}</span>
                  </>
                )}
                {report.extraction_method && (
                  <>
                    <span>&middot;</span>
                    <span>{report.extraction_method === "ocr" ? "Read with OCR" : "Digital text layer"}</span>
                  </>
                )}
                <span>&middot;</span>
                <span>Uploaded {formatDate(report.created_at)}</span>
              </div>
            </div>
            <div className="flex gap-3">
              <Button variant="secondary" onClick={runExtract} busy={working === "extract"} disabled={working !== null}>
                {report.extracted_text ? "Re-extract text" : "Extract text"}
              </Button>
              <Button onClick={runAnalyze} busy={working === "analyze"} disabled={working !== null || !report.extracted_text}>
                {analysis ? "Re-run analysis" : "Analyze with AI"}
              </Button>
            </div>
          </div>

          <PipelineRail state={rail} />

          {error && <div className="mt-8"><Notice>{error}</Notice></div>}

          <div className="mt-10 border-b border-border flex items-center justify-between" role="tablist">
            <div className="flex gap-8">
              <TabButton active={tab === "analysis"} onClick={() => setTab("analysis")}>AI Analysis</TabButton>
              <TabButton active={tab === "text"} onClick={() => setTab("text")}>Extracted Text</TabButton>
            </div>
            <button
              onClick={() => setTab("ask")}
              className={`mb-3 px-5 py-2 rounded-lg text-sm font-bold transition-all shadow-sm ${
                tab === "ask" 
                  ? "bg-primary text-primary-foreground ring-2 ring-primary ring-offset-2 ring-offset-background" 
                  : "bg-primary text-primary-foreground hover:bg-primary/90 hover:-translate-y-0.5"
              }`}
            >
              Ask Questions
            </button>
          </div>

          <div className="mt-8">
            {tab === "analysis" && (
              analysis ? (
                <AnalysisView analysis={analysis} />
              ) : working === "analyze" ? (
                <div className="text-muted-foreground flex items-center gap-2"><Spinner /> AI is analyzing the clinical report</div>
              ) : (
                <EmptyState
                  title={report.extracted_text ? "No analysis yet" : "Extract the text first"}
                  body={report.extracted_text
                    ? "Run the AI analysis to get a plain-language explanation of every value."
                    : "The report needs its text extracted before it can be analysed."}
                />
              )
            )}
            {tab === "text" && (
              report.extracted_text ? (
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-4">
                    This is exactly what the {report.extraction_method === "ocr" ? "OCR engine" : "PDF text layer"} produced, after cleanup.
                    It is what the AI reads.
                  </p>
                  <pre className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed bg-background border border-border rounded-xl p-6 max-h-[70vh] overflow-auto shadow-sm">
                    {report.extracted_text}
                  </pre>
                </div>
              ) : working === "extract" ? (
                <div className="text-muted-foreground flex items-center gap-2"><Spinner /> Extracting text securely</div>
              ) : (
                <EmptyState title="No text extracted yet" body="Use Extract text to read the file." />
              )
            )}
            {tab === "ask" && <AskPanel reportId={id} enabled={canAsk} onAnswered={setQuestionsAsked} />}
          </div>
        </>
      )}
    </Shell>
  );
}

function buildRail(report: Report | null, analysis: Analysis | null, working: Stage | null, questionsAsked: number): RailState {
  const done: Stage[] = [];
  if (report) done.push("upload");
  if (report?.extracted_text) done.push("extract");
  if (analysis) done.push("analyze");
  if (questionsAsked > 0) done.push("ask");
  const failed: Stage | null =
    report?.status === "failed" ? "extract" : report?.error && !analysis && report.extracted_text ? "analyze" : null;
  const detail: RailState["detail"] = {};
  if (report?.extraction_method) {
    detail.extract = `${report.extraction_method === "ocr" ? "Tesseract OCR" : "PyMuPDF text layer"}, ${report.page_count ?? 1} page${(report.page_count ?? 1) === 1 ? "" : "s"}`;
  }
  if (analysis) detail.analyze = `${analysis.model}, ${analysis.analysis.findings.length} values explained`;
  if (questionsAsked > 0) detail.ask = `${questionsAsked} question${questionsAsked === 1 ? "" : "s"} answered from the report`;
  else if (report?.extracted_text) detail.ask = "Indexed in ChromaDB, ready for questions";
  return { done, active: working, failed, detail };
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`-mb-px pb-3 text-sm font-semibold tracking-wide border-b-2 transition-colors ${active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
    >
      {children}
    </button>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-dashed border-input bg-background rounded-xl p-12 text-center max-w-2xl mx-auto relative overflow-hidden">
      <div className="absolute inset-0 flex items-center justify-center opacity-[0.02] pointer-events-none">
        <svg width="200" height="200" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>
      </div>
      <p className="text-xl font-semibold text-foreground relative z-10">{title}</p>
      <p className="text-muted-foreground mt-2 text-base relative z-10">{body}</p>
    </div>
  );
}
