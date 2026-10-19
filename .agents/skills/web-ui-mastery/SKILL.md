---
name: web-ui-mastery
description: |
  Mastery in building premium, high-density, production-grade web applications, dashboards,
  and landing pages with Aeza/Linear/Vercel dark neo-brutalist aesthetics.
  Enforces zero-amateur UI rules, Bento-grid layouts, typography hierarchies,
  Playwright headless visual feedback verification, and clean React + Vite + Tailwind architectures.
  Use whenever creating, updating, or styling websites, dashboards, frontends, or UI components.
---

# Web UI Mastery: Production-Grade Design & Engineering Standard

This skill establishes the strict engineering and design standards for creating web applications, dashboards, presentation slides, and user interfaces within the Vazus ecosystem. It eliminates generic LLM web output and guarantees high-density, modern aesthetic and functional quality.

---

## 1. Aesthetic Benchmark (The Aeza / Annet / Linear Standard)

Every UI must conform to **Dark Neo-Brutalism & High Information Density**:

### Color Palette (Obsidian Depth Scale)
- **Base Canvas (Level 0)**: `#08090c` (deep obsidian / near-black void). Never pure `#000000` or washed-out `#1f2937`.
- **Primary Surface / Cards (Level 1)**: `rgba(14, 16, 22, 0.75)` or `#0e1017` with `backdrop-blur-md`.
- **Elevated Surfaces / Modals / Tooltips (Level 2)**: `#141722` or `#181b26`.
- **Subtle Hairline Borders**: `1px solid rgba(255, 255, 255, 0.07)` (`border-white/[0.07]`).
  - Hover state: `rgba(255, 255, 255, 0.16)` (`hover:border-white/[0.16]`).
- **Text Hierarchy**:
  - Headings: `#ffffff` with `tracking-tight` (`letter-spacing: -0.025em`).
  - Body: `#e2e8f0` (clean high-contrast readability).
  - Secondary/Muted: `#888d9b` or `text-zinc-400`.
  - Micro / Labels / Footers: `text-zinc-500` or `text-zinc-600`.
- **Status & Accent Colors (Neon on Dark)**:
  - Online / Healthy / Git Sync: Emerald (`#10b981`, `bg-emerald-500/10 text-emerald-400 border-emerald-500/20`).
  - Active / Primary / Action: Cyan (`#06b6d4`, `bg-cyan-500/10 text-cyan-400 border-cyan-500/20`).
  - Risk / Warning / Attention: Amber (`#f59e0b`, `bg-amber-500/10 text-amber-400 border-amber-500/20`).
  - Critical / Failure / Rollback: Rose / Crimson (`#f43f5e`, `bg-rose-500/10 text-rose-400 border-rose-500/20`).
  - AI / Neural / Special: Violet (`#8b5cf6`, `bg-violet-500/10 text-violet-400 border-violet-500/20`).

---

## 2. Strict Negative Rules (What NOT to Do)

❌ **NO Purple-to-Pink Gradients**: Never use generic LLM gradients (`from-purple-500 to-pink-500`) unless explicitly demanded.
❌ **NO Unstyled Windows Scrollbars**: Always apply slim 6px dark webkit scrollbars.
❌ **NO Low Information Density**: Never leave giant empty voids with only 2 lines of text. Use Bento Grid cards, stat metrics, badges, and quick toggles.
❌ **NO Clumsy Font Sizes**: Numbers, telemetry, IPs, ports, Git hashes, and statuses MUST use `font-mono text-xs`.
❌ **NO Raw Unstyled HTML Elements**: Inputs, selects, and buttons must have explicit focus rings, hover transitions, and dark styling.
❌ **NO Blind Delivery**: Never declare completion without building and verifying in headless browser.

---

## 3. Mandatory UI Primitives & CSS Toolkit

### Glass Panels & Hover
```css
.glass-panel {
  background: rgba(14, 16, 22, 0.75);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.07);
}

.glass-panel-hover {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.glass-panel-hover:hover {
  border-color: rgba(255, 255, 255, 0.16);
  background: rgba(18, 21, 28, 0.85);
}
```

### Radar Status Dot (Aeza pulsing dot)
```html
<span class="relative flex h-2 w-2">
  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
  <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
</span>
```

### Slim Dark Scrollbar
```css
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #08090c; }
::-webkit-scrollbar-thumb { background: #27272a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3f3f46; }
```

---

## 4. Closed-Loop Verification Protocol

When creating or modifying any frontend:
1. **Compile & Lint Check**:
   Run `npm run build` or `oxlint` to guarantee zero syntax or TypeScript errors.
2. **Headless Browser Verification (Playwright MCP)**:
   - Navigate to the page using `call_mcp_tool` (`ServerName: "playwright"`, `ToolName: "browser_navigate"`).
   - Check `browser_console_messages` to ensure zero uncaught errors or unhandled exceptions.
   - Run layout audit via `browser_evaluate`:
     ```js
     (() => {
       const hasOverflow = document.documentElement.scrollWidth > window.innerWidth;
       const brokenImages = Array.from(document.querySelectorAll('img')).filter(i => !i.complete || i.naturalWidth === 0).length;
       return { hasOverflow, brokenImages, title: document.title };
     })()
     ```
3. **Commit & Report**: Only present the working URL and validated components to the user.
