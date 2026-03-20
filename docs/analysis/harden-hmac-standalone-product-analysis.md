# HardenHMAC Standalone Product — Evaluation

**Date:** 2026-03-20
**Author:** Product (PM Agent)
**Status:** Final recommendation

---

## Executive Summary

**Recommendation: Do not build HardenHMAC as a standalone product.**

The core insight driving the proposal — HMAC implementation is painful and teams would pay a small amount to skip it — is real and validated by the hmac-simplification-positioning.md analysis. The strategic instinct to build a product ladder is also sound. But the proposed execution solves the wrong problem in the wrong way at the wrong time.

HardenHMAC as described (separate repo, separate product page, separate accounts, simple HMAC SDK wrapper) would create a permanent competitive anchor below HardenAPI that cannibalizes the bottom of the funnel without producing upgrade pressure. The right answer is to use the HMAC pain as acquisition content and PLG conversion material for HardenAPI Starter ($79), not to build a separate product that gives customers a reason to never upgrade.

The sections below explain each dimension in detail. A narrow alternative is identified at the end.

---

## 1. Product Definition Analysis

### What HardenHMAC would actually be

A HardenHMAC SDK that helps teams implement HMAC authentication quickly is, at its core, one of three things:

**Option A: A wrapper library.** Thin abstraction over standard HMAC-SHA256 with opinionated defaults (algorithm, encoding, canonical string format, timestamp, replay window). No server component. Ships as an open-source NuGet/pip/npm package.

**Option B: A static secret management service.** SDK + backend that handles key distribution and storage, but with static or manually rotated keys. Low operational complexity. Priced below $79/month.

**Option C: A reduced-feature HardenAPI.** Essentially HardenAPI Starter but at a lower price, possibly with a more limited feature set (no 14-day trial → always free, or flat $9-29/month).

Each of these fails for a different reason:
- **Option A** is not a product — it is an open-source library. It has no server costs, no retention, no upgrade path. If it is genuinely useful, it should be open-sourced and used as a top-of-funnel developer acquisition channel for HardenAPI — not a paid product.
- **Option B** (static secrets) is a step backward from HardenAPI's value proposition. Harden's entire differentiation is ephemeral keys that rotate automatically. Selling "we help you manage static secrets" actively contradicts the positioning and makes it harder to explain why rotation matters.
- **Option C** is just HardenAPI Starter with a different name on a different website, which is redundant and fragments the brand.

**What HardenHMAC does NOT do that HardenAPI does — and why those gaps are the point:**
- No ephemeral key rotation (static or manually rotated keys)
- No out-of-path architecture benefit (probably requires key distribution server anyway)
- No degradation handling (passthrough, dormant states, per-target recovery)
- No TOTP layer
- No service pair concept (bidirectional blast radius control)
- No dashboard or telemetry
- No trial → paid conversion infrastructure

Every feature HardenHMAC omits to stay simple is a feature that justifies HardenAPI's price. Removing them creates a product that is easier to dismiss, not easier to upgrade from.

---

## 2. Pricing Strategy Problems

### The floor and ceiling problem

If HardenHMAC is priced to capture the "below Starter" market, it needs to be priced below $79/month. Any reasonable price point (say $9-29/month) creates the following economic situation:

| Scenario | HardenHMAC | HardenAPI Starter | Upgrade delta |
|----------|-----------|-------------------|---------------|
| Monthly | $19/mo | $79/mo | $60/mo = 4.2x jump |
| Annual | $190/yr | $790/yr | $600/yr |

A 4x price jump for an upgrade is punitive even if the feature set justifies it, especially for a developer or small team who signed up for the cheap product expecting "good enough." The Starter plan's pair limit (5 pairs), not price, is what should trigger the upgrade. A separate cheaper product decouples the pricing signal from the constraint that actually drives expansion.

### The anchor problem

HardenHMAC would anchor HardenAPI's comparison to "$19/month HMAC wrapper" rather than "manual HMAC implementation + static secrets." The correct price anchor for HardenAPI is the engineering cost of building and maintaining what Harden replaces: ~40-80 hours of implementation time + ongoing key rotation coordination overhead. A $19 product destroys that anchor permanently for every customer who encounters HardenHMAC first.

This is the same risk identified in hmac-simplification-positioning.md (Risk 2), but amplified: instead of messaging that might anchor price expectations low, a separate product actively provides a $19 alternative.

### Free tier is worse, not better

A free tier for HardenHMAC makes the anchor problem structural. You now have a $0 product in the Harden ecosystem that does "HMAC authentication." Every enterprise prospect who encounters it will ask why they are paying $1,499/month for Business when there is a free Harden product that does HMAC.

