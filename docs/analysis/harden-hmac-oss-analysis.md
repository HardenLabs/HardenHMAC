# HardenHMAC as Free Open-Source Library — Strategic Evaluation

**Date:** 2026-03-20
**Author:** Product (PM Agent)
**Status:** Final recommendation
**Prior analyses:**
- `harden-hmac-standalone-product-analysis.md` — evaluated as SaaS product (rejected), then as licensed SDK (deferred)
- `hmac-simplification-positioning.md` — HMAC as secondary value prop and acquisition channel

---

## Executive Summary

**Recommendation: Build it. But only after HardenAPI has 10+ paying customers, and with explicit scope constraints.**

The free OSS proposal is categorically different from everything evaluated previously. The prior analyses rejected a paid product and conditionally deferred a licensed SDK. The open-source library is what Section 5 of the standalone product analysis already called "strictly better" — it is the top-of-funnel acquisition channel that avoids every structural problem a paid product creates.

The objections that applied to the licensed SDK (price anchoring, cannibalization, "why not build it yourself") are either eliminated or inverted by going fully free. The new risks are different: maintenance overhead across three language SDKs, brand quality risk on an unmaintained OSS repo, and the risk that "free HMAC library" becomes the HardenLabs brand association before "managed ephemeral key rotation" does.

Those risks are real but manageable. The strategic opportunity — seeding the HardenLabs brand into developer ecosystems before a competitor does the same thing, and building a measurable top-of-funnel funnel tied directly to HardenAPI signups — outweighs them, provided the scope is right and the timing is after production launch.

---

## 1. Does Free OSS Solve the Prior Objections?

### 1.1 Price anchoring problem

**Prior verdict (paid product):** A $19-29 product anchors HardenAPI comparisons to "cheap HMAC wrapper" instead of "engineering cost of building and maintaining managed auth infrastructure." Destroys the correct price anchor.

**OSS verdict: Problem eliminated.**

When HardenHMAC is free, it becomes a reference implementation, not a product. The comparison HardenAPI faces is no longer "HardenHMAC ($29) vs HardenAPI Starter ($79)" — it is "HardenHMAC (free, I manage my own keys, no rotation) vs HardenAPI (I get automatic rotation, ephemeral keys, TOTP, degradation handling)." That comparison is one Harden wins clearly.

Critically, free OSS reinforces rather than undermines the rotation story. The library explicitly cannot do automatic key rotation — the customer has to manage their own key exchange. That limitation is not a bug in the free library; it is the feature gap that pulls users to HardenAPI. If Harden's marketing says "rotation is why you pay us," a free library that visibly cannot rotate keys is proof of the claim, not contradiction of it.

**One nuance:** The risk that remains is a developer who uses HardenHMAC and decides "static HMAC is good enough, we don't need rotation." That risk existed before the library did — those developers were already out of the target market. The library does not create new competition for HardenAPI's value proposition; it surfaces developers who are already making that trade-off and gives Harden visibility into that decision.

### 1.2 Cannibalization risk

**Prior verdict (paid product):** High cannibalization risk. Teams with 1-3 services and no rotation urgency would stay on HardenHMAC forever. No pair limit, no trial pressure, no natural upgrade trigger.

**OSS verdict: Risk substantially reduced, not eliminated.**

Free OSS does not generate the same retention gravity a paid product does. There is no subscription relationship to preserve, no billing page to check, no customer success touchpoint. A developer who outgrows HardenHMAC does not feel they are "leaving" — they are simply using a different tool for a bigger problem.

The residual risk: developers who are genuinely well-served by static HMAC (small internal tooling, low-value service pairs, hobby projects) will use HardenHMAC and never upgrade. This is fine. These are not HardenAPI customers now and they would not be without the library. Harden's actual market is teams with enough services and enough rotation urgency to justify $79-249/month.

The important constraint: the library must make the rotation gap explicit and prominent. Not buried in a footer — upfront in the README, in docs, and in the library itself when it makes sense (e.g., a comment in the key configuration section: "You are responsible for key rotation. For automatic ephemeral key rotation, see HardenAPI."). This is not a marketing trick; it is accurate documentation that serves developers and drives qualified interest.

