"use client";

import Link from "next/link";
import { Brain, Shield, Lock, Server, Eye, FileCheck, AlertTriangle } from "lucide-react";

export default function SecurityPage() {
  const practices = [
    { icon: Lock, title: "Encryption", description: "AES-256 encryption at rest, TLS 1.3 in transit. All PHI is encrypted with customer-managed keys available on Enterprise plans." },
    { icon: Shield, title: "SOC 2 Type II (In Process)", description: "Currently pursuing SOC 2 Type II certification. Our controls are designed around security, availability, and confidentiality trust service criteria." },
    { icon: FileCheck, title: "HIPAA-Ready Architecture", description: "Platform designed with HIPAA safeguards from day one. Administrative, physical, and technical controls aligned with the HIPAA Security Rule. BAA available." },
    { icon: Server, title: "Infrastructure", description: "Hosted on SOC 2 and ISO 27001 certified cloud infrastructure. VPC isolation, private networking, and no shared tenancy for Enterprise." },
    { icon: Eye, title: "Access Controls", description: "Role-based access control (RBAC), SSO via SAML 2.0 and OIDC, multi-factor authentication, and comprehensive audit logging." },
    { icon: AlertTriangle, title: "Incident Response", description: "24/7 monitoring with automated alerting. Documented incident response plan with defined SLAs for notification and remediation." },
  ];

  return (
    <div className="min-h-screen bg-white">
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-white/80 border-b border-neutral-200/60">
        <div className="max-w-[1200px] mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-neutral-900 flex items-center justify-center"><Brain className="h-4 w-4 text-white" /></div>
            <span className="font-semibold text-[15px] tracking-[-0.02em]">Sulci</span>
          </Link>
          <Link href="/" className="text-[13px] text-neutral-500 hover:text-neutral-900 transition-colors">&larr; Back to home</Link>
        </div>
      </nav>

      <main className="max-w-[900px] mx-auto px-6 py-20 md:py-32">
        <div className="text-center mb-16">
          <h1 className="text-[2rem] md:text-[2.5rem] font-semibold tracking-[-0.04em] text-neutral-900 mb-4">Security at Sulci</h1>
          <p className="text-neutral-500 max-w-lg mx-auto text-[16px] leading-relaxed">
            We build clinical data infrastructure. Security and compliance are foundational to everything we do.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-20">
          {practices.map((p) => (
            <div key={p.title} className="p-6 rounded-xl border border-neutral-200/80 hover:border-neutral-300 hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)] transition-all">
              <div className="flex items-center gap-3 mb-3">
                <div className="h-9 w-9 rounded-lg bg-neutral-100 flex items-center justify-center">
                  <p.icon className="h-4.5 w-4.5 text-neutral-600" />
                </div>
                <h3 className="text-[15px] font-semibold text-neutral-900">{p.title}</h3>
              </div>
              <p className="text-[14px] text-neutral-500 leading-relaxed">{p.description}</p>
            </div>
          ))}
        </div>

        <div className="rounded-xl border border-neutral-200/80 p-8 md:p-10 text-center">
          <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">Responsible Disclosure</h2>
          <p className="text-[14px] text-neutral-500 leading-relaxed max-w-lg mx-auto mb-6">
            If you discover a security vulnerability, please report it responsibly. We appreciate the security research community and will work with you to address any valid findings.
          </p>
          <p className="text-[14px] text-neutral-900 font-medium">security@sulci.ai</p>
        </div>
      </main>
    </div>
  );
}
