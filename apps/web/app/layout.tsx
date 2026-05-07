import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Personal AI Research OS",
  description: "Uncertainty-aware reasoning continuity and synthesis",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="container">
          <header className="header">
            <div className="title">Personal AI Research OS</div>
            <div className="subtitle">Reasoning continuity · Uncertainty tracking · Synthesis support</div>
          </header>
          {children}
          <footer className="footer">
            <span>Local dev MVP · persists to Postgres via Prisma (DATABASE_URL)</span>
          </footer>
        </div>
      </body>
    </html>
  );
}

