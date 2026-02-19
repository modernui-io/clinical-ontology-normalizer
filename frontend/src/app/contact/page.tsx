"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Brain, CheckCircle2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";

const INTEREST_OPTIONS = [
  { value: "general", label: "General Inquiry" },
  { value: "demo", label: "Product Demo" },
  { value: "pro", label: "Pro Plan" },
  { value: "enterprise", label: "Enterprise Plan" },
  { value: "partnership", label: "Partnership" },
  { value: "other", label: "Other" },
];

function ContactForm() {
  const searchParams = useSearchParams();
  const planParam = searchParams.get("plan");

  // Map plan param to interest value
  const initialInterest = planParam === "pro" ? "pro" : planParam === "enterprise" ? "enterprise" : planParam === "demo" ? "demo" : "general";

  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({
    name: "",
    email: "",
    company: "",
    role: "",
    interest: initialInterest,
    message: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="text-center py-16">
        <div className="h-16 w-16 rounded-full bg-emerald-50 flex items-center justify-center mx-auto mb-6">
          <CheckCircle2 className="h-8 w-8 text-emerald-500" />
        </div>
        <h2 className="text-[1.5rem] font-semibold text-neutral-900 mb-3">Thank you!</h2>
        <p className="text-neutral-500 max-w-md mx-auto mb-8">
          We've received your message and will get back to you within 1 business day.
        </p>
        <Link href="/">
          <Button variant="outline" className="rounded-xl">Back to home</Button>
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-[520px]">
      {/* Form title based on plan param */}
      {planParam && (
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 text-indigo-600 text-[13px] font-medium mb-2">
          {planParam === "pro" ? "Pro Plan Inquiry" : planParam === "enterprise" ? "Enterprise Inquiry" : "Demo Request"}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-[13px] font-medium text-neutral-700 mb-1.5">Name *</label>
          <input required value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-neutral-200 text-[14px] focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300" />
        </div>
        <div>
          <label className="block text-[13px] font-medium text-neutral-700 mb-1.5">Email *</label>
          <input required type="email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-neutral-200 text-[14px] focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-[13px] font-medium text-neutral-700 mb-1.5">Company</label>
          <input value={form.company} onChange={(e) => setForm({...form, company: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-neutral-200 text-[14px] focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300" />
        </div>
        <div>
          <label className="block text-[13px] font-medium text-neutral-700 mb-1.5">Role</label>
          <input value={form.role} onChange={(e) => setForm({...form, role: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-neutral-200 text-[14px] focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300" />
        </div>
      </div>

      <div>
        <label className="block text-[13px] font-medium text-neutral-700 mb-1.5">Interest Area</label>
        <select value={form.interest} onChange={(e) => setForm({...form, interest: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-neutral-200 text-[14px] focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300 bg-white">
          {INTEREST_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-[13px] font-medium text-neutral-700 mb-1.5">Message *</label>
        <textarea required rows={5} value={form.message} onChange={(e) => setForm({...form, message: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-neutral-200 text-[14px] focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300 resize-none" />
      </div>

      <Button type="submit" className="bg-neutral-900 text-white hover:bg-neutral-800 rounded-xl h-11 px-6 text-[14px]">
        <Send className="mr-2 h-4 w-4" /> Send Message
      </Button>

      <p className="text-[13px] text-neutral-400">
        Or reach us directly at <span className="text-neutral-600 font-medium">hello@sulci.ai</span>
      </p>
    </form>
  );
}

export default function ContactPage() {
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
        <h1 className="text-[2rem] md:text-[2.5rem] font-semibold tracking-[-0.04em] text-neutral-900 mb-3">Get in Touch</h1>
        <p className="text-[15px] text-neutral-500 mb-10 max-w-[480px]">
          Request a demo, ask about pricing, or tell us what you're building. We'd love to hear from you.
        </p>
        <Suspense>
          <ContactForm />
        </Suspense>
      </main>
    </div>
  );
}
