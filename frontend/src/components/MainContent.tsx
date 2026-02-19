"use client";

import { usePathname } from "next/navigation";

const FULL_BLEED_PAGES = ["/", "/investors", "/login", "/register", "/forgot-password", "/contact", "/about", "/privacy", "/terms", "/security", "/careers", "/proof", "/changelog", "/docs", "/sales-demo"];

export function MainContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isFullBleed =
    FULL_BLEED_PAGES.includes(pathname) || pathname.startsWith("/smart/");

  return (
    <main
      className={`flex-1 overflow-auto ${isFullBleed ? "" : "bg-muted/30"}`}
    >
      {children}
    </main>
  );
}