### 1.3 "Why not build it yourself" objection

**Prior verdict (paid product):** Decisive objection. An experienced developer can implement HMAC in 2-3 hours. The argument "we wrote it so you don't have to" is not defensible at any price point.

**OSS verdict: Objection dissolved.**

When the library is free, "why not build it yourself" is answered by "you can, and this is what you'd build." HardenHMAC is not asking a developer to pay for something they could write. It is offering a maintained, correct, cross-language reference implementation that eliminates the canonical string format negotiation problem — the real pain identified in hmac-simplification-positioning.md.

The value proposition shifts from "convenience you pay for" to "correct implementation you can trust." These are entirely different conversations. A developer evaluating a free library does not ask "is this worth $X?" They ask "is this better than what I'd write myself?" For cross-language consistency and maintained framework integrations, the answer is yes for a substantial share of the target population.

### 1.4 Timing concern

**Prior verdict (licensed SDK):** Defer until HardenAPI has 10+ paying customers and churn data to validate the hypothesis.

**OSS verdict: Timing constraint partially relaxed, but not eliminated.**

The reason for the timing constraint was resource allocation: a pre-production team cannot afford to split engineering focus across two products. That reasoning still applies. The OSS library should not be built in parallel with getting HardenAPI to production.

However, the scope of the OSS library is meaningfully smaller than a licensed SDK product. No billing integration, no license Lambda, no Stripe setup, no account system. It is a library, a README, and a package publication pipeline. This is closer to 2-3 weeks of engineering work than 6-8, and it can legitimately be done by a single developer as a focused side effort after HardenAPI launches.

The 10-paying-customer threshold still applies. The specific reason: until HardenAPI has real users, Harden does not know which languages matter most in the target customer base. Building .NET + Python + Node.js before having any signal on which language stack the actual buyers use is premature. One founding member conversion from a Node.js shop changes the prioritization entirely.

**Adjusted threshold:** After HardenAPI has paying customers and language stack data from at least the founding member cohort. This is likely 4-8 weeks post-production launch, not months.

---

## 2. OSS Strategy

### 2.1 License choice

**Recommendation: Apache 2.0.**

Reasoning:
- Apache 2.0 includes an explicit patent grant. MIT does not. For a security library where Harden may have patentable methods in the canonical string construction or multi-layer signing approach, Apache 2.0 preserves optionality without asserting it.
- Apache 2.0 is the standard for developer infrastructure libraries from commercial-backed entities (Kubernetes, TensorFlow, gRPC). It signals "serious infrastructure," not "weekend project."
- MIT is fine but feels like a personal open-source contribution. Apache 2.0 feels like a company-backed library. The HardenLabs brand benefits from the latter signal.
- SSPL and BSL are non-starters — they are not recognized as open-source and would trigger immediate negative reaction from the developer community.

### 2.2 Governance model

**Model: Benevolent Dictator (HardenLabs-controlled), accepting PRs with review.**

Not a foundation model, not a pure community model. HardenLabs owns the spec and the canonical string format. Community contributions for framework integrations, bug fixes, and language ports are welcome but require review before merge. The canonical string format is not subject to community votes — it must be identical to HardenAPI's implementation or the migration path breaks.

Operational requirements:
- Issue triage: acknowledge within 72 hours, close or roadmap within 2 weeks
- PR review: merge or provide actionable feedback within 2 weeks
- Security disclosures: private disclosure email in README, 90-day disclosure timeline
- Language ports by the community: accepted if they include a test suite that validates canonical format parity against the reference implementation

The honest resource cost of this governance is 2-4 hours per week for a small library with modest initial adoption. It scales with adoption, which is the desirable direction.

### 2.3 HardenAPI upsell prominence in docs/README

**Recommendation: Prominent but non-aggressive. Once at the top, once at the natural upgrade trigger.**

The README structure should be:

```
1. What it is (2 sentences)
2. Installation (language-specific)
3. Quick start (30 lines of code)
4. What it does NOT do (explicit limitations section)
   - "HardenHMAC does not rotate keys. You are responsible for key exchange and rotation."
   - "For automatic ephemeral key rotation with zero key management overhead, see HardenAPI."
5. Full documentation
6. Contributing
```

