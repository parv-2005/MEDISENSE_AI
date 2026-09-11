"use client";

import type { Analysis } from "@/lib/api";
import { findingColor } from "./ui";
import { AlertCircle, CheckCircle2, HeartPulse, Info, WatermarkIcon, ShieldAlert } from "./Icons";

const URGENCY: Record<Analysis["analysis"]["urgency"], { label: string; tone: string; icon: React.ElementType; bannerBg: string }> = {
  routine: { label: "Routine follow-up", tone: "text-status-normal", icon: CheckCircle2, bannerBg: "bg-status-normal-bg border-status-normal/20" },
  soon: { label: "Discuss with a doctor soon", tone: "text-status-caution", icon: Info, bannerBg: "bg-status-caution-bg border-status-caution/20" },
  urgent: { label: "Seek care promptly", tone: "text-status-critical", icon: ShieldAlert, bannerBg: "bg-status-critical-bg border-status-critical/20" },
  unknown: { label: "Urgency not determined", tone: "text-muted-foreground", icon: Info, bannerBg: "bg-muted/50 border-muted/20" },
};

export function AnalysisView({ analysis }: { analysis: Analysis }) {
  const a = analysis.analysis;
  const abnormal = a.findings.filter((f) => f.status !== "normal" && f.status !== "unknown").length;
  const urgency = URGENCY[a.urgency] ?? URGENCY.unknown;
  const UrgencyIcon = urgency.icon;

  return (
    <div className="space-y-12">
      {/* --------------------------------------------------- triage urgency banner */}
      <section className={`border rounded-xl p-6 flex flex-col md:flex-row md:items-center gap-6 ${urgency.bannerBg}`}>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <UrgencyIcon className={`w-6 h-6 ${urgency.tone}`} />
            <h2 className="text-sm font-bold uppercase tracking-wider text-foreground">Triage Priority</h2>
          </div>
          <p className={`text-2xl font-bold tracking-tight ${urgency.tone}`}>{urgency.label}</p>
        </div>
        <div className="w-full md:w-px md:h-16 bg-border" aria-hidden="true" />
        <div className="flex-1">
          <p className="text-sm text-muted-foreground font-medium uppercase tracking-wider mb-2">Clinical Summary</p>
          <p className="text-lg font-medium text-foreground leading-snug">{a.summary}</p>
        </div>
      </section>

      {/* --------------------------------------------------- findings sheet */}
      {a.findings.length > 0 && (
        <section>
          <div className="flex items-end justify-between mb-5">
            <div>
              <h3 className="text-2xl font-bold tracking-tight text-foreground">Biomarker Analysis</h3>
              <p className="text-muted-foreground mt-1 text-base">Detailed breakdown of {a.findings.length} extracted values.</p>
            </div>
            {abnormal > 0 && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-status-abnormal-bg border border-status-abnormal/20 text-status-abnormal text-sm font-semibold">
                <AlertCircle className="w-4 h-4" />
                {abnormal} abnormal {abnormal === 1 ? "finding" : "findings"}
              </div>
            )}
          </div>
          
          <div className="border border-border rounded-xl bg-background overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[760px]">
                <thead>
                  <tr className="text-left bg-muted/30 border-b border-border">
                    <th className="py-4 pl-6 pr-4 font-semibold text-foreground">Parameter</th>
                    <th className="py-4 px-4 font-semibold text-foreground">Result</th>
                    <th className="py-4 px-4 font-semibold text-foreground">Reference</th>
                    <th className="py-4 px-4 font-semibold text-foreground">Status</th>
                    <th className="py-4 pr-6 pl-4 font-semibold text-foreground">Clinical Context</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {a.findings.map((f, i) => {
                    const c = findingColor(f.status);
                    return (
                      <tr key={`${f.parameter}-${i}`} className="hover:bg-muted/10 transition-colors align-top group">
                        <td className="pl-6 pr-4 py-4">
                          <span className="font-semibold text-foreground block">{f.parameter}</span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap font-medium text-foreground">{f.value || "—"}</td>
                        <td className="px-4 py-4 text-muted-foreground whitespace-nowrap">{f.reference_range || "—"}</td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider border ${c.badge}`}>
                            {c.word}
                          </span>
                        </td>
                        <td className="pr-6 pl-4 py-4 text-muted-foreground leading-relaxed max-w-[48ch]">
                          {f.explanation}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* --------------------------------------------------- insights / recommendations */}
      <section className="grid lg:grid-cols-2 gap-8">
        {a.insights.length > 0 && (
          <div className="bg-background border border-border rounded-xl p-8 relative overflow-hidden group hover:border-primary/30 transition-colors shadow-sm">
            <WatermarkIcon icon={HeartPulse} className="-right-6 -bottom-6 w-48 h-48" />
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-6">
                <HeartPulse className="w-5 h-5 text-primary" />
                <h3 className="text-xl font-bold tracking-tight text-foreground">Clinical Takeaways</h3>
              </div>
              <ul className="space-y-4">
                {a.insights.map((t, i) => (
                  <li key={i} className="flex gap-3 text-foreground leading-relaxed text-base">
                    <span className="mt-2 h-2 w-2 rounded-full bg-primary shrink-0" aria-hidden="true" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        
        {a.recommendations.length > 0 && (
          <div className="bg-background border border-border rounded-xl p-8 relative overflow-hidden group hover:border-status-normal/30 transition-colors shadow-sm">
            <WatermarkIcon icon={CheckCircle2} className="-right-6 -bottom-6 w-48 h-48" />
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-6">
                <CheckCircle2 className="w-5 h-5 text-status-normal" />
                <h3 className="text-xl font-bold tracking-tight text-foreground">Doctor Questions</h3>
              </div>
              <ul className="space-y-4">
                {a.recommendations.map((t, i) => (
                  <li key={i} className="flex gap-3 text-foreground leading-relaxed text-base">
                    <span className="mt-2 h-2 w-2 rounded-full bg-status-normal shrink-0" aria-hidden="true" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </section>

      <p className="text-sm font-medium text-muted-foreground border-t border-border pt-6 max-w-[80ch]">
        {a.disclaimer} Analysis powered by {analysis.model}.
      </p>
    </div>
  );
}
