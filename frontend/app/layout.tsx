import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
  weight: ["400", "500", "600", "700"],
});

const plex = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-plex",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "MediSense AI",
  description: "Upload a medical report, read it in plain language, and ask follow-up questions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${bricolage.variable} ${plex.variable}`}>
      <body className="min-h-screen antialiased bg-background text-foreground font-sans selection:bg-primary/20 selection:text-primary">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
