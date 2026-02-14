import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { Providers } from "@/components/Providers";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { MainContent } from "@/components/MainContent";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const SITE_URL = "https://sulci.ai";
const SITE_NAME = "Sulci AI";
const SITE_DESCRIPTION =
  "Clinical ontology normalization — NLP extraction, UMLS and OMOP mapping, and knowledge graph infrastructure for modern health systems.";

export const metadata: Metadata = {
  title: {
    default: "Sulci AI — Clinical Ontology Normalization",
    template: "%s | Sulci AI",
  },
  description: SITE_DESCRIPTION,
  keywords: [
    "clinical ontology",
    "NLP extraction",
    "OMOP mapping",
    "UMLS",
    "knowledge graph healthcare",
    "clinical data normalization",
    "FHIR",
    "clinical AI",
    "health informatics",
    "clinical NLP",
    "OMOP CDM",
    "structured clinical data",
  ],
  authors: [{ name: SITE_NAME, url: SITE_URL }],
  creator: SITE_NAME,
  publisher: SITE_NAME,
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
    ],
    apple: "/favicon.svg",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: "Sulci AI — Clinical Ontology Normalization",
    description: SITE_DESCRIPTION,
    images: [
      {
        url: `${SITE_URL}/og-image.png`,
        width: 1200,
        height: 630,
        alt: "Sulci AI — Unstructured notes are a smooth brain. We add the folds.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Sulci AI — Clinical Ontology Normalization",
    description: SITE_DESCRIPTION,
    images: [`${SITE_URL}/og-image.png`],
    creator: "@sulci_ai",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: SITE_NAME,
      url: SITE_URL,
      logo: `${SITE_URL}/logo.png`,
      description: SITE_DESCRIPTION,
      sameAs: [
        "https://twitter.com/sulci_ai",
        "https://linkedin.com/company/sulci-ai",
        "https://github.com/sulci-ai",
      ],
      contactPoint: {
        "@type": "ContactPoint",
        contactType: "sales",
        email: "hello@sulci.ai",
      },
    },
    {
      "@type": "SoftwareApplication",
      name: SITE_NAME,
      url: SITE_URL,
      applicationCategory: "HealthApplication",
      operatingSystem: "Web",
      description: SITE_DESCRIPTION,
      offers: {
        "@type": "Offer",
        category: "Enterprise",
      },
      featureList: [
        "Clinical NLP extraction",
        "UMLS and OMOP concept mapping",
        "Knowledge graph construction",
        "FHIR import and export",
        "Clinical data normalization",
      ],
    },
    {
      "@type": "WebSite",
      name: SITE_NAME,
      url: SITE_URL,
      description: SITE_DESCRIPTION,
      publisher: {
        "@type": "Organization",
        name: SITE_NAME,
      },
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex flex-1 flex-col lg:pl-0 min-w-0">
              <Header />
              <MainContent>{children}</MainContent>
            </div>
          </div>
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