The upsell appears twice: once in the README at section 4, and once in code-level comments where developers configure their secret key (the moment they feel the pain of manual key management). It does not appear in every function docstring, does not dominate the README, and does not appear as a banner or popup in the package manager listing.

This is the Stripe CLI model, not the freemium SaaS model. The upgrade path is clear but not pushy. Developers who need it will find it.

### 2.4 Package naming

**Recommendation: `@hardenlabs/hmac` (npm), `HardenLabs.Hmac` (NuGet), `hardenlabs-hmac` (PyPI).**

Not `@hardenhmac/*` — that namespace implies a product family that does not exist yet and creates a naming collision if HardenHMAC ever needs sub-packages. Not `@hardenlabs/hmac-*` — the suffix implies versioning or variants that add confusion.

The `HardenLabs` namespace is the correct company-level brand. `Hmac` is the library. Simple, discoverable, consistent across package managers.

The `hardenapi` npm/NuGet/PyPI name should be reserved separately for when HardenAPI ships official multi-language SDKs. These are distinct namespaces for distinct purposes.

---

## 3. Competitive Landscape

### 3.1 What exists today

The web search confirms what the prior analysis predicted: the OSS HMAC request signing space is fragmented, language-siloed, and mostly unmaintained.

Specific findings:
- **npm:** `hmac-sign-request`, `simple-hmac-auth`, `hmac-authentication-npm` (18F government project, likely unmaintained). No dominant solution with significant adoption.
- **PyPI:** `signit` (HMAC-SHA256 helper), `requests-http-signature` (supports multiple algorithms including HMAC), `apysigner`. No clear leader.
- **.NET / NuGet:** `Hmac` (signature creator/validator "inspired by AWS Signature V4"). Very low download counts. No framework middleware integration.

**Common failure modes across all of these:**
- Single-language only (no cross-language canonical format spec)
- No framework middleware (raw signing function, you wire it up yourself)
- Unmaintained (last commit 2-5 years ago for most)
- No timestamp validation or replay protection (just the signing primitive)
- No reference test suite for cross-language parity validation

### 3.2 The real gap HardenHMAC fills

The existing libraries treat HMAC signing as a cryptographic primitive problem. HardenHMAC treats it as a **service-to-service authentication coordination problem**.

The gap is not "we have better crypto code." The gap is:
1. **Cross-language canonical string format** — defined, versioned, and validated by an authoritative reference test suite. If Service A (Node.js) signs a request and Service B (.NET) validates it, HardenHMAC guarantees they agree. No other library makes this guarantee across languages.
2. **Framework middleware, not just signing functions** — ASP.NET Core middleware, FastAPI middleware, Express.js middleware. Developers configure it once, it handles all incoming/outgoing requests automatically. Existing libraries give you a function; you wire up the integration yourself.
3. **Correct replay protection** — timestamp validation with configurable window, nonce tracking. Most existing libraries omit this entirely or document it as "left as an exercise."
4. **Maintained canonical string format spec** — as a versioned document, so teams can reference "we implement HardenHMAC v1.0 canonical string format" in their API documentation without owning the spec themselves.

### 3.3 Is "opinionated, cross-language HMAC with the same canonical format" a real differentiator?

Yes, for the specific pain point the hmac-simplification-positioning.md analysis identified: the "API Contract Negotiator" persona who has to coordinate authentication between services owned by different teams, possibly in different languages.

The differentiator is not technical novelty — HMAC-SHA256 is not novel. The differentiator is **the canonical string format spec as a shared artifact that both teams can reference**. This is what eliminates the 2-day signature mismatch debugging cycle. Existing libraries each define their own format (or leave it to the developer), which means two teams using two different libraries still have the coordination problem.

HardenHMAC's canonical string format being identical to HardenAPI's implementation is the additional moat: teams that grow beyond manual key management can migrate to HardenAPI without changing their signing code. This is a real and specific upgrade path that no existing library can offer.

---

## 4. Funnel Mechanics

