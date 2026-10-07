def classify_claim(status, evidence_present):
    if status == "contradicted":
        return "contradicted"
    if status == "verified":
        return "verified"
    return "unresolved"
