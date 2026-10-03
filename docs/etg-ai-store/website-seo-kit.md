# ETG AI Store — Website & SEO Kit

Owner: Novah Greywolf (they/them), Emerging Technology Group (ETG), etg.ai
Prepared: 2026-10-03 · Status: DRAFT. Nothing in this kit has been published.

> **Before you publish:** Every item marked `[CONFIRM]` needs a fact from Novah, such as an address, PECB partner status, lead times or a model list. Do not add prices, certifications, customer names, reviews or ratings that ETG cannot prove. Prices on hardware pages stay "Request a quote".

---

## 0. What we found (audit, 2026-10-03)

| Item | Finding |
|---|---|
| **etg.ai** | Live (HTTP 200). Built on **Hostinger Website Builder** (Zyro), so there is no code repository. `www` redirects with a 301 to the apex. robots.txt allows all crawlers. sitemap.xml lists 45 URLs. A canonical tag is set and OG tags are present. |
| **store.etg.ai** | **Down. DNS returns NXDOMAIN** (the hostname does not resolve). The VARStreet storefront is gone. The etg.ai nav "Store" menu points to on-site pages (`/ai-hardware-store`, `/ai-laptops`, `/ai-ready-nvidia-gpus`), not to store.etg.ai. |
| Home title | "Comprehensive AI & Cloud Solutions for Digital Transformation \| etg.ai". This is generic. It does not mention private or on-prem AI, hardware or a location. |
| Home meta description | 288 characters, so Google truncates it at about 155. It also opens with "EMERGING TECHNOLOGY GROUP" in all caps. |
| H1 | "Empowering AI Innovation". Vague, with no keyword. |
| Schema | Only a minimal `WebSite` JSON-LD. There is no `Organization`, `LocalBusiness`, `Product`, `Service` or `FAQPage` markup. |
| Images | 9 of 11 images on the homepage have no `alt` text. |
| Footer | Shows "© 2024". It is now 2026. |
| NAP | The site lists a phone number (+1 415 496 9339) and sales@etg.ai but **no street address or service area**. That hurts local SEO and the Google Business Profile. |
| Junk URL (live, in sitemap) | `/-youre-absolutely-right-i-missed-including-the-post-title-description-and-url-which-you-emphasized-...`. A chatbot reply was pasted into a blog slug. The page title is "SXM vs. PCIe GPUs…" and Google indexes the slug. |
| Thin or stray pages in the sitemap | `/tatyana`, `/palo-alto` (title only, no real content). There are also many single-GPU product pages for older cards (RTX 3090 Ti, A2000, A400 …) with no buying path. |
| Positioning gap | There is no page for "private AI", "local LLM", "on-prem AI", Supermicro, Vertiv, ISO 42001 or the spec check. |

---

## 1. Site map — AI Store section

Hostinger Builder works best with flat slugs, so every page uses a top-level slug with a consistent prefix.

```
/private-ai                         ← NEW pillar landing page "Private AI for Your Business"
├── /private-ai-hardware            ← hub (replaces /ai-hardware-store via 301)
│   ├── /desktop-ai-box             ← Tier 1: AMD Ryzen AI Max / NVIDIA desktop AI
│   ├── /rtx-ai-workstation         ← Tier 2: RTX AI workstations
│   ├── /supermicro-gpu-server      ← Tier 3: Supermicro Gold Series GPU servers
│   └── /vertiv-power-cooling       ← Add-on: Vertiv UPS / PDU / cooling
├── /private-ai-services            ← hub
│   ├── /private-ai-setup
│   ├── /private-ai-pilot
│   ├── /managed-ai-support         (301 from /ai-support-services)
│   ├── /ai-consulting-retainer     (301 from /ai-consulting-services-integration)
│   └── /iso-42001-training
├── /ai-spec-check                  ← "Which AI model fits your hardware?" tool + lead form
├── /private-ai-law-firms           ← vertical pages (phase 2)
├── /private-ai-healthcare
├── /private-ai-government-education
├── /private-ai-manufacturing
├── /book-a-consult                 ← calendar + form (single conversion page)
└── /blog/…                         ← content calendar (Section 7)
```

Navigation: change "Store" to **"Private AI"**, with the submenu Hardware · Services · Spec Check · Book a consult.
Keep the existing `/ai-ready-nvidia-gpus` and `/ai-laptops` pages, and link them from the hardware hub as "Components & laptops".

