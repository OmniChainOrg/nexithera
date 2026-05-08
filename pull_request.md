## Pull request: Initial NexiThera website

### Summary

This pull request introduces the first public version of **NexiThera.com**, the new home for our autonomous scientific discovery engine.  The changes comprise a complete one‑page website built with vanilla HTML, CSS and JavaScript that reflects NexiThera’s brand identity and mission.  The narrative has been substantially expanded to convey the company’s role as an autonomous scientific discovery venture, highlighting precision medicine, biologics, synthetic biology, translational science, computational therapeutics, genomic/proteomic systems, formulation intelligence, regenerative medicine and probabilistic biomedical infrastructure.

### Key features

- **Modern, responsive design** using a dark base palette with **green accents** (life sciences) and **purple accents** (advanced technology) inspired by biotech/AI ventures such as Aitia【661798392917105†L22-L29】.
- **Navigation bar** with anchor links for smooth scrolling between sections.
- **Hero section** summarising the company mission: *“Autonomous Cognition for Next‑Generation Therapies”* and introducing our expanded narrative around precision medicine, biologics, synthetic biology, translational science, autonomous discovery, computational therapeutics, genomic/proteomic systems, formulation intelligence, regenerative medicine and probabilistic biomedical infrastructure.
- **About section** explaining the evolution from TheraVac and the integration of Genovate and ChronoThera within EpistemicOS.
- **Platform section** now features four cards detailing the core pillars of our cognition stack: **EpistemicOS** (verifiable intelligence kernel), **Agentic Orchestration** (up to 10 powerful AI‑Agents collaborating across domains), **Guardian – Human Variant** (ethics and oversight) and **Data Fusion** (multi‑omics, genomic/proteomic integration and probabilistic biomedical infrastructure).  The previous CXUs and OmniChain cards have been replaced to reflect the updated architecture.
- **Programs section** listing key therapeutic areas: **Immunotherapies**, **Synthetic Biology & Systems**, **Regenerative Medicine & Longevity**, and **Adaptive Formulations & Formulation Intelligence**, each with richer descriptions that embed our mission’s keywords (precision medicine, biologics, translational science, computational therapeutics, genomic/proteomic systems, regenerative medicine, formulation intelligence and longevity).
- Placeholder sections for **News**, **Careers** and **Contact**, ready for expansion.
- **Footer** with copyright notice and links to legal documents.
- **Smooth scrolling** implemented with a small JavaScript helper.
- All assets are self‑contained: no external images or fonts; the site loads quickly and works offline.

### Files added

- `index.html` – main HTML document with semantic structure and anchor links.
- `styles.css` – stylesheet implementing the colour scheme, layout grid and typography.
- `script.js` – JavaScript for smooth anchor scrolling.
- `pull_request.md` – this PR description.

### How to test

1. Navigate to the `/workspace/nexithera` directory.
2. Open `index.html` in any modern browser.
3. Resize the browser window to ensure responsive behaviour.
4. Click the navigation links to confirm smooth scrolling.

### Next steps

This initial site intentionally focuses on a clean structure and narrative flow.  Future improvements could include:

- Adding multilingual support (English/French) for our European audience.
- Implementing a blog/news feed and integrating with a CMS.
- Embedding interactive visuals or diagrams explaining EpistemicOS.
- Replacing placeholder text with dynamic content from our backend.
- Adding analytics and accessibility enhancements.

Please review the code and share any feedback.  Once merged, this will deploy NexiThera.com to production.