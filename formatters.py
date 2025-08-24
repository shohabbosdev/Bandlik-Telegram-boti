from typing import Dict, List, Any
from config import REQUIRED_STATUS
from utils import escape_md

def _status_icon(status_text: str) -> str:
    return "🟢" if REQUIRED_STATUS.lower() in (status_text or "").lower() else "🔴"

def format_card(item: Dict[str, Any]) -> str:
    """Bitta foydalanuvchi kartasi (Markdown)."""
    icon = _status_icon(item.get("status", ""))
    fakultet = escape_md(item.get("fakultet", "Nomaʼlum"))
    mutaxassislik = escape_md(item.get("mutaxassislik", "Nomaʼlum"))
    guruh = escape_md(item.get("guruh", "Nomaʼlum"))
    fio      = escape_md(item.get("fio", "Nomaʼlum"))
    hemisuid = escape_md(item.get("hemisuid", ""))
    hemis    = escape_md(item.get("hemis", ""))
    jsh      = escape_md(item.get("jshshir", ""))
    status   = escape_md(item.get("status", ""))

    lines = [
        f"🏷 Fakultet: `{fakultet}`",
        f"🎓 Mutaxassislik: `{mutaxassislik}`",
        f"👤 *{fio}*",
        f"👥 Guruh: `{guruh}`",
        f"🆔 HEMIS UID: `{hemisuid}`",
        f"💼 HEMIS ID: `{hemis}`",
        f"🔑 JSHSHIR: `{jsh}`",
        f"{icon} {status}",
    ]

    if REQUIRED_STATUS.lower() in (item.get("status","") or "").lower():
        lavozim   = escape_md(item.get("lavozim", "-"))
        tashkilot = escape_md(item.get("tashkilot", "-"))
        sanasi    = escape_md(item.get("sanasi", "-"))
        lines.append("")
        lines.append("🏢 *Ish joyi haqida ma'lumot:*")
        lines.append(f"   • Lavozimi: _{lavozim}_")
        lines.append(f"   • Tashkilot: _{tashkilot}_")
        lines.append(f"   • Ishga kirgan sana: _{sanasi}_")

    return "\n".join(lines)

def format_results_block(items: List[Dict[str, Any]]) -> str:
    """Bir sahifadagi natijalarni bloklar bilan birlashtiradi."""
    blocks = []
    for i, it in enumerate(items, start=1):
        blocks.append(f"──────── {i} ────────\n{format_card(it)}")
    return "\n\n".join(blocks)