---

## 2. Landing page — "Private AI for Your Business" (`/private-ai`)

**Title tag:** Private AI Server for Business | On-Prem Local AI | ETG
**Meta description:** Run AI on your own hardware so your data never leaves the building. Desktop AI boxes, RTX workstations and Supermicro GPU servers, set up on your data by ETG.
**Target keyword:** private AI server for business (secondary: on-premise AI, local LLM for business)
**H1:** Private AI for Your Business

### Hero
**Private AI for Your Business**
Use AI on your contracts, records and customer data without sending any of it to the cloud. ETG supplies the hardware, installs a local AI model, connects it to your own files and keeps it running. Your data stays on hardware you own.

[Book a consult] [Run the spec check]

*Hardware ships in days, not months. Supermicro GPU servers typically ship in 2–3 business days.* `[CONFIRM current lead time]`

### The problem
Your team already uses ChatGPT. The question is what they paste into it.

- **Client and patient data can't go to a public AI.** Privilege, HIPAA, CJIS, FERPA, NDAs and contract terms often rule it out.
- **Cloud AI costs grow with headcount.** Per-seat subscriptions and API bills rise every month.
- **You can't audit what you can't see.** Regulators and customers increasingly ask how you govern AI (for example, under ISO/IEC 42001).

Private AI fixes all three. The model runs on a machine in your office or data center, reads only the documents you give it, and answers your team on your own network.

### Choose your hardware

| | **Desktop AI Box** | **RTX AI Workstation** | **Supermicro GPU Server** |
|---|---|---|---|
| Best for | Small teams or one department getting started | Power users, developers, document-heavy teams | Company-wide AI, many users, larger models |
| Platform | AMD Ryzen AI Max-class and NVIDIA desktop AI systems | NVIDIA RTX professional GPUs | Supermicro Gold Series multi-GPU servers |
| Where it lives | On a desk | Under a desk | In a rack or server room |
| Ships | `[CONFIRM]` | `[CONFIRM]` | Typically 2–3 business days |
| Price | Request a quote | Request a quote | Request a quote |

**Add-on: Vertiv power and cooling.** UPS, rack PDUs and cooling sized for GPU load, so your AI stays up.

Not sure which one you need? **Run the spec check.** It tells you which AI models fit a given GPU and memory size.

### Services
- **Private AI Setup:** We deliver the hardware, install a local model, connect it to your documents and train your team. You get a working private assistant, not a box of parts.
- **Private AI Pilot:** A short, scoped trial on one real workflow with clear success criteria, so you can prove value before you scale.
- **Managed AI Support:** Monitoring, updates, model refreshes and help-desk support for your private AI.
- **AI Consulting Retainer:** Ongoing strategy and implementation help from a team that has done this before. That covers use-case selection, data readiness, integrations and roadmap.
- **ISO/IEC 42001 AI Governance Training:** PECB ISO/IEC 42001 courses that teach your team how to run AI responsibly and be ready for an audit. `[CONFIRM PECB partner/trainer status wording]`

### Why ETG
- **Years of selling technology to government and education.** We know procurement, compliance and budget cycles.
- **Dell partner,** with Dell server projects delivered for a manufacturing customer.
- **Approved Supermicro webstore reseller,** with GPU servers that ship fast.
- **Hardware and AI expertise from one partner.** One team sizes the machine, installs the model and supports it.
- **Governance built in.** ISO/IEC 42001 training is available alongside deployment.

### How it works
1. **Consult (30 min):** Tell us your data, users and what you want AI to do.
2. **Spec check:** We match model size to hardware so you don't overbuy or underbuy.
3. **Quote and ship:** You get a written quote. Hardware ships, and servers typically go out in 2–3 days.
4. **Set up on your data:** We install the model, connect your documents and lock down access.
5. **Train and support:** Your team is onboarded. Managed support is available.

### FAQ
**What is private AI?**
Private AI means a large language model (LLM) runs on hardware you own, in your office or data center. Prompts and documents are processed locally and are never sent to a third-party AI provider.

**Can a local AI model be as good as ChatGPT?**
For many business tasks, such as summarizing, drafting, searching your documents and answering questions about your policies, current open models work well. Larger models need more GPU memory. The spec check shows what fits.