---

## 3. Upgrade Path Assessment

### The "never upgrade" risk is not a risk — it is a near-certainty for a segment

The question posed is: "Risk of users staying on HardenHMAC forever and never upgrading."

For any team with 1-3 services that need auth between them, HardenHMAC would be genuinely sufficient. There is no pair limit pressure, no rotation urgency (if static keys work for them), and no compliance driver. These teams would stay forever. This is not a small segment — it describes most of the developers who would be attracted by the "cheap HMAC wrapper" pitch.

The teams most likely to upgrade are the ones who:
1. Hit the pair limit and need more
2. Experience a key leak incident and understand why rotation matters
3. Face a SOC 2 audit and need to demonstrate rotation controls

None of these upgrade triggers are better served by starting on HardenHMAC vs. starting on HardenAPI Starter. In fact, the Starter plan's 14-day trial and 5-pair limit already creates natural upgrade pressure. HardenHMAC removes both: no trial countdown, no pair constraint that causes operational pain.

### Migration friction would be real

Separate repo, separate product, separate accounts means a customer upgrading from HardenHMAC to HardenAPI would need to:
- Create a new HardenAPI account
- Re-register all services as service pairs
- Migrate credentials
- Update SDK references (if different SDK)
- Manage two billing relationships during transition

The proposal mentions "config compatibility" as a potential migration helper, but this requires ongoing engineering investment to maintain parity — which is exactly the kind of maintenance overhead that a pre-production team cannot afford.

---

## 4. Technical Scope Problems

### A simple HMAC SDK wrapper has zero server costs

If HardenHMAC is purely client-side with shared secrets (users manage their own key exchange), there is no server component to bill for. This is a library, not a SaaS product. The infrastructure economics that make HardenAPI viable ($1-6/month AWS cost, 98-99% margins) do not apply to a library. Revenue comes from adoption-driven upsell, not subscription value capture.

If HardenHMAC does have a server component (key distribution, at minimum), you have rebuilt a simplified HardenAPI backend with all the infrastructure overhead — Lambda, DynamoDB, KMS — but at a price point that cannot cover even the $1/month per-account KMS key cost at the low end.

Cost floor reality: The corrected cost model shows HardenAPI Starter costs $1.04/month to serve at plan maximum (5 pairs). A HardenHMAC product with a server component at $9-19/month is marginally viable but achieves nothing HardenAPI Starter's free trial cannot already accomplish. A HardenHMAC product without a server component (library only) has no AWS cost but also no subscription revenue and no natural SaaS retention mechanics.

### Language support prioritization is premature

The current SDK is .NET only. HardenMCP and HardenAPI multi-language support is already on the backlog. Building HardenHMAC SDKs across languages before HardenAPI is in production would mean:
- Multiple SDK surface areas to maintain before the core product has paying customers
- Developer time split between polishing HardenAPI for production and building a secondary product
- Risk that language-specific behavior inconsistencies in HardenHMAC undermine trust in HardenAPI

---

## 5. Competitive Positioning

### Who HardenHMAC actually competes with

A simple HMAC SDK competes directly with:
- `System.Security.Cryptography.HMACSHA256` (.NET, free)
- `hmac` (Python standard library, free)
- `crypto` (Node.js standard library, free)
- Every blog post titled "How to implement HMAC in X language" (free)
- GitHub Copilot (free)

The "why pay for this" story becomes: "We wrote the HMAC code so you don't have to." This is not defensible at any price point, because the counter-argument ("I can write this myself") is trivially true and demonstrably fast. An experienced developer can implement basic HMAC request signing in 2-3 hours, including canonical string construction and timestamp validation.

HardenAPI wins by moving the comparison away from "did you implement HMAC correctly" and toward "did you solve the system-level problems: cross-team coordination, key rotation at scale, replay protection, degradation handling." A HardenHMAC product that only solves the first problem gives prospects a valid reason to dismiss the system-level argument as oversold.

### The open-source library alternative is strictly better

If the real goal is top-of-funnel developer acquisition through HMAC pain, the right answer is an open-source HMAC implementation library that:
- Is opinionated (same canonical string format as HardenAPI)
- Is correct (replay protection, timestamp validation, cross-language consistency)
- Has a prominent "ready to add automatic key rotation? → HardenAPI Starter" CTA in the README and docs

This achieves the same developer acquisition outcome without:
- A second billing system
- A second support channel
- A second SDK surface area
- Brand fragmentation
- Upgrade friction

