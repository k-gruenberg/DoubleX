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
attacker-controllable site).
However, multiple patterns however can mean "all websites" (more or less) and these are listed here.
"""
INJECTED_EVERYWHERE_PATTERNS = {
    "*://*/*",
    "http://*/*",
    "https://*/*",
    "<all_urls>",
    "file:///*",
}  # TODO?: add missing patterns?