### 4.1 The conversion journey

```
Developer searches for "HMAC request signing [language]"
    → Finds HardenHMAC on GitHub / package registry
    → Installs it, integrates in 30 minutes
    → Uses it successfully for months

Trigger event (one of):
    A. Key rotation incident: static key leaks or gets committed to git
    B. SOC 2 / compliance audit: auditor asks about key rotation controls
    C. Scale: 4+ services, coordination overhead becomes painful
    D. Team expansion: new team member asks "why aren't we rotating keys?"

Developer reads the "What HardenHMAC does NOT do" section in README
    → Clicks the HardenAPI link
    → Starts free trial (no credit card, existing SDK knowledge transfers)
    → Upgrades to Starter ($79/month)
```

The conversion trigger is not manufactured by the library — it is a natural event that happens at a predictable point in a company's security maturity arc. HardenHMAC positions Harden to be the first brand the developer thinks of when that trigger fires, because they already trust and use the library.

### 4.2 Why this is better than cold PLG

Without HardenHMAC, the funnel starts at: "Developer has HMAC pain → searches for solutions → discovers HardenAPI → evaluates."

With HardenHMAC, the funnel starts at: "Developer has HMAC pain → finds free solution → uses it → discovers the limitation → already trusts HardenLabs → converts."

The pre-existing trust is the critical difference. A developer who has used HardenHMAC for six months and found it reliable does not need to evaluate HardenAPI from scratch. The brand has already passed the "do these people know what they're doing?" test. Conversion friction is dramatically lower.

This is the HashiCorp model: Vagrant (free) → Terraform (open core, paid Enterprise), and Consul/Vault (OSS) → Vault Enterprise. The OSS tool builds trust; the enterprise product captures value. HardenHMAC is Harden's Vagrant.

### 4.3 Measuring the funnel

**GitHub → npm/NuGet/PyPI → HardenAPI signups** is measurable with deliberate instrumentation:

| Metric | How to measure |
|--------|----------------|
| Library downloads | npm/NuGet/PyPI download stats (public) |
| GitHub stars / issues | GitHub Insights |
| HardenAPI signups mentioning HardenHMAC | Signup survey ("How did you hear about us?") |
| UTM-tagged README links | All README CTA links include `?utm_source=hardenhmac&utm_medium=readme` |
| Trial starts from HMAC referral | UTM tracking on the trial signup page |
| Trial-to-paid conversion from HMAC referral | Stripe + UTM source matching |

The UTM instrumentation is the critical piece. Without it, you cannot distinguish "organic search → HardenAPI" from "HardenHMAC → HardenAPI." Build the tracking before launch, not after.

A 1-3% conversion rate from library downloads to HardenAPI trials is realistic based on OSS-to-paid benchmarks. At 10,000 monthly downloads (achievable within 6 months of launch with HN and dev.to distribution), that is 100-300 trial starts per month from the library funnel alone — a meaningful acquisition channel.

---

## 5. Revised Risk Assessment

### 5.1 Brand risk: low-quality or abandoned OSS repo

**Risk level: High if unmitigated, Medium with constraints.**

An abandoned GitHub repo with unanswered issues is worse for the HardenLabs brand than having no OSS library at all. This is the most serious risk in the proposal.

Mitigation requirements (non-negotiable):
- Do not publish until the library is feature-complete for the initial scope (3 languages, framework middleware, canonical string format spec, reference test suite). A half-built library is a liability.
- Assign explicit ownership. One named engineer is the maintainer. Not "the team."
- Set public expectations in the README: "This library is maintained by HardenLabs. We respond to issues within 72 hours and merge community PRs within 2 weeks."
- If HardenLabs cannot sustain that commitment at any point, deprecate explicitly and redirect to HardenAPI rather than going silent.

### 5.2 Competitor forks

**Risk level: Low.**

Apache 2.0 permits forks. A competitor could fork HardenHMAC, strip the HardenAPI upsell, and publish under their own brand. This is possible but not a significant strategic threat: the canonical string format being identical to HardenAPI's is the moat, not the library code itself. A fork that changes the canonical format breaks the migration path and loses the primary value. A fork that keeps it reinforces HardenAPI's format as the standard.