**What hardware do I need to run a local LLM?**
It depends on model size and the number of users. A desktop AI box handles a small team and mid-size models. RTX workstations add speed and capacity. Supermicro GPU servers support many users and larger models. Run the spec check or book a consult.

**Does the AI work without internet?**
Yes. Once it is set up, the model can run fully offline or on an isolated network. Updates are applied on a schedule you control.

**Is private AI compliant with HIPAA or attorney-client privilege?**
Keeping data on your own hardware removes the third-party AI processor from the picture, and that is the main concern for most compliance programs. Compliance still depends on your access controls and policies. We help you set those up, and ISO/IEC 42001 training covers AI governance.

**How fast can we get started?**
Supermicro GPU servers typically ship in 2–3 business days. A Private AI Pilot can begin once the hardware arrives. `[CONFIRM pilot duration]`

**Do you sell to government and schools?**
Yes. ETG has years of experience selling to government and education buyers. `[CONFIRM contract vehicles to list, if any]`

### Final CTA
**Your data. Your hardware. Your AI.**
Book a 30-minute consult, or run the spec check to see which models fit your hardware.
[Book a consult] [Run the spec check]
sales@etg.ai · +1 415 496 9339

---

## 3. Hardware tier pages

### 3.1 Desktop AI Box (`/desktop-ai-box`)
- **Title:** Desktop AI Box for Local LLMs | Ryzen AI Max & NVIDIA | ETG
- **Meta:** Compact desktop AI systems that run private LLMs on your desk. AMD Ryzen AI Max-class and NVIDIA desktop AI, set up with a local model on your data.
- **Target keyword:** AI mini PC for local LLM (secondary: desktop AI computer for business)
- **Copy:** This is the easiest way to start with private AI. It is a quiet desktop system with large unified memory, so it can run capable open models for a small team with no server room needed. ETG ships it with a local model installed and connected to the folders you choose. It is a good fit for a law office, clinic, agency or one department. **Options:** AMD Ryzen AI Max-class systems and NVIDIA desktop AI systems `[CONFIRM exact SKUs]`. **Price:** Request a quote. CTA: Run the spec check · Book a consult.

### 3.2 RTX AI Workstation (`/rtx-ai-workstation`)
- **Title:** RTX AI Workstation for Local LLMs & Private AI | ETG
- **Meta:** NVIDIA RTX professional workstations for faster private AI, RAG on your documents, and development. Configured, tested and set up by ETG.
- **Target keyword:** local LLM workstation (secondary: RTX AI workstation, AI workstation for business)
- **Copy:** RTX workstations give power users and developers more GPU memory and speed. That means faster answers, larger models, and room for document search (RAG), fine-tuning experiments and AI-assisted engineering. ETG configures GPU, memory and storage for your workload, and links to the RTX cards we already stock. **Price:** Request a quote. CTA: Run the spec check.

### 3.3 Supermicro GPU Server (`/supermicro-gpu-server`)
- **Title:** Supermicro GPU Servers for AI | Ships in 2–3 Days | ETG
- **Meta:** Supermicro Gold Series GPU servers for on-prem AI and LLM inference, typically shipping in 2–3 business days. Approved Supermicro reseller. Request a quote.
- **Target keyword:** Supermicro GPU server (secondary: on-premise AI server, GPU server for LLM inference)
- **Copy:** These servers bring company-wide private AI to your rack. Supermicro Gold Series multi-GPU servers serve many users at once and run larger models. ETG is approved to resell Supermicro through our webstore, and Gold Series systems typically ship in 2–3 business days. Add Private AI Setup and we install the model, connect your data and hand over a working system. Pair it with Vertiv power and cooling. **Price:** Request a quote.

### 3.4 Vertiv Power & Cooling (`/vertiv-power-cooling`)
- **Title:** Vertiv UPS, PDU & Cooling for AI Servers | ETG
- **Meta:** Keep GPU servers running. Vertiv UPS, rack PDUs and cooling sized for AI workloads, quoted together with your server.
- **Target keyword:** Vertiv UPS for GPU server
- **Copy:** GPU servers draw serious power and produce serious heat. ETG sizes Vertiv UPS, rack PDUs and cooling to your server so a power blip doesn't take down your AI. We quote it with the hardware so everything arrives together. **Price:** Request a quote.

---

## 4. Service pages

