IBM_Z_DISCLAIMER = (
    "This information is sourced from the linux-on-ibm-z community documentation "
    "and build guides. Always verify build steps against the latest official documentation "
    "for your specific distribution and version."
)


def add_disclaimer(results: list[dict]) -> list[dict]:
    if results:
        results.append({"disclaimer": IBM_Z_DISCLAIMER})
    return results
