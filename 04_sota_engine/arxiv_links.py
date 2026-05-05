"""Pure string helpers for arXiv URLs (no `arxiv` package, no network)."""


def abs_url_from_pdf_url(pdf_url: str) -> str:
    """
    Map https://arxiv.org/pdf/XXXX.pdf to https://arxiv.org/abs/XXXX.
    Version suffixes (v1, v2) are preserved on the abs URL.
    """
    u = (pdf_url or "").strip()
    if "arxiv.org/pdf/" not in u:
        return ""
    tail = u.split("arxiv.org/pdf/", 1)[1].split("?")[0].split("#")[0]
    if tail.lower().endswith(".pdf"):
        tail = tail[:-4]
    return f"https://arxiv.org/abs/{tail}" if tail else ""
