"use client";

import Link from "next/link";
import { Brain } from "lucide-react";

export default function TermsPage() {
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
        <h1 className="text-[2rem] md:text-[2.5rem] font-semibold tracking-[-0.04em] text-neutral-900 mb-3">Terms of Service</h1>
        <p className="text-[13px] text-neutral-400 mb-12">Last updated: February 15, 2026</p>

        <div className="prose prose-neutral max-w-none text-[15px] leading-relaxed text-neutral-600 space-y-8">
          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">1. Acceptance of Terms</h2>
            <p>By accessing or using the Sulci AI platform (&quot;Service&quot;), you agree to be bound by these Terms of Service (&quot;Terms&quot;). If you do not agree to these Terms, do not use the Service. These Terms apply to all users, including visitors, registered users, and API consumers.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">2. Description of Service</h2>
            <p>Sulci AI provides clinical ontology normalization tools, including natural language processing (NLP) extraction, UMLS and OMOP concept mapping, knowledge graph construction, and related clinical data infrastructure services. The Service is provided &quot;as is&quot; and is intended for use by healthcare organizations, clinical researchers, and data engineering teams.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">3. Account Registration</h2>
            <p>To use certain features of the Service, you must register for an account. You agree to provide accurate, current, and complete information during registration and to update such information as necessary. You are responsible for safeguarding your account credentials and for all activity that occurs under your account.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">4. Acceptable Use</h2>
            <p>You agree not to: (a) use the Service for any unlawful purpose; (b) attempt to gain unauthorized access to any part of the Service; (c) interfere with or disrupt the integrity or performance of the Service; (d) use the Service to process data in violation of applicable healthcare regulations including HIPAA; or (e) reverse engineer, decompile, or disassemble any part of the Service.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">5. Data and Privacy</h2>
            <p>Your use of the Service is also governed by our <Link href="/privacy" className="text-neutral-900 underline underline-offset-2">Privacy Policy</Link>. You retain ownership of all data you submit to the Service. We process your data solely to provide and improve the Service, and in accordance with applicable data protection laws and any Business Associate Agreement (BAA) in place.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">6. HIPAA Compliance</h2>
            <p>For customers who process Protected Health Information (PHI) through the Service, Sulci AI will enter into a Business Associate Agreement (BAA). The Service is designed and operated to support HIPAA compliance, including administrative, physical, and technical safeguards.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">7. Intellectual Property</h2>
            <p>The Service, including its design, code, algorithms, models, and documentation, is the property of Sulci AI, Inc. and is protected by copyright, trademark, and other intellectual property laws. You are granted a limited, non-exclusive, non-transferable license to use the Service in accordance with these Terms.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">8. Limitation of Liability</h2>
            <p>To the fullest extent permitted by law, Sulci AI shall not be liable for any indirect, incidental, special, consequential, or punitive damages, including loss of profits, data, or use, arising from your use of the Service. The Service is not intended to replace clinical judgment, and Sulci AI makes no warranties regarding the accuracy of clinical mappings or NLP outputs for diagnostic or treatment purposes.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">9. Termination</h2>
            <p>We may suspend or terminate your access to the Service at any time, with or without cause, upon notice. Upon termination, your right to use the Service will immediately cease. You may export your data for 30 days following termination.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">10. Changes to Terms</h2>
            <p>We may update these Terms from time to time. We will notify you of material changes via email or through the Service. Your continued use of the Service after changes take effect constitutes acceptance of the updated Terms.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">11. Medical Disclaimer</h2>
            <p>The Service is a data infrastructure tool for clinical data normalization and structuring. It is <strong className="text-neutral-900">not a medical device</strong> as defined by the FDA, and is not intended to diagnose, treat, cure, or prevent any disease or medical condition. The Service does not provide medical advice. Clinical outputs, including NLP extractions, ontology mappings, and knowledge graph representations, are intended for informational and research purposes only and should not be used as a substitute for professional medical judgment, diagnosis, or treatment. Users are solely responsible for validating all outputs before clinical use.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">12. Disclaimer of Warranties</h2>
            <p>The Service is provided &quot;as is&quot; and &quot;as available&quot; without warranties of any kind, either express or implied, including but not limited to implied warranties of merchantability, fitness for a particular purpose, accuracy, and non-infringement. We do not warrant that the Service will be uninterrupted, error-free, or free of harmful components. Performance metrics and benchmarks referenced in marketing materials are based on internal testing and may not reflect your specific results.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">13. Indemnification</h2>
            <p>You agree to indemnify, defend, and hold harmless Sulci AI, Inc. and its officers, directors, employees, and agents from and against any claims, liabilities, damages, losses, and expenses arising from: (a) your use of the Service; (b) your violation of these Terms; (c) your violation of any applicable law or regulation; or (d) any clinical decisions made based on Service outputs.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">14. Governing Law</h2>
            <p>These Terms shall be governed by and construed in accordance with the laws of the State of Florida, without regard to its conflict of law provisions. Any disputes arising from these Terms shall be resolved in the state or federal courts located in Orange County, Florida.</p>
          </section>

          <section>
            <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">15. Contact</h2>
            <p>For questions about these Terms, contact us at <span className="text-neutral-900 font-medium">legal@sulci.ai</span>.</p>
          </section>
        </div>
      </main>
    </div>
  );
}
