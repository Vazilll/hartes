# Native Google Multimodal Image Protocol (Google ai.google.dev Standards)

## Core Architectural Principles (First Principles)
1. **Google Native Multimodal Function Calling (`ai.google.dev` Specification)**:
   - Images and visual assets MUST be ingested natively via Gemini's visual token attention layers.
   - Text reading tools (`view_file`) must return `TextContent` for source code/documents. For visual files, tool responses MUST follow Google's official `functionResponse` specification returning `inlineData` (Base64) or `fileData` (Google Files API).

2. **Polymorphic Tool Execution Protocol**:
   - **Files < 20MB**: Handled via `inlineData` with `mimeType` (`image/png`, `image/jpeg`, etc.) and Base64 encoded payload.
   - **Files > 20MB or Persistent Media**: Handled via Google Files API (`fileData` with `fileUri`).
   - **Screenshots & Web Testing**: Handled natively via Playwright MCP (`browser_take_screenshot`) or direct multimodal UI attachments.

3. **No Intermediate Workarounds**:
   - Eliminate legacy OCR/text-wrapper workarounds. Gemini 3.6 Flash natively processes pixel tokens directly within its self-attention layers with maximum fidelity and zero conversion loss.