### 4.1 Private AI Setup (`/private-ai-setup`)
- **Title:** Private AI Setup | Local LLM Installed on Your Data | ETG
- **Meta:** We install a local AI model on your hardware, connect it to your documents, secure access and train your team. Private AI that works on day one.
- **Keyword:** private AI setup (secondary: local LLM installation service)
- **Copy:** You get hardware delivered and a local model installed, then connected to the documents you choose: policies, contracts, manuals, tickets. We set user access, test the answers against real questions and train your team. The deliverable is a working private assistant on your network.

### 4.2 Private AI Pilot (`/private-ai-pilot`)
- **Title:** Private AI Pilot | Prove Value on One Workflow | ETG
- **Meta:** A short, scoped private AI pilot on one real workflow, with clear success criteria, on hardware you keep. Book a pilot scoping call.
- **Keyword:** AI pilot program for business
- **Copy:** Pick one workflow, such as contract review, intake, an internal help desk or quoting. We define success up front, run it on private hardware with your data, and report the results. At the end you decide to scale, adjust or stop, based on evidence. `[CONFIRM duration/scope]`

### 4.3 Managed AI Support (`/managed-ai-support`)
- **Title:** Managed AI Support for Private & On-Prem AI | ETG
- **Meta:** Monitoring, updates, model refreshes and help-desk support for your on-prem AI, so your team keeps using it and IT doesn't have to babysit it.
- **Keyword:** managed AI services
- **Copy:** Private AI needs care, just like any server. ETG monitors health, applies updates, refreshes models as better ones are released, and answers your team's questions.

### 4.4 AI Consulting Retainer (`/ai-consulting-retainer`)
- **Title:** AI Consulting Retainer | Strategy to Deployment | ETG
- **Meta:** Ongoing AI consulting: use-case selection, data readiness, integrations and roadmap. Hands-on help from a team that ships hardware and software.
- **Keyword:** AI consulting services for small business
- **Copy:** You get a standing team for your AI program. Each month we prioritize use cases, prepare data, build integrations and keep your roadmap honest.

### 4.5 ISO/IEC 42001 Training (`/iso-42001-training`)
- **Title:** ISO/IEC 42001 Training | PECB AI Governance Courses | ETG
- **Meta:** PECB ISO/IEC 42001 AI management system training for your team. Learn to govern AI responsibly and prepare for certification.
- **Keyword:** ISO 42001 training (secondary: ISO 42001 lead implementer)
- **Copy:** ISO/IEC 42001 is the international standard for AI management systems. ETG offers PECB ISO/IEC 42001 courses so your team can build, run and improve AI governance. It pairs naturally with a private AI deployment. `[CONFIRM: which PECB courses (Foundation / Lead Implementer / Lead Auditor), delivery format, and ETG's PECB partner status. Do not claim "authorized" until confirmed.]`

### 4.6 Spec Check (`/ai-spec-check`)
- **Title:** Which AI Model Fits My GPU? Free Local LLM Spec Check | ETG
- **Meta:** Enter your GPU and memory and see which local AI models will run. A free spec check from ETG.
- **Keyword:** what GPU do I need to run LLM (secondary: LLM VRAM requirements)
- **Copy:** Find out what your hardware can run before you buy. Enter your GPU (or pick a tier) and the spec check tells you which open models fit and how comfortably. If you want more, we'll show the smallest upgrade that gets you there. *(Embed Novah's spec-check script here, or link a hosted version, and gate the detailed report behind an email field.)*

---

## 5. JSON-LD snippets

Paste these into Hostinger page settings under Custom code, in the head. Replace `[CONFIRM]` values first. **Do not add `aggregateRating`, `review` or `price`.**

### 5.1 Organization (site-wide)
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://etg.ai/#org",
  "name": "Emerging Technology Group",
  "alternateName": "ETG",
  "url": "https://etg.ai/",
  "logo": "https://assets.zyrosite.com/YbNvn2j916IvKyvP/logo-AoPvLojkbkHKxrWw.jpg",
  "email": "sales@etg.ai",
  "telephone": "+1-415-496-9339",
  "founder": { "@type": "Person", "name": "Novah Greywolf" },
  "areaServed": "US",
  "knowsAbout": ["Private AI", "On-premise AI", "Local LLM", "GPU servers", "ISO/IEC 42001"],
  "sameAs": ["[CONFIRM LinkedIn company URL]"]
}
```

### 5.2 Product (one per hardware page — example: Supermicro)
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Supermicro Gold Series GPU Server for Private AI",
  "brand": { "@type": "Brand", "name": "Supermicro" },
  "category": "GPU Server",
  "description": "Multi-GPU Supermicro Gold Series server for on-premise AI and LLM inference, configured and set up by ETG. Typically ships in 2–3 business days.",
  "url": "https://etg.ai/supermicro-gpu-server",
  "seller": { "@id": "https://etg.ai/#org" },
  "potentialAction": {
    "@type": "QuoteAction",
    "name": "Request a quote",
    "target": "https://etg.ai/book-a-consult"
  }
}
```
*Note:* Google's Product rich results need an `offers` block that includes a price. Without one, this markup still helps Google understand the page but won't show price snippets. That is the correct trade-off while prices are quote-only. Do not add a placeholder price.

