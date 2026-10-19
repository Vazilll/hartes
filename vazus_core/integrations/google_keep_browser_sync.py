"""
vazus_core.integrations.google_keep_browser_sync
================================================
Browser-driven Google Keep to Obsidian Vault sync engine via Playwright.
Bypasses unofficial API blocks by interacting with keep.google.com directly
using user's persistent Chrome profile or CDP debugging session.
"""

import sys
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

INBOX_PATH = Path("/home/tarhes/Проекты/vazus/services/memory/semantic/wiki/inbox")
PROFILE_PATH = Path("C:/Users/Vaz/AppData/Local/Google/Chrome/User Data")
FALLBACK_PROFILE = Path("C:/Users/Vaz/.vazus_keep_browser_profile")


class GoogleKeepBrowserSync:
    """
    Automates extraction of notes from keep.google.com via Playwright.
    """

    def __init__(self, inbox_dir: Path = INBOX_PATH):
        self.inbox_dir = Path(inbox_dir)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def extract_notes_from_html(self, cards_data: List[Dict[str, Any]]) -> int:
        """
        Saves extracted card JSONs into Obsidian Inbox as atomic Markdown files.
        """
        count = 0
        now_str = datetime.datetime.now().strftime("%Y-%m-%d")
        for card in cards_data:
            title = card.get("title", "").strip() or f"Keep_Note_{int(time.time())}"
            content = card.get("content", "").strip()
            checklist = card.get("checklist", [])
            card_id = card.get("id", str(abs(hash(title + content)) % 1000000))

            safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).rstrip()[:50]
            if not safe_title:
                safe_title = f"keep_{card_id}"
            filename = f"{now_str}_{safe_title}.md"
            file_path = self.inbox_dir / filename

            body_lines = [
                "---",
                "source: google_keep",
                f"date: {now_str}",
                f"keep_id: {card_id}",
                "status: inbox",
                "tags:",
                "  - inbox",
                "  - mobile_thought",
                "---",
                "",
                f"# {title}",
                "",
                content,
                ""
            ]

            if checklist:
                body_lines.append("### Чек-лист:")
                for item in checklist:
                    checked = "x" if item.get("checked") else " "
                    text = item.get("text", "")
                    body_lines.append(f"- [{checked}] {text}")
                body_lines.append("")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(body_lines))
            count += 1

        return count

    async def sync_via_cdp(self, cdp_url: str = "http://localhost:9222") -> Dict[str, Any]:
        """Connects over CDP to an already-open Chrome browser."""
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            try:
                browser = await p.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                if not contexts:
                    return {"status": "error", "message": "No browser contexts found on CDP"}
                context = contexts[0]
                page = await context.new_page()
                await page.goto("https://keep.google.com", timeout=30000)
                await page.wait_for_selector(".IZ65Hb-n0tgbe, [role='dialog']", timeout=10000)
                cards = await self._scrape_keep_page(page)
                saved_count = self.extract_notes_from_html(cards)
                await page.close()
                return {"status": "ok", "synced_notes": saved_count}
            except Exception as e:
                return {"status": "error", "error": str(e)}

    async def _scrape_keep_page(self, page) -> List[Dict[str, Any]]:
        """Scrapes text and checklist notes from active Keep page."""
        js_code = """
        () => {
            const notes = [];
            // Target note card containers in Google Keep
            const cards = document.querySelectorAll('div.IZ65Hb-n0tgbe, div[role="dialog"]');
            cards.forEach((card, idx) => {
                const titleEl = card.querySelector('.IZ65Hb-YPqjbf, .editable[aria-label="Title"]');
                const contentEl = card.querySelector('.IZ65Hb-haAclf, .editable[aria-label="Note"]');
                const title = titleEl ? titleEl.innerText : '';
                const content = contentEl ? contentEl.innerText : '';
                const checklist = [];
                card.querySelectorAll('.gkA7Yd-sKfxWe, div.L1CIof').forEach(item => {
                    const text = item.innerText || '';
                    const isChecked = item.classList.contains('Q0vbed') || item.innerHTML.includes('checked');
                    if (text) checklist.push({ text: text, checked: isChecked });
                });
                if (title || content || checklist.length > 0) {
                    notes.push({
                        id: card.getAttribute('data-id') || String(idx),
                        title: title,
                        content: content,
                        checklist: checklist
                    });
                }
            });
            return notes;
        }
        """
        return await page.evaluate(js_code)


if __name__ == "__main__":
    sync = GoogleKeepBrowserSync()
    print("GoogleKeepBrowserSync initialized for path:", sync.inbox_dir)
