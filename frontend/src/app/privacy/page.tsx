"use client";

import Link from "next/link";
import { Brain } from "lucide-react";

export default function PrivacyPage() {
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

      <main className="max-w-[720px] mx-auto px-6 py-20 md:py-32">
        <h1 className="text-[2rem] md:text-[2.5rem] font-semibold tracking-[-0.04em] text-neutral-900 mb-3">Privacy Policy</h1>
        <p className="text-[13px] text-neutral-400 mb-12">Last updated: February 15, 2026</p>

        <div className="prose prose-neutral max-w-none text-[15px] leading-relaxed text-neutral-600 space-y-8">
          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">1. Introduction</h2>
            <p>Sulci AI, Inc. (&quot;Sulci,&quot; &quot;we,&quot; &quot;us&quot;) is committed to protecting the privacy and security of your information. This Privacy Policy describes how we collect, use, disclose, and safeguard information when you use our clinical ontology normalization platform and related services.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">2. Information We Collect</h2>
            <p><strong className="text-neutral-900">Account Information:</strong> Name, email address, organization, and role when you create an account.</p>
            <p><strong className="text-neutral-900">Clinical Data:</strong> Documents, notes, and data you submit for processing through our NLP and mapping services. This may include Protected Health Information (PHI) governed by a BAA.</p>
            <p><strong className="text-neutral-900">Usage Data:</strong> API call logs, feature usage patterns, and performance metrics to improve the Service.</p>
            <p><strong className="text-neutral-900">Device Information:</strong> Browser type, IP address, and operating system for security and analytics purposes.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">3. How We Use Your Information</h2>
            <p>We use collected information to: (a) provide and operate the Service; (b) process clinical data through our NLP and ontology mapping pipelines; (c) improve model accuracy and Service performance; (d) communicate with you about your account and Service updates; (e) ensure the security and integrity of the platform; and (f) comply with legal obligations.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">4. Protected Health Information</h2>
            <p>When customers process PHI through the Service, we act as a Business Associate under HIPAA. We process PHI only as permitted by the BAA and applicable law. PHI is encrypted at rest (AES-256) and in transit (TLS 1.3), and access is restricted to authorized personnel and systems. We do not use PHI for model training without explicit, separate authorization.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">5. Data Sharing</h2>
            <p>We do not sell your personal information or clinical data. We may share information with: (a) service providers who assist in operating the platform, under strict contractual obligations; (b) law enforcement when required by law; and (c) in connection with a merger, acquisition, or sale of assets, with prior notice to you.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">6. Data Retention</h2>
            <p>We retain your data for as long as your account is active or as needed to provide the Service. Clinical data is retained per your organization&apos;s configured retention policy. You may request data deletion at any time, subject to legal and regulatory retention requirements.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">7. Security</h2>
            <p>We implement industry-standard security measures including encryption, access controls, audit logging, and regular penetration testing. Our infrastructure is SOC 2 Type II certified. For more details, see our <Link href="/security" className="text-neutral-900 underline underline-offset-2">Security page</Link>.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">8. Your Rights</h2>
            <p>You have the right to: (a) access your personal data; (b) correct inaccurate data; (c) request deletion of your data; (d) export your data in a machine-readable format; and (e) withdraw consent for data processing where applicable. To exercise these rights, contact <span className="text-neutral-900 font-medium">privacy@sulci.ai</span>.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">9. Changes to This Policy</h2>
            <p>We may update this Privacy Policy from time to time. We will notify you of material changes via email and update the &quot;Last updated&quot; date above.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">10. Contact</h2>
            <p>For questions about this Privacy Policy, contact us at <span className="text-neutral-900 font-medium">privacy@sulci.ai</span>.</p>
          </section>
        </div>
      </main>
    </div>
  );
}
