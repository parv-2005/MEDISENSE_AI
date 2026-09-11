"use client";

import Link from "next/link";
import { Logomark } from "./ui";
import { ShieldCheck, WatermarkIcon } from "./Icons";

export function AuthCard({
  title,
  lede,
  children,
  footer,
}: {
  title: string;
  lede: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]">
      <aside className="hidden lg:flex flex-col justify-between bg-primary text-primary-foreground p-12 relative overflow-hidden">
        <WatermarkIcon icon={ShieldCheck} className="-left-10 -bottom-10 w-96 h-96 opacity-[0.05]" />
        
        <div className="flex items-center gap-3 relative z-10">
          <Logomark />
          <span className="text-xl font-semibold tracking-tight">MediSense AI</span>
        </div>
        
        <div className="max-w-md relative z-10">
          <h1 className="text-4xl leading-tight font-semibold">
            Your lab report, read back to you in plain language.
          </h1>
          <p className="mt-6 text-primary-foreground/80 leading-relaxed text-lg">
            Upload a PDF or a photo of a report. MediSense reads the text, flags what sits outside the reference
            range, and answers follow-up questions using only what the report says.
          </p>
          
          <ol className="mt-12 space-y-5 text-base text-primary-foreground/90 font-medium">
            <li className="flex gap-4 items-center">
              <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary-foreground/10 text-primary-foreground">1</span>
              Upload the report
            </li>
            <li className="flex gap-4 items-center">
              <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary-foreground/10 text-primary-foreground">2</span>
              Text is extracted securely
            </li>
            <li className="flex gap-4 items-center">
              <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary-foreground/10 text-primary-foreground">3</span>
              AI explains every value
            </li>
            <li className="flex gap-4 items-center">
              <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary-foreground/10 text-primary-foreground">4</span>
              Ask follow-up questions
            </li>
          </ol>
        </div>
        
        <p className="text-sm font-medium text-primary-foreground/60 relative z-10">
          For informational purposes only. Not a medical diagnosis.
        </p>
      </aside>
      
      <section className="flex items-center justify-center p-6 bg-background">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <Logomark />
            <span className="text-xl font-semibold tracking-tight text-foreground">MediSense AI</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">{title}</h2>
          <p className="text-muted-foreground mt-2 mb-8">{lede}</p>
          {children}
          <p className="text-sm font-medium text-muted-foreground mt-8 text-center">{footer}</p>
        </div>
      </section>
    </div>
  );
}

export { Link };
