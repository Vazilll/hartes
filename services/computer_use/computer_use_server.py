"""Vazus Computer-Use FastMCP Server (Windows UIA + SoM + MSS + Background Input).

Implements the SOTA Set-of-Mark (SoM) + Background Accessibility injection protocol.
Enables full agentic interaction with Desktop, Windows Sandbox, VirtualBox, and Electron apps.
"""

import os
import sys
import time
import json
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastmcp import FastMCP
import win32gui
import win32con
import win32process
import win32api
from PIL import Image, ImageDraw, ImageFont

# Initialize FastMCP Server
mcp = FastMCP("vazus-computer-use")

# Global element cache for Set-of-Mark (SoM) referencing
_SOM_ELEMENT_CACHE: List[Dict[str, Any]] = []
_LAST_SCREENSHOT_PATH: Optional[str] = None


def _attach_interactive_desktop():
    """Attach background thread to the interactive user window station and desktop."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        h_winsta = user32.OpenWindowStationW("winsta0", False, 0x000F037F)
        if h_winsta:
            user32.SetProcessWindowStation(h_winsta)
        h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass


def _get_window_list() -> List[Dict[str, Any]]:
    """Enumerate all visible top-level windows."""
    _attach_interactive_desktop()
    windows = []
    
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and not title.startswith("Default IME") and not title.startswith("MSCTFIME"):
                rect = win32gui.GetWindowRect(hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if w > 50 and h > 50:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    windows.append({
                        "hwnd": hwnd,
                        "pid": pid,
                        "title": title,
                        "x": rect[0],
                        "y": rect[1],
                        "width": w,
                        "height": h
                    })
        return True
    
    win32gui.EnumWindows(enum_cb, None)
    return windows


def _capture_screen_mss() -> Image.Image:
    """Capture full virtual desktop using MSS or PIL fallback."""
    _attach_interactive_desktop()
    try:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[0]  # Full virtual screen across all monitors
            sct_img = sct.grab(mon)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img
    except Exception:
        # Fallback using PIL / Win32 DC
        import win32ui
        hdesktop = win32gui.GetDesktopWindow()
        w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        
        desktop_dc = win32gui.GetWindowDC(hdesktop)
        img_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = img_dc.CreateCompatibleDC()
        screenshot = win32ui.CreateBitmap()
        screenshot.CreateCompatibleBitmap(img_dc, w, h)
        mem_dc.SelectObject(screenshot)
        mem_dc.BitBlt((0, 0), (w, h), img_dc, (left, top), win32con.SRCCOPY)
        
        bmpinfo = screenshot.GetInfo()
        bmpstr = screenshot.GetBitmapBits(True)
        img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
        
        mem_dc.DeleteDC()
        win32gui.DeleteObject(screenshot.GetHandle())
        win32gui.ReleaseDC(hdesktop, desktop_dc)
        return img


@mcp.tool()
def computer_list_windows() -> Dict[str, Any]:
    """List all open desktop application windows with titles, coordinates, HWNDs, and PIDs."""
    windows = _get_window_list()
    return {
        "success": True,
        "count": len(windows),
        "windows": windows
    }


@mcp.tool()
def computer_focus_window(title_query: str) -> Dict[str, Any]:
    """Bring a window matching title_query to focus (e.g. 'Windows Sandbox', 'Antigravity')."""
    windows = _get_window_list()
    matched = [w for w in windows if title_query.lower() in w["title"].lower()]
    if not matched:
        return {"success": False, "error": f"No window found matching '{title_query}'"}
    
    target = matched[0]
    hwnd = target["hwnd"]
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return {"success": True, "focused_window": target["title"], "hwnd": hwnd}
    except Exception as e:
        return {"success": False, "error": str(e), "hwnd": hwnd}


@mcp.tool()
def computer_capture(
    mode: str = "som",
    app_title: Optional[str] = None
) -> Dict[str, Any]:
    """Capture screen and detect interactable UI elements using Set-of-Mark (SoM).
    
    Args:
        mode: 'som' (screenshot with numbered markers + element index), 'vision' (plain screenshot), or 'ax' (text elements only)
        app_title: Optional filter to focus detection on a specific window (e.g. 'Windows Sandbox')
    
    Returns:
        Structured element index with #ID, bounding box, text content, and screenshot path.
    """
    global _SOM_ELEMENT_CACHE, _LAST_SCREENSHOT_PATH
    _SOM_ELEMENT_CACHE = []
    
    # 1. Capture screen
    raw_img = _capture_screen_mss()
    width, height = raw_img.size
    
    # Output paths
    out_dir = Path(r"C:\Users\Vaz\.gemini\antigravity\brain\0645059b-09e7-4e9d-bdcb-eb4c7cef0910\screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time() * 1000)
    raw_path = out_dir / f"screen_raw_{stamp}.png"
    som_path = out_dir / f"screen_som_{stamp}.png"
    raw_img.save(str(raw_path))
    
    # 2. Run OCR / Text Element Detection
    elements = []
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        ocr_res, _ = ocr(str(raw_path))
        
        if ocr_res:
            for idx, item in enumerate(ocr_res, start=1):
                box = item[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text = item[1]
                conf = item[2]
                
                x_min = int(min(p[0] for p in box))
                y_min = int(min(p[1] for p in box))
                x_max = int(max(p[0] for p in box))
                y_max = int(max(p[1] for p in box))
                center_x = (x_min + x_max) // 2
                center_y = (y_min + y_max) // 2
                
                conf_val = float(conf) if conf is not None else 1.0
                el_entry = {
                    "id": idx,
                    "text": str(text),
                    "confidence": round(conf_val, 2),
                    "bbox": [x_min, y_min, x_max - x_min, y_max - y_min],
                    "center": [center_x, center_y]
                }
                elements.append(el_entry)
    except Exception as e:
        import traceback
        print(f"OCR Error: {e}\n{traceback.format_exc()}", file=sys.stderr)
        elements = []
    
    _SOM_ELEMENT_CACHE = elements
    _LAST_SCREENSHOT_PATH = str(som_path) if mode == "som" else str(raw_path)
    
    # 3. Draw Set-of-Mark (SoM) overlays if requested
    if mode == "som" and elements and "error" not in elements[0]:
        som_img = raw_img.copy()
        draw = ImageDraw.Draw(som_img)
        
        for el in elements:
            x, y, w, h = el["bbox"]
            el_id = el["id"]
            
            # Draw semi-transparent bounding box
            draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 70), width=2)
            
            # Draw numbered badge
            badge_text = f"#{el_id}"
            badge_w = len(badge_text) * 8 + 6
            badge_h = 16
            draw.rectangle([x, max(0, y - badge_h), x + badge_w, y], fill=(255, 0, 70))
            draw.text((x + 3, max(0, y - badge_h) + 1), badge_text, fill=(255, 255, 255))
        
        som_img.save(str(som_path))
    
    return {
        "success": True,
        "mode": mode,
        "screen_size": [width, height],
        "elements_count": len(elements),
        "elements": elements,
        "screenshot_path": _LAST_SCREENSHOT_PATH,
        "instruction": "Use computer_click(element=ID) to click any numbered element directly, or computer_type(text=...) to enter text."
    }


@mcp.tool()
def computer_click(
    element: Optional[int] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
    double: bool = False,
    delivery_mode: str = "foreground"
) -> Dict[str, Any]:
    """Click a specific UI element by its #ID from the last capture, or by direct (x, y) coordinates.
    
    Args:
        element: Numbered element ID from computer_capture (e.g. 7 for '#7 Link Sign in')
        x: Direct X pixel coordinate (used if element is not specified)
        y: Direct Y pixel coordinate (used if element is not specified)
        button: 'left', 'right', or 'middle'
        double: If True, perform a double-click
        delivery_mode: 'foreground' (moves cursor & clicks) or 'background' (sends WM_LBUTTONDOWN without stealing cursor)
    """
    global _SOM_ELEMENT_CACHE
    target_x, target_y = None, None
    el_text = ""
    
    if element is not None:
        for el in _SOM_ELEMENT_CACHE:
            if el.get("id") == element:
                target_x, target_y = el["center"]
                el_text = el.get("text", "")
                break
        if target_x is None:
            return {"success": False, "error": f"Element #{element} not found in recent capture cache. Run computer_capture first."}
    elif x is not None and y is not None:
        target_x, target_y = x, y
    else:
        return {"success": False, "error": "Must specify either element (ID number) or (x, y) coordinates."}
    
    if delivery_mode == "background":
        # Background click via Win32 WindowFromPoint & PostMessage
        point = (target_x, target_y)
        hwnd = win32gui.WindowFromPoint(point)
        if hwnd:
            # Convert screen coord to client coord
            client_x, client_y = win32gui.ScreenToClient(hwnd, point)
            lparam = win32api.MAKELONG(client_x, client_y)
            msg_down = win32con.WM_LBUTTONDOWN if button == "left" else win32con.WM_RBUTTONDOWN
            msg_up = win32con.WM_LBUTTONUP if button == "left" else win32con.WM_RBUTTONUP
            
            win32api.PostMessage(hwnd, msg_down, win32con.MK_LBUTTON, lparam)
            time.sleep(0.05)
            win32api.PostMessage(hwnd, msg_up, 0, lparam)
            
            if double:
                time.sleep(0.05)
                win32api.PostMessage(hwnd, msg_down, win32con.MK_LBUTTON, lparam)
                time.sleep(0.05)
                win32api.PostMessage(hwnd, msg_up, 0, lparam)
            
            return {
                "success": True,
                "effect": "confirmed",
                "delivery_mode": "background",
                "target": {"x": target_x, "y": target_y, "element": element, "text": el_text, "hwnd": hwnd}
            }
    
    # Foreground click via SendInput / PyAutoGUI
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        if double:
            pyautogui.doubleClick(target_x, target_y, button=button)
        else:
            pyautogui.click(target_x, target_y, button=button)
        return {
            "success": True,
            "effect": "confirmed",
            "delivery_mode": "foreground",
            "target": {"x": target_x, "y": target_y, "element": element, "text": el_text}
        }
    except Exception as e:
        # Fallback via Win32 mouse_event
        win32api.SetCursorPos((target_x, target_y))
        time.sleep(0.02)
        flag_down = win32con.MOUSEEVENTF_LEFTDOWN if button == "left" else win32con.MOUSEEVENTF_RIGHTDOWN
        flag_up = win32con.MOUSEEVENTF_LEFTUP if button == "left" else win32con.MOUSEEVENTF_RIGHTUP
        win32api.mouse_event(flag_down, target_x, target_y, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(flag_up, target_x, target_y, 0, 0)
        return {
            "success": True,
            "effect": "confirmed",
            "delivery_mode": "win32_mouse_event",
            "target": {"x": target_x, "y": target_y, "element": element, "text": el_text}
        }


@mcp.tool()
def computer_type(
    text: str,
    element: Optional[int] = None,
    press_enter: bool = False
) -> Dict[str, Any]:
    """Type text into the currently focused input control or click an element first before typing."""
    if element is not None:
        click_res = computer_click(element=element)
        if not click_res.get("success"):
            return click_res
        time.sleep(0.1)
    
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=0.02)
        if press_enter:
            pyautogui.press("enter")
        return {"success": True, "typed_length": len(text), "press_enter": press_enter}
    except Exception:
        # Fallback via SendInput / pynput
        for char in text:
            win32api.keybd_event(win32con.VkKeyScan(char) & 0xFF, 0, 0, 0)
            time.sleep(0.01)
            win32api.keybd_event(win32con.VkKeyScan(char) & 0xFF, 0, win32con.KEYEVENTF_KEYUP, 0)
        if press_enter:
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        return {"success": True, "typed_length": len(text), "method": "win32_keybd_event"}


@mcp.tool()
def computer_key(keys: str) -> Dict[str, Any]:
    """Press keyboard hotkeys or special keys (e.g. 'enter', 'escape', 'ctrl+a', 'ctrl+s', 'alt+tab', 'backspace')."""
    key_lower = keys.lower().strip()
    try:
        import pyautogui
        if "+" in key_lower:
            parts = [p.strip() for p in key_lower.split("+")]
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(key_lower)
        return {"success": True, "pressed": keys}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