### 5.3 Service (one per service page — example: Private AI Setup)
```json
{
  "@context": "https://schema.org",
  "@type": "Service",
  "name": "Private AI Setup",
  "serviceType": "On-premise AI deployment",
  "description": "ETG installs a local AI model on your own hardware, connects it to your documents, secures access and trains your team.",
  "provider": { "@id": "https://etg.ai/#org" },
  "areaServed": "US",
  "url": "https://etg.ai/private-ai-setup",
  "potentialAction": { "@type": "ReserveAction", "name": "Book a consult", "target": "https://etg.ai/book-a-consult" }
}
```

### 5.4 FAQPage (on /private-ai)
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    { "@type": "Question", "name": "What is private AI?",
      "acceptedAnswer": { "@type": "Answer", "text": "Private AI means a large language model runs on hardware you own, in your office or data center. Prompts and documents are processed locally and are never sent to a third-party AI provider." } },
    { "@type": "Question", "name": "What hardware do I need to run a local LLM?",
      "acceptedAnswer": { "@type": "Answer", "text": "It depends on model size and the number of users. A desktop AI box suits a small team, RTX workstations add speed and capacity, and Supermicro GPU servers support many users and larger models. ETG's free spec check shows which models fit your GPU." } },
    { "@type": "Question", "name": "Does the AI work without internet?",
      "acceptedAnswer": { "@type": "Answer", "text": "Yes. Once set up, the model can run fully offline or on an isolated network, with updates applied on a schedule you control." } },
    { "@type": "Question", "name": "How fast can we get started?",
      "acceptedAnswer": { "@type": "Answer", "text": "Supermicro Gold Series GPU servers typically ship in 2–3 business days, and setup on your data can begin once the hardware arrives." } }
  ]
}
```
FAQ rich results now show mainly for authoritative government and health sites. The markup is still worth adding for AI-answer engines and general understanding.

---

## 6. Google Business Profile

**Prerequisite:** a verifiable address. If ETG has no public storefront, set it up as a **service-area business** (hide the address and list service areas, e.g. San Francisco Bay Area, California, or nationwide). `[CONFIRM address/service area]` The NAP (name, address, phone) must match the site footer exactly.

**Primary category:** Computer consultant
**Secondary categories:** Computer store · Computer hardware store (if one is available, otherwise use Computer support and services) · IT services (or "Information technology company") · Business management consultant · Training centre / Educational consultant (for ISO 42001)

**Business description (≤750 characters):**
> Emerging Technology Group (ETG) helps businesses use AI without sending their data to the cloud. We supply and set up private, on-premise AI: desktop AI systems, NVIDIA RTX AI workstations, and Supermicro Gold Series GPU servers that typically ship in 2–3 business days, plus Vertiv power and cooling. Our Private AI Setup installs a local AI model on your own hardware and connects it to your documents. We also offer AI pilots, managed AI support, AI consulting and PECB ISO/IEC 42001 AI-governance training. ETG has years of experience serving government and education buyers and is a Dell partner. Book a consult or run our free spec check to see which AI models fit your hardware.

**5 starter posts:**
1. **Launch:** "Private AI is here. ETG now sets up AI that runs on your own hardware, so client and patient data never leaves your building. Book a 30-minute consult." CTA: Book → /book-a-consult
2. **Speed:** "Need GPU servers fast? Supermicro Gold Series GPU servers for on-prem AI typically ship in 2–3 business days. Request a quote." CTA: Learn more → /supermicro-gpu-server
3. **Spec check:** "Which AI model can your GPU run? Try our free spec check before you buy hardware." CTA: Learn more → /ai-spec-check
4. **Law firms:** "Privilege and public AI don't mix. A private AI assistant reviews contracts and searches your files entirely on your own network." CTA: Learn more → /private-ai-law-firms
5. **Governance:** "Customers are starting to ask how you govern AI. ISO/IEC 42001 training helps your team build an AI management system. Ask about upcoming sessions." CTA: Learn more → /iso-42001-training

---

## 7. Content calendar: 8 posts, 2 per month, Nov 2026 to Feb 2027

| # | Month | Title | Target keyword | Outline |
|---|---|---|---|---|
| 1 | Nov wk1 | What Is Private AI? A Plain-English Guide for Business Owners | what is private AI | Definition · cloud vs. local · what stays on your hardware · 5 common use cases · when cloud is fine · CTA to spec check |
| 2 | Nov wk3 | How Much GPU Do You Need to Run a Local LLM? | what GPU do I need to run LLM | Why VRAM and memory matter most · model size vs. memory (general ranges, no invented benchmarks) · users and concurrency · quantization in plain terms · desktop vs. workstation vs. server · embed the spec check |
| 3 | Dec wk1 | Private AI for Law Firms: Using LLMs Without Risking Privilege | private LLM for law firms | Ethics and confidentiality concerns · what goes wrong with public AI · on-prem architecture · use cases (contract review, research memos, intake) · access controls · pilot path |
| 4 | Dec wk3 | Desktop AI Box vs. RTX Workstation vs. GPU Server: Which Is Right for You? | AI workstation vs GPU server | Decision table · team size · model size · noise, power and space · upgrade path · Vertiv power considerations · quote CTA |
| 5 | Jan wk1 | ISO/IEC 42001 Explained: What It Means for Businesses Using AI | ISO 42001 | What the standard covers · AIMS basics · who needs it · how it relates to ISO 27001 · PECB training paths · CTA |
| 6 | Jan wk3 | HIPAA and AI: Why Clinics Are Moving to Local Models | HIPAA compliant AI on premise | PHI and third-party processors · BAAs vs. keeping data local · practical use cases (notes, policies, scheduling) · safeguards checklist · not legal advice disclaimer |
| 7 | Feb wk1 | On-Prem AI for Government and Schools: A Buyer's Checklist | on-premise AI for government | Data residency · procurement realities · security reviews · sizing · support and training · ETG's government/education experience |
| 8 | Feb wk3 | Cloud AI Subscriptions vs. Owning Your AI Hardware: A Cost Framework | local LLM vs cloud cost | Cost drivers on each side (seats, tokens, hardware, power, support) · a worksheet the reader fills in · break-even thinking (no made-up numbers) · CTA consult |

Every post links to `/private-ai`, one hardware page and the spec check. Repurpose each one as a LinkedIn post and a GBP post.

---

## 8. Target keywords (15)

| # | Keyword | Intent | Page |
|---|---|---|---|
| 1 | private AI server for business | Commercial | /private-ai |
| 2 | local LLM workstation | Commercial/Transactional | /rtx-ai-workstation |
| 3 | private LLM for law firms / on-prem AI for law firms | Commercial (vertical) | /private-ai-law-firms, blog 3 |
| 4 | ISO 42001 training | Transactional | /iso-42001-training |
| 5 | what GPU do I need to run LLM | Informational (lead magnet) | /ai-spec-check, blog 2 |
| 6 | on-premise AI server | Commercial | /private-ai-hardware |
| 7 | Supermicro GPU server | Transactional | /supermicro-gpu-server |
| 8 | GPU server for LLM inference | Commercial | /supermicro-gpu-server |
| 9 | AI mini PC for local LLM | Transactional | /desktop-ai-box |
| 10 | AI workstation California / Bay Area | Local | /private-ai + GBP |
| 11 | private AI setup / local LLM installation service | Commercial | /private-ai-setup |
| 12 | managed AI services | Commercial | /managed-ai-support |
| 13 | ISO 42001 lead implementer | Transactional | /iso-42001-training |
| 14 | HIPAA compliant AI on premise | Commercial (vertical) | /private-ai-healthcare, blog 6 |
| 15 | Vertiv UPS for GPU server | Transactional | /vertiv-power-cooling |

**Competitive notes:** Results for "AI workstation" are led by custom builders (Puget Systems, Exxact in Fremont CA, VRLA Tech in Los Angeles, Bizon) and by MSP-style "private AI" pages (Petronella Tech and others). Law-firm results are dominated by content sites (law.co, scand.com, premai.io). PECB itself and training partners (TÜV, Global Knowledge) own the ISO 42001 results. **ETG's edge:** hardware, fast Supermicro shipping, setup on your data and governance training from one vendor, plus government and education experience. Few competitors combine all four. Lead with that bundle, not with specs.

---

## 9. Technical SEO checklist (from the audit)

**Urgent (this week)**
- [ ] **Fix the junk slug.** Rename `/-youre-absolutely-right-i-missed-…` to `/sxm-vs-pcie-gpus-llm-training` and add a 301 from the old URL in Hostinger's redirect settings. Then resubmit the sitemap.
- [ ] **Publish `/private-ai`** and put it in the main nav. Today there is no page targeting the core offer.
- [ ] **Rewrite the homepage title, meta and H1.** Title: "Private AI & GPU Servers for Business | ETG (etg.ai)". Meta: keep it to 155 characters or fewer and mention private AI, hardware and setup. H1: "Private AI on Hardware You Own".
- [ ] **Resolve store.etg.ai.** It is NXDOMAIN now. Either (a) add a DNS record that 301-redirects `store.etg.ai/*` to `etg.ai/private-ai-hardware` to keep any old backlinks or bookmarks, or (b) leave it dead and remove it from Google Search Console. Option (a) is recommended.
- [ ] **Update the footer** to "© 2026" and add NAP (address or service area plus phone).

**Next (2–4 weeks)**
- [ ] Add alt text to every image (9 of 11 on the homepage have none).
- [ ] Add the Organization JSON-LD site-wide, plus Product, Service and FAQPage per page (Section 5).
- [ ] Noindex or delete `/tatyana` and `/palo-alto` unless they are intentional. If `/palo-alto` is meant as a location page, build it out properly.
- [ ] Consolidate the older single-GPU product pages (RTX 3090 Ti, A2000, A400 …). Either update them with a "Request a quote" path or 301 them to `/rtx-ai-workstation` or `/ai-ready-nvidia-gpus`.
- [ ] Add 301s: `/ai-hardware-store` → `/private-ai-hardware`, `/ai-support-services` → `/managed-ai-support`, `/ai-consulting-services-integration` → `/ai-consulting-retainer`.
- [ ] Remove the duplicated Privacy Policy links (7 instances on the homepage).
- [ ] Verify Google Search Console and Bing Webmaster Tools, submit the sitemap and check Coverage for the junk URL.
- [ ] Set up GA4 conversion events for Book a consult and Run spec check.
- [ ] Create the Google Business Profile (Section 6) with NAP that matches the site.

**Ongoing**
- [ ] Publish 2 posts a month (Section 7) and interlink them to /private-ai and the hardware pages.
- [ ] Earn links from the Supermicro partner locator, the Dell partner directory and the PECB partner listing `[CONFIRM eligibility]`, plus local chambers and government/education vendor lists.
- [ ] Run a PageSpeed Insights check on mobile. Hostinger pages are heavy (the homepage HTML is about 316 KB), so compress images.

---

## 10. Store recommendation

**Don't revive VARStreet. Sell from etg.ai with "Request a quote", and add a lightweight cart only for the few SKUs you can price.** store.etg.ai no longer resolves, the account has had a billing problem since 2024, and VARStreet's main strength is a huge distributor catalog with live pricing. That is the opposite of this offer: a small set of configured AI systems sold with setup services, where every deal is a consult and a quote. **The deciding factor is that the buyer here purchases a configured solution after a conversation, not an item off a shelf.** A quote-first flow on etg.ai (Hostinger form plus calendar, with quotes generated from Novah's existing tools) converts better, keeps SEO on one domain, and costs nothing extra. If Supermicro's approved-webstore terms *require* a cart, add Hostinger's built-in eCommerce or a Shopify Lite/Buy Button for the Gold Series SKUs on `/supermicro-gpu-server` only. Revisit VARStreet only if catalog volume (hundreds of SKUs with live distributor pricing) becomes the business. `[CONFIRM Supermicro webstore requirements]`

---
*Sources consulted for competitor research: ragic.com, palark.com, petronellatech.com, bestructured.com, vrlatech.com, law.co, scand.com, premai.io, pecb.com, globalknowledge.com, TÜV Academy, NICCS (CISA).*
