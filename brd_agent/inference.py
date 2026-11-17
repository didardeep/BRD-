"""
inference.py -- derives all 16 detail fields from the 11 core question
answers using rule-based Python: keyword routing, regex extraction, and
deterministic sentence splitting.

No ML models, no API calls, no training data.  Improving the derivation
means editing the KEYWORD_BANKS below.

Usage:
    from brd_agent.inference import infer_details
    detail = infer_details(answers)
"""

import re


# Leading list marker ("- ", "* ", "• ") -- but not the "**bold**" /
# "*italic*" markers typed with the formatting toolbar.
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-•]+\s*|\*\s+)")


def _strip_bullet(text):
    return _LIST_MARKER_RE.sub("", text).strip()


# --------------------------------------------------------------------------
# Keyword banks: each detail field has a list of keywords / phrases.
# Sentences containing more matches score higher for that field.
# --------------------------------------------------------------------------

KEYWORD_BANKS = {
    # --- derived from q_tech ---
    "d_if_hardware": [
        "server", "device", "desktop", "laptop", "tablet", "mobile",
        "phone", "scanner", "printer", "barcode", "on-prem", "on-premise",
        "appliance", "rack", "workstation", "kiosk", "terminal",
        "hardware", "machine", "peripheral", "biometric", "reader",
    ],
    "d_if_data": [
        "data", "format", "csv", "xml", "json", "excel", "xls", "xlsx",
        "pdf", "file", "sftp", "ftp", "transfer", "etl", "pipeline",
        "batch", "real-time", "streaming", "parquet", "api",
        "encryption", "aes", "tls", "ssl", "encoding", "schema",
        "database", "export", "import", "migration",
    ],
    "d_if_comm": [
        "email", "smtp", "imap", "https", "http", "protocol", "network",
        "tcp", "udp", "websocket", "rest", "soap", "grpc", "mqtt",
        "notification", "alert", "sms", "messaging", "webhook",
        "communication", "vpn", "firewall", "proxy", "dns",
        "teams", "slack", "chat",
    ],

    # --- derived from q_security ---
    "d_if_security": [
        "authenticate", "authentication", "sso", "single sign-on", "saml",
        "oauth", "oidc", "mfa", "multi-factor", "two-factor", "2fa",
        "token", "jwt", "certificate", "ldap", "active directory",
        "azure ad", "entra", "login", "password", "credential",
        "authorization", "rbac", "role-based", "acl", "permission",
    ],
    "d_security_nfr": [
        "audit", "trail", "log", "logging", "retention", "residency",
        "data residency", "encryption at rest", "in transit", "compliance",
        "gdpr", "dpdp", "pci", "hipaa", "sox", "iso 27001",
        "penetration", "vulnerability", "scan", "privilege", "elevated",
        "separation of duties", "segregation",
    ],

    # --- derived from q_nonfunc ---
    "d_performance": [
        "response time", "latency", "throughput", "page load", "batch",
        "sla", "seconds", "millisecond", "ms", "tps", "transactions per",
        "api response", "query time", "processing time", "performance",
        "fast", "speed", "benchmark",
    ],
    "d_availability": [
        "uptime", "availability", "downtime", "disaster recovery", "dr",
        "rto", "rpo", "backup", "failover", "ha", "high availability",
        "business continuity", "bcp", "maintenance window",
        "redundancy", "replication", "retention",
    ],
    "d_scalability": [
        "scale", "scalability", "concurrent", "concurrency", "users",
        "volume", "growth", "peak", "load", "capacity", "horizontal",
        "vertical", "elastic", "auto-scale", "records per", "transactions",
        "million", "thousand", "daily", "monthly",
    ],

    # --- derived from q_problem ---
    "d_challenges": [
        "challenge", "problem", "issue", "pain", "bottleneck", "delay",
        "error", "rework", "manual", "inefficient", "gap", "risk",
        "limitation", "dependency", "slow", "inconsistent", "missing",
        "duplication", "lack", "no audit", "no trail",
    ],

    # --- derived from q_objective ---
    "d_to_be": [
        "after go-live", "future", "automated", "to-be", "target state",
        "new process", "will be", "should be", "expected", "improved",
        "streamlined", "replaced", "eliminated", "enabled",
    ],
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _split_sentences(text):
    """Split text into sentences.  Newlines are treated as boundaries."""
    if not text or not text.strip():
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sentences = []
    for line in lines:
        parts = re.split(r'(?<=[.!?])\s+', line)
        for part in parts:
            cleaned = _strip_bullet(part)
            if cleaned:
                sentences.append(cleaned)
    return sentences


def _score(sentence, keywords):
    """Count keyword hits in a sentence (case-insensitive)."""
    lower = sentence.lower()
    return sum(1 for kw in keywords if kw in lower)


def _route(sentences, field_keywords, threshold=1):
    """Route each sentence to the best-matching detail field."""
    result = {f: [] for f in field_keywords}
    for sent in sentences:
        scores = {f: _score(sent, kws) for f, kws in field_keywords.items()}
        best = max(scores, key=scores.get)
        if scores[best] >= threshold:
            result[best].append(sent)
    return result


def _join(parts):
    return "\n".join(parts) if parts else ""


# --------------------------------------------------------------------------
# Per-source derivation
# --------------------------------------------------------------------------

def _from_tech(q_tech):
    sents = _split_sentences(q_tech)
    routed = _route(sents, {
        "d_if_hardware": KEYWORD_BANKS["d_if_hardware"],
        "d_if_data":     KEYWORD_BANKS["d_if_data"],
        "d_if_comm":     KEYWORD_BANKS["d_if_comm"],
    })
    return {f: _join(s) for f, s in routed.items()}


def _from_security(q_security):
    sents = _split_sentences(q_security)
    routed = _route(sents, {
        "d_if_security": KEYWORD_BANKS["d_if_security"],
        "d_security_nfr": KEYWORD_BANKS["d_security_nfr"],
    })
    # fallback: if nothing matched, put it all in d_if_security
    if not routed["d_if_security"] and not routed["d_security_nfr"]:
        return {"d_if_security": q_security.strip(), "d_security_nfr": ""}
    return {f: _join(s) for f, s in routed.items()}


def _from_nonfunc(q_nonfunc):
    sents = _split_sentences(q_nonfunc)
    routed = _route(sents, {
        "d_performance":  KEYWORD_BANKS["d_performance"],
        "d_availability": KEYWORD_BANKS["d_availability"],
        "d_scalability":  KEYWORD_BANKS["d_scalability"],
    })
    return {f: _join(s) for f, s in routed.items()}


def _derive_challenges(q_problem):
    sents = _split_sentences(q_problem)
    kws = KEYWORD_BANKS["d_challenges"]
    hits = [s for s in sents if _score(s, kws) >= 1]
    return _join(hits) if hits else q_problem.strip()


def _derive_to_be(q_objective):
    sents = _split_sentences(q_objective)
    kws = KEYWORD_BANKS["d_to_be"]
    hits = [s for s in sents if _score(s, kws) >= 1]
    return _join(hits) if hits else q_objective.strip()


def _derive_proposed(q_features, q_objective):
    parts = []
    if q_objective and q_objective.strip():
        first_line = q_objective.strip().splitlines()[0]
        parts.append(f"The proposed solution aims to: {first_line}")
    if q_features and q_features.strip():
        feats = [_strip_bullet(ln) for ln in q_features.splitlines()
                 if ln.strip()][:5]
        if feats:
            parts.append("Key capabilities include: " + "; ".join(feats) + ".")
    return "\n".join(parts)


def _derive_if_software(q_systems):
    systems = [_strip_bullet(ln) for ln in (q_systems or "").splitlines()
               if ln.strip()]
    if not systems:
        return ""
    return ("The solution interfaces with the following software systems: "
            + ", ".join(systems)
            + ". Component versions, databases and libraries are to be "
            "confirmed with client IT.")


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------

def infer_details(answers):
    """Derive all 16 detail fields from the 11 core question answers.

    Returns a dict keyed by d_* field names.  Empty strings for fields
    that cannot be derived (d_prototype).
    Deterministic, no side effects.
    """
    a = {k: (v or "").strip() for k, v in (answers or {}).items()}
    result = {}

    # From q_tech
    if a.get("q_tech"):
        result.update(_from_tech(a["q_tech"]))
    else:
        result.update({"d_if_hardware": "", "d_if_data": "", "d_if_comm": ""})

    # From q_security (legacy) + q_regs + q_tech + q_nonfunc
    sec_parts = [a.get("q_security", ""), a.get("q_regs", ""),
                 a.get("q_tech", ""), a.get("q_nonfunc", "")]
    sec_combined = "\n".join(p for p in sec_parts if p)
    if sec_combined.strip():
        result.update(_from_security(sec_combined))
    else:
        result.update({"d_if_security": "", "d_security_nfr": ""})

    # From q_nonfunc
    if a.get("q_nonfunc"):
        result.update(_from_nonfunc(a["q_nonfunc"]))
    else:
        result.update({"d_performance": "", "d_availability": "",
                       "d_scalability": ""})

    # From q_problem
    result["d_challenges"] = (
        _derive_challenges(a["q_problem"]) if a.get("q_problem") else "")

    # From q_objective
    result["d_to_be"] = (
        _derive_to_be(a["q_objective"]) if a.get("q_objective") else "")

    # From q_features + q_objective
    result["d_proposed"] = _derive_proposed(
        a.get("q_features", ""), a.get("q_objective", ""))

    # From q_systems
    result["d_if_software"] = _derive_if_software(a.get("q_systems", ""))

    # Not derivable
    result["d_prototype"] = ""

    return result