Open-source library with HardenAPI upsell is the canonical PLG motion for developer tools. It is not a novel idea, but it works: HashiCorp Vault open-source → Vault Enterprise, ngrok free → ngrok Teams, Sentry free plan → Sentry paid. The library builds trust and audience; the paid product captures value.

---

## 6. Risk Assessment

### Brand dilution: High risk

"Harden" as a brand currently means: out-of-path, ephemeral key rotation, zero-trust service-to-service auth. A product called "HardenHMAC" that is cheap and simple implies Harden is a spectrum from "simple HMAC wrapper" to "full security platform." This dilutes the primary brand message and makes the product family harder to explain.

The product ladder concept (HardenHMAC → HardenAPI → HardenMCP) sounds clean on a slide but creates real positioning problems:
- A prospect who hears about HardenHMAC first has already formed a mental model of Harden as a convenience tool, not infrastructure
- A security buyer evaluating HardenAPI sees the cheap product in the family and wonders what they are actually buying
- Press and community coverage will lead with the cheapest, most accessible product in the family, not the one you want to define the brand

### Competitive confusion: Medium risk

Three separate products named Harden{X} creates a "which one do I need?" problem that currently does not exist. HardenAPI is a single product with a clear tier progression. HardenHMAC forces a pre-purchase decision that adds friction exactly where PLG needs frictionless entry.

### Premature product diversification: High risk

HardenAPI is pre-production with zero paying customers. HardenMCP is a product strategy decision that was correctly analyzed and resolved (unified product, same billing). Adding a third product SKU before the first product has revenue is a resource allocation mistake.

The founding member program has 30 slots (20 HMAC + 10 RSA). Those slots are not filled yet. The immediate priority is converting founding members to paid, learning what they actually need, and getting to a production launch. A parallel HardenHMAC project would split engineering focus and delay that goal.

---

## 7. Go-to-Market Assessment

### Timeline and resource reality

Current state: HardenAPI pre-production, founding member beta active, multiple open PRs, SDK in .NET only.

A separate HardenHMAC product requires at minimum:
- Separate product site and positioning
- Separate SDK (or forked SDK with reduced feature set)
- Separate billing integration (or shared, which contradicts "completely separate")
- Separate documentation and onboarding
- Separate support workflow

Conservatively, this is 4-8 weeks of product and engineering work before a single customer can sign up. For a product with unclear revenue potential and high cannibalization risk, this is not the right use of pre-production bandwidth.

### The product ladder is a premature structure

Product ladders work when you have: (1) validated demand at multiple price points, (2) clear differentiation between rungs, and (3) demonstrated upgrade motion between them. None of these are true yet. The correct sequence is:

1. Launch HardenAPI, get founding members to paid, understand why they chose Harden
2. Identify which customers are stopping at Starter because the price or feature set is wrong for their scale
3. Decide whether the right response is a lower tier, a lighter product, or better acquisition content
4. Build what the data shows, not what the pre-launch hypothesis suggests

---

## What to Do Instead

The underlying insight — HMAC implementation is painful, teams would pay a small amount to fix it — is correct and worth acting on. The right channels are:

### 1. Open-source HMAC reference library (2-3 weeks, any language)

Publish `harden-hmac` as an open-source, opinionated HMAC implementation:
- Canonical string format identical to HardenAPI SDK
- Correct timestamp validation, replay window, cross-language consistency
- Ships with a static shared-secret model (user manages key exchange)
- README prominently explains the rotation problem and links to HardenAPI Starter trial

This is top-of-funnel acquisition, not a product. It generates GitHub stars, developer trust, and high-intent traffic from people actively solving the HMAC coordination problem.

### 2. HMAC-focused content marketing (ongoing, no engineering required)

Three high-ROI pieces from hmac-simplification-positioning.md analysis:
- "Why HMAC signatures disagree across languages" — long-form, technical, SEO-targeted
- Quick-start guide that explicitly states "no algorithm negotiation required"
- Conference talk angle for service reliability / platform engineering audiences

### 3. Use the Starter trial to do what HardenHMAC would do

HardenAPI Starter is already $79/month with a 14-day free trial, 5 pairs, and full HMAC support. For a developer who wants to skip HMAC implementation pain, this is the product. The friction is not price — it is perceived complexity. Fix the onboarding and quick-start, not the price point.

If conversion data after launch shows price is genuinely blocking Starter adoption (not just complexity), the right response is either a lower Starter price or a free tier with 1-2 pairs — not a separate product.

---

## Decision Matrix