If a competitor forks and gains significant adoption, that is evidence the library is valuable — which validates the HardenAPI positioning. Treat it as a forcing function to accelerate HardenAPI's SDK availability in the languages where the fork is gaining ground.

### 5.3 Resource cost (3 language SDKs as OSS)

**Risk level: Medium. Must be scoped aggressively.**

Three language SDKs means three sets of:
- Framework middleware implementations (ASP.NET Core, FastAPI/Flask, Express/Fastify)
- Dependency upgrade cycles
- Security patch obligations
- Issue backlogs

This is a real maintenance burden. The mitigation is scope discipline at launch:

**Phase 1 (launch):** .NET only. This is where Harden's existing SDK code lives. Extract the HMAC signing logic, add framework middleware, publish to NuGet. Total effort: 1-2 weeks.

**Phase 2 (post-launch, demand-driven):** Add the language that founding members actually use. If founding member data shows Python shops are the primary HardenAPI customer, Python is Phase 2. If it shows Node.js, Node.js is Phase 2.

**Phase 3:** Third language, driven by the same demand signal.

Do not commit to three languages at launch. The "cross-language interop" value proposition works as soon as there are two languages. The reference test suite for canonical format parity can be published immediately even if only one implementation exists — it defines the spec that future implementations must match.

### 5.4 Does free HMAC make HardenAPI feel overpriced or unnecessary?

**Risk level: Low, with correct framing.**

This is the version of the cannibalization risk that survives the OSS proposal. If HardenHMAC's docs don't explain clearly what it cannot do, a developer might conclude "I have HMAC, I don't need HardenAPI."

The mitigation is already embedded in the README structure from Section 2.3: an explicit "What this does NOT do" section that names rotation, ephemeral keys, and degradation handling as explicit gaps, with a link to HardenAPI as the solution. This is not marketing copy — it is accurate documentation.

The framing risk is more subtle: if HardenHMAC becomes strongly associated with "HMAC is easy," it could undermine the hmac-simplification-positioning.md caution about leading with HMAC simplification (Risk 2: anchors price expectations to $0).

The mitigation: HardenHMAC's positioning is "correct static HMAC implementation." HardenAPI's positioning remains "managed auth with automatic rotation." These are not competing claims — the library is explicitly the non-rotating version. The distinction is structural, not just a messaging choice.

---

## 6. Go-to-Market

### 6.1 Build timing: after HardenAPI production launch, not before

The reasoning from the prior analyses still holds. HardenAPI is the primary product. Getting to 10+ paying customers is the priority. A parallel OSS library project divides focus before the core product has validated revenue.

Specific timing trigger: after the founding member cohort is fully converted to paid and language stack data is available. This gives Phase 1 language prioritization signal and ensures the team has bandwidth.

### 6.2 Launch strategy

**Phase 1: Quiet launch + HN Show HN**

Do not Product Hunt until Phase 2 (multi-language). A .NET-only library will not land on Product Hunt — the audience is too broad and .NET HMAC is too niche.

For the initial launch:
- Publish to NuGet with complete docs
- Write "Why HMAC implementations disagree across languages" (the blog post from hmac-simplification-positioning.md) and publish on the HardenLabs blog
- Post "Show HN: HardenHMAC — opinionated cross-language HMAC for service-to-service auth" on Hacker News
- Cross-post technical blog to dev.to

The HN post should lead with the canonical string format problem, not the library itself. "We got tired of debugging signature mismatches between Node.js and .NET services, so we defined a shared canonical format and published implementations for both" is the story that resonates with HN.

**Phase 2: Product Hunt + broader distribution**

Once two languages are available, Product Hunt becomes viable. "Free cross-language HMAC library for service-to-service auth — works the same in .NET, Python, and Node.js" is a Product Hunt-worthy product. Include the HardenAPI context as the company behind it.

**Ongoing: Reddit (/r/devops, /r/netsec, /r/dotnet, /r/Python), developer newsletters**

