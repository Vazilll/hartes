---
trigger: model_decision
description: "Rules for designing and developing web interfaces, dashboards, and presentation slides"
---

# UI/UX & Frontend Development Rules

When creating, editing, or inspecting any frontend code (`.tsx`, `.jsx`, `.html`, `.css`, `frontend/`, `src/`):

1. **Aesthetic Compliance**:
   - Strictly follow `C:\vazus\services\memory\DESIGN_SYSTEM.md`.
   - Use the Obsidian Depth Palette (`#08090c` canvas, `#0e1017` surfaces, `border-white/[0.07]`).
   - Never generate default purple/pink gradients, Bootstrap styles, or plain gray surfaces.
2. **Typography**:
   - Headers: `tracking-tight`.
   - Technical numbers, metrics, IPs, ports, Git tags: `font-mono text-xs`.
3. **Icons & Controls**:
   - Use `lucide-react` with `strokeWidth={1.5}`.
   - All interactive items must have subtle transitions (`transition-all duration-150`).
4. **Verification**:
   - Verify build via `npm run build` or `oxlint`.
   - Verify via Playwright MCP on localhost before delivering to user.
