"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Report } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { Button, Notice, Shell, Spinner, STATUS_LABEL, StatusDot, formatBytes, formatDate, StatCard } from "@/components/ui";
import { FileText, Activity, UploadCloud, WatermarkIcon, CheckCircle2, AlertCircle } from "@/components/Icons";

const ACCEPT = "application/pdf,image/png,image/jpeg,image/webp,image/tiff,image/bmp";

export default function DashboardPage() {
  const { user, loading } = useRequireAuth();
  const router = useRouter();
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setReports(await api.listReports());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load reports");
    }
  }, []);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const report = await api.uploadReport(file);
      // Hand off to the report page, which drives extraction and analysis.
      router.push(`/reports/${report.id}?run=1`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
      setUploading(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) upload(file);
  }

  async function remove(report: Report) {
    if (!confirm(`Delete "${report.original_filename}"? This removes the file, its analysis and Q&A.`)) return;
    try {
      await api.deleteReport(report.id);
      setReports((r) => (r ? r.filter((x) => x.id !== report.id) : r));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  if (loading || !user) {
    return (
      <div className="min-h-screen grid place-items-center text-muted">
        <Spinner />
      </div>
    );
  }

  return (
    <Shell>
      <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-6 mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Clinical Dashboard</h1>
          <p className="text-muted-foreground mt-1 text-lg">Manage and analyze patient lab reports.</p>
        </div>
      </div>

      {error && <div className="mb-6"><Notice>{error}</Notice></div>}

      {/* Clinical Overview Stat Cards */}
      {reports !== null && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <StatCard 
            label="Total Reports" 
            value={reports.length} 
            icon={FileText} 
          />
          <StatCard 
            label="Successfully Analyzed" 
            value={reports.filter(r => r.status === "analyzed").length} 
            icon={CheckCircle2} 
          />
          <StatCard 
            label="Needs Attention" 
            value={reports.filter(r => r.status === "failed").length} 
            icon={AlertCircle} 
          />
        </div>
      )}

      <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] gap-10 items-start">
        {/* ------------------------------------------------ report list */}
        <section aria-label="Your reports">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold tracking-tight">Recent Reports</h2>
          </div>
          
          {reports === null ? (
            <div className="text-muted-foreground flex items-center gap-2 p-8 border border-border rounded-xl bg-background"><Spinner /> Loading reports</div>
          ) : reports.length === 0 ? (
            <div className="border border-dashed border-input bg-background rounded-xl p-12 text-center relative overflow-hidden">
              <WatermarkIcon icon={FileText} className="left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 opacity-[0.02] transform-none" />
              <p className="text-xl font-semibold text-foreground relative z-10">No reports yet</p>
              <p className="text-muted-foreground mt-2 text-base relative z-10">Add your first clinical report from the panel on the right.</p>
            </div>
          ) : (
            <ul className="space-y-4">
              {reports.map((r) => (
                <li key={r.id} className="bg-background border border-border rounded-xl p-5 flex flex-col sm:flex-row sm:items-center gap-4 hover:border-primary/50 transition-colors shadow-sm group">
                  <div className="flex-1 min-w-0 flex items-start gap-4">
                    <div className="mt-1.5"><StatusDot status={r.status} /></div>
                    <div className="min-w-0">
                      <Link href={`/reports/${r.id}`} className="text-lg font-semibold text-foreground hover:text-primary truncate block transition-colors">
                        {r.original_filename}
                      </Link>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm font-medium text-muted-foreground mt-1">
                        <span className="flex items-center gap-1.5">
                          <Activity className="w-3.5 h-3.5" />
                          {STATUS_LABEL[r.status]}
                        </span>
                        <span>&middot;</span>
                        <span>{formatDate(r.created_at)}</span>
                        <span>&middot;</span>
                        <span>{formatBytes(r.size_bytes)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 self-end sm:self-auto mt-4 sm:mt-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                    <Link href={`/reports/${r.id}`}>
                      <Button variant="secondary" className="h-9 px-4">Open</Button>
                    </Link>
                    <Button variant="danger" className="h-9 px-3 bg-destructive/10 text-destructive hover:bg-destructive hover:text-destructive-foreground border-0 shadow-none" onClick={() => remove(r)} aria-label={`Delete ${r.original_filename}`}>
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* ------------------------------------------------ upload panel */}
        <aside
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`rounded-xl border-2 p-8 transition-all relative overflow-hidden group ${dragging ? "border-primary bg-primary/5 scale-[1.02]" : "border-dashed border-input bg-background hover:border-primary/40"}`}
        >
          <WatermarkIcon icon={UploadCloud} className="-right-10 -bottom-10 w-64 h-64" />
          
          <div className="relative z-10 flex flex-col items-center text-center">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 transition-colors ${dragging ? "bg-primary text-primary-foreground" : "bg-primary/10 text-primary"}`}>
              <UploadCloud className="w-8 h-8" />
            </div>
            
            <h2 className="text-xl font-semibold text-foreground">Upload Report</h2>
            <p className="text-sm font-medium text-muted-foreground mt-2 leading-relaxed">
              PDF, PNG, JPEG, WebP or TIFF.<br />Up to 25 MB.
            </p>
            
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              className="sr-only"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) upload(f);
                e.target.value = "";
              }}
            />
            <Button className="w-full mt-6 h-11 text-base shadow-md" busy={uploading} onClick={() => inputRef.current?.click()}>
              {uploading ? "Uploading..." : "Select File"}
            </Button>
            <p className="text-sm font-medium text-muted-foreground mt-4">or drag and drop here</p>
          </div>
        </aside>
      </div>
    </Shell>
  );
}