The library is the content. Link the library in answers to HMAC questions on Stack Overflow where appropriate (when the library genuinely solves the OP's problem). This is legitimate community participation, not spam.

### 6.3 Can this be a side project?

**Phase 1 (single language, NuGet):** Yes. One engineer, focused sprint of 1-2 weeks after HardenAPI launches. This is extracting and cleaning up existing HMAC code from the .NET SDK — not building from scratch.

**Phase 2+ (multi-language):** No. Framework middleware for FastAPI and Express is real engineering work, and maintaining three language SDKs cannot be a side effort if Harden has paying customers to support on HardenAPI simultaneously. By Phase 2, the library should be generating enough HardenAPI pipeline to justify dedicated time.

---

## 7. Decision Matrix: All Options Compared

| Dimension | Free OSS Library | Licensed SDK ($29/mo) | HardenAPI Starter PLG only |
|-----------|-----------------|----------------------|---------------------------|
| Acquisition potential | High (zero friction, SEO, GitHub) | Medium (paid barrier) | Medium (14-day trial) |
| Upgrade conversion | Medium-High (explicit gap + trust) | Medium (migration easy) | High (pair limit pressure) |
| Brand coherence | Neutral-Positive (shows expertise) | Dilutes slightly | Reinforces |
| Engineering cost | Low Phase 1, Medium Phase 2+ | Medium (license Lambda, billing) | None |
| Revenue capture (direct) | None | Low ($29/mo) | High (existing tiers) |
| Cannibalization risk | Low | Medium | None |
| "Why not DIY" objection | Dissolved (it's free) | High | N/A |
| Price anchoring risk | None | Medium | None |
| Maintenance burden | Medium (ongoing) | Medium (billing + SDK) | None |
| Timing risk | Low after launch | Medium (pre-production wrong) | None |

**Verdict:** Free OSS library is the right vehicle for the developer acquisition goal. Do not charge for it.

---

## 8. Non-Negotiable Constraints

If this is built, these constraints are binding:

1. **After HardenAPI production launch.** No parallel builds. The primary product gets to paying customers first.

2. **Canonical string format is identical to HardenAPI's HMAC implementation.** Migration from HardenHMAC to HardenAPI must be "swap the key source, nothing else changes." Validate this with a shared test suite before publishing.

3. **Start with one language (.NET).** Expand demand-driven, not assumption-driven.

4. **Explicit "What this does NOT do" section in the README.** Named maintainer, 72-hour issue response commitment, explicit deprecation policy if maintenance drops.

5. **UTM tracking on all README and doc links to HardenAPI.** Measure the funnel from day one. If the library is not generating measurable HardenAPI trial traffic within 6 months of meaningful adoption, evaluate whether the maintenance cost is justified.

6. **Apache 2.0 license.** Not MIT, not SSPL.

7. **Package namespace: `HardenLabs.Hmac` (NuGet), `hardenlabs-hmac` (PyPI), `@hardenlabs/hmac` (npm).** Reserve `hardenlabs` namespace on all three registries before launch.

---

## What This Is Not

- Not a product. Not a tier. Not a revenue line.
- Not a stepping stone to a paid version (the licensed SDK analysis is separate and deferred).
- Not a substitute for HardenAPI content marketing (the blog posts and use-case pages from hmac-simplification-positioning.md should be built regardless of this library).
- Not a commitment to maintain indefinitely. If HardenAPI's paying customers are not coming through this channel, the library can be archived cleanly.

---

## Appendix: Competitive Library Landscape (March 2026)

From web search conducted during this analysis:

**npm:** `hmac-sign-request`, `simple-hmac-auth`, `hmac-authentication-npm` (18F). No dominant solution.
**PyPI:** `signit`, `requests-http-signature`, `apysigner`. Fragmented, mostly unmaintained.
**.NET/NuGet:** `Hmac` (inspired by AWS Sig V4). Very low downloads, no middleware.

Common failure modes: single-language, no framework middleware, no cross-language canonical format, unmaintained, no replay protection.

**HardenHMAC's actual differentiator:** Cross-language canonical string format spec, framework middleware (not just signing primitives), correct replay protection, maintained by a commercial entity with a support commitment.
