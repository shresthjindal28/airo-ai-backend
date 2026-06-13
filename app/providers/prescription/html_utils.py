import re


def strip_markdown_fences(text: str) -> str:
    cleaned = text.strip()
    fenced = re.search(r"```(?:html)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.I)
    if fenced:
        return fenced.group(1).strip()
    return cleaned


def extract_html_document(text: str) -> str:
    cleaned = strip_markdown_fences(text)
    start = cleaned.lower().find("<")
    end = cleaned.lower().rfind(">")
    if start == -1 or end == -1:
        raise ValueError("Model response did not contain HTML")
    return sanitize_prescription_layout(cleaned[start : end + 1])


_LAYOUT_STYLE_PATTERN = re.compile(
    r"(?<![\w-])(?:max-width|min-width|width|margin(?:-left|-right|-top|-bottom)?|left|right|top|bottom|transform|position)\s*:\s*[^;\"']+;?",
    re.IGNORECASE,
)
_CENTERING_MARGIN_PATTERN = re.compile(
    r"\bmargin\s*:\s*(?:\d+px\s+)?auto\b[^;\"']*",
    re.IGNORECASE,
)


def sanitize_prescription_layout(html: str) -> str:
    """Strip layout-breaking inline styles the model sometimes adds."""
    cleaned = _unwrap_body_content(html)
    cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)

    def _clean_style_attr(match: re.Match[str]) -> str:
        quote = match.group(1)
        style_value = match.group(2)
        cleaned_style = _LAYOUT_STYLE_PATTERN.sub("", style_value)
        cleaned_style = _CENTERING_MARGIN_PATTERN.sub("", cleaned_style)
        cleaned_style = re.sub(r";{2,}", ";", cleaned_style).strip(" ;")
        return f" style={quote}{cleaned_style}{quote}" if cleaned_style else ""

    cleaned = re.sub(
        r'\sstyle=(["\'])(.*?)\1',
        _clean_style_attr,
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    cleaned = re.sub(
        r"<(html|head|body)[^>]*>|</(html|head|body)>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"<!DOCTYPE[^>]*>", "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def _unwrap_body_content(html: str) -> str:
    body_match = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, re.IGNORECASE)
    if body_match:
        return body_match.group(1).strip()
    return html.strip()


def html_to_plain_text(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"</tr>", "\n", text, flags=re.I)
    text = re.sub(r"</t[dh]>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_fallback_prescription_html(context) -> str:
    ctx = context
    return f"""<div class="prescription">
  <header>
    <h1>{ctx.hospital_name or "AIRO Clinical"}</h1>
    <h2>Medical Prescription</h2>
  </header>
  <section class="patient-details">
    <p><strong>Patient:</strong> {ctx.patient_name}</p>
    <p><strong>Age:</strong> {ctx.patient_age}</p>
    <p><strong>Gender:</strong> {ctx.patient_gender}</p>
    <p><strong>Date:</strong> {ctx.consultation_date}</p>
  </section>
  <section class="diagnosis">
    <h3>Diagnosis</h3>
    <p>{ctx.assessment or "See clinical assessment."}</p>
  </section>
  <section class="medications">
    <h3>Medications</h3>
    <table>
      <thead>
        <tr><th>Medicine</th><th>Dosage</th><th>Frequency</th><th>Duration</th></tr>
      </thead>
      <tbody>
        <tr><td colspan="4">Refer to plan section for medication details.</td></tr>
      </tbody>
    </table>
    <p>{ctx.plan}</p>
  </section>
  <section class="instructions">
    <h3>Instructions</h3>
    <p>{ctx.plan or "Follow treating physician guidance."}</p>
  </section>
  <section class="warnings">
    <h3>Warnings</h3>
    <p>Take medications only as prescribed. Seek immediate care for worsening symptoms.</p>
  </section>
  <section class="follow-up">
    <h3>Follow-up</h3>
    <p>As advised during consultation.</p>
  </section>
  <footer class="signature">
    <p><strong>Doctor:</strong> {ctx.doctor_name}</p>
    <p><strong>Registration No:</strong> {ctx.doctor_registration or "—"}</p>
    <p><strong>Signature:</strong> _______________________</p>
  </footer>
</div>"""