| Dimension | HardenHMAC (separate product) | Open-source library | Starter PLG investment |
|-----------|-------------------------------|--------------------|-----------------------|
| Acquisition potential | Medium (paid barrier) | High (zero friction) | Medium (14-day trial) |
| Upgrade conversion | Low (no natural trigger) | Medium (rotation CTA) | High (pair limit pressure) |
| Brand coherence | Dilutes | Neutral | Reinforces |
| Engineering cost | High (separate product) | Low (library only) | Low (content + onboarding) |
| Revenue capture | Low-medium (cheap tier) | None direct | High (existing tiers) |
| Risk to HardenAPI | High (cannibalization) | Low | None |
| Timing | Wrong (pre-production) | Right (anytime) | Right (now) |

**Verdict:** Open-source library + Starter PLG investment. Not a standalone product.

---

## If You Proceed Anyway (Minimum Viable Constraints)

If after reading this analysis the decision is to build HardenHMAC anyway, these constraints are non-negotiable to limit downside:

1. **Same account system.** Do not create separate accounts. HardenHMAC is a feature tier within HardenAPI billing, not a separate product. This is the MCP precedent (unified product, type-agnostic billing).
2. **No static key distribution server.** If HardenHMAC has a backend, it must use the same KMS-backed ephemeral key architecture. Otherwise you are building a step backward in security and will explain forever why the cheap product is less secure.
3. **Pair limit of 2, not unlimited.** Without a hard constraint, users have no upgrade trigger. 2 pairs creates real pain at the right time.
4. **Price at $19/month, no free tier.** Free destroys the anchor entirely. $19 creates a price point that makes Starter ($79) feel like an obvious step-up, not a 4x shock.
5. **After production launch only.** This work does not start until HardenAPI has paying customers and conversion data to validate the hypothesis.

---

## Addendum: Re-Evaluation with Corrected Scope (2026-03-20)

**The above analysis assumed a managed-service scope. The corrected scope is a licensed SDK — fundamentally different.**

### What changed

The original analysis evaluated HardenHMAC as a product in one of three forms: (A) wrapper library, (B) static secret management service, or (C) reduced-feature HardenAPI. The actual concept is none of these: it is a **licensed SDK where the customer manages their own HMAC keys**, with a single license-check Lambda call on startup and no ongoing Harden infrastructure involvement in authentication.

This corrects several of the core objections:
- **Infrastructure cost:** Near-zero. One Lambda invocation per app boot. Margins ~100% minus Stripe fees.
- **Server component concerns:** Eliminated. Harden's backend is not involved in auth.
- **"Step backward in security" concern:** Eliminated. The security model is transparent — customer manages keys, SDK implements signing correctly.
- **Cannibalization via operational overlap:** Significantly reduced. HardenAPI manages ephemeral keys; HardenHMAC does not touch key management at all.

### Revised recommendation

**Conditionally viable. Defer until after HardenAPI has 10+ paying customers.**

The licensed-SDK model is a recognized product category (precedents: JetBrains tools, Redis Enterprise modules, Telerik component suites). The "why not just use a library" objection is real but answerable: cross-language interop guarantee, maintained canonical string format spec, security updates, framework integrations maintained across framework versions.

### Non-negotiable constraints for this scope

1. **Separate product, separate repo, separate billing.** NOT unified with HardenAPI. The operational model is different enough to justify separation (unlike MCP, which stayed unified). Forcing same-account would require an architecturally incompatible tier in seed-tier-config.py.
2. **Canonical string format identical to HardenAPI HMAC.** Migration = swap key source (env var to Harden-issued ephemeral key). No rewrite required. This is the migration path that makes the upgrade real.
3. **Multi-language required on day one.** .NET + Python minimum. .NET-only cannot defeat the "just write it yourself" objection for the majority of mixed-language microservice shops.
4. **$29/month, 14-day trial, annual option ($290/yr).** No free tier. Per-org license (covers all services and environments).
5. **Fail-open on license check failure.** Auth continues if Harden's license Lambda is unreachable. Log a warning. Do not make customer services dependent on Harden uptime for request auth.
6. **After HardenAPI production launch.** Founding member data and churn patterns must validate the hypothesis before building.

### What the constraints above get wrong for the corrected scope

- **"Same account system"** — wrong for this scope. Separate accounts are correct because the operational model is different.
- **"No static key distribution server"** — correct conclusion for the wrong reason. HardenHMAC has no server component for key distribution at all, not because it must use KMS, but because the customer manages their own keys.
- **"Pair limit of 2"** — does not apply. HardenHMAC has no pair concept; there is no natural limit to enforce.
- **"Price at $19/month"** — too low for the corrected scope. $29/month is appropriate given the multi-language cross-language guarantee and per-org licensing model.
