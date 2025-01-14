"""
Each content script specified in the manifest.json is injected into those sites only whose URL matches one of the
listed "matches"; e.g.:

  "content_scripts": [
    {
      "matches": [
        "<all_urls>"
      ],
      "js": [
        "bubble_compiled.js"
      ],
      "css": [
        "bubble_gss.css"
      ],
      "all_frames": true
    }
  ],

Unless yet another vulnerability is present, the vulnerabilities that our tool finds will only be exploitable by an
arbitrary web attacker if at least one content script is injected into all websites (and therefore also into an
attacker-controllable site), or at least into all websites matching a certain pattern which an attacker's site (from
the attacker's origin) can easily match.
All sorts of such "vulnerable" URL patterns are listed below (no claim to completeness).
There are verbatim, prefix and regex patterns (see below).
"""

import re

# URLs matching these verbatim URL patterns are potentially attacker-controlled:
INJECTED_EVERYWHERE_LITERAL_PATTERNS = {
    "<all_urls>",
    "file:///*",
    "file://*",
    "file:///*/*",
    "file://*/*",
}
# Note: We consider "file:" URLs to be attacker-controllable as well (and not just http/https URLs).
#       Instead of a link to click, the attacker has to send the victim an HTML file to open.

# All URL patterns beginning with any of these prefixes can match attacker-controlled URLs:
INJECTED_EVERYWHERE_PATTERN_PREFIXES = {
    "*://*/",  # catches "*://*/*" as well
    "http://*/",
    "https://*/",
}
# No matter what comes after the last slash of these prefixes, an attacker can always create a URL matching the
#   pattern under his own origin "attacker.org"!
# Note: We cannot list "file:///*" here because "file://*/*.text" for example isn't actually exploitable!!!
#       "https://*/*.text" however CAN be exploitable, as long as the attacker's server sends the correct
#         Content-Type response header ("text/html")! :)

# All URL patterns matching any of these regular expressions can match attacker-controlled URLs:
INJECTED_EVERYWHERE_REGEX_PATTERNS = {
    # URL patterns matching a local HTML file (with suffix ".html") whose file name (before ".html") we can control;
    # the file path/location must however not be restricted by the pattern (we would deem this to difficult to exploit):
    # Example: file://*/*.pdf*
    # Pattern: - Pattern begins with "file://*", "file:///*", "file://*/", "file:///*/", "file://*/*" or "file:///*/*".
    #          - Pattern may continue with alphanumerical characters or further wildcards "*" but NO(!) slashes "/" !!!
    #          - Pattern ends with either a wildcard "*", ".html" or ".htm"
    r"file:///?\*(|/|/*)[^/]*(\*|\.html?)",
}


def is_an_injected_everywhere_url_pattern(url_pattern: str) -> bool:
    return (
            url_pattern in INJECTED_EVERYWHERE_LITERAL_PATTERNS
            or
            any(url_pattern.startswith(pattern_prefix)
                for pattern_prefix in INJECTED_EVERYWHERE_PATTERN_PREFIXES)
            or
            any(re.fullmatch(pattern=regex_pattern, string=url_pattern)
                for regex_pattern in INJECTED_EVERYWHERE_REGEX_PATTERNS)
            )
