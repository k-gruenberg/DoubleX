import unittest

from INJECTED_EVERYWHERE_PATTERNS import is_an_injected_everywhere_url_pattern


class TestInjectedEverywherePatterns(unittest.TestCase):
    def test_is_an_injected_everywhere_url_pattern(self):
        # Positive examples (the most common, basic cases of attacker-exploitable URL patterns):
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("http://*/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("https://*/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("<all_urls>"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file:///*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file:///*/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*"))
        # Note: We consider "file:" URLs to be attacker-controllable as well.
        #       Instead of a link to click, the attacker has to send the victim an HTML file to open.

        # Positive examples (more complex cases of attacker-exploitable URL patterns from real-world extensions!):
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.pdf*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*.pdf*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/owa/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*.*md*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*.*MD*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*.markdown*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*.mdown*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*.txt*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*.mkd*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("file://*/*.rst*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.*md*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.*MD*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.markdown*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.mdown*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.txt*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.mkd*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.rst*"))

        # Some further, hypothetically possible, positive examples:
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/foo/*/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*/foo/*/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/foo/bar/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/foo/bar/baz/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/foo/*/baz/*"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/foobar.html"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/baz/foobar.html"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.html"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("*://*/*.text"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("http://*/*.text"))
        self.assertTrue(is_an_injected_everywhere_url_pattern("https://*/*.text"))
        # Note that, unlike file:// URLs, *://, http:// and https:// URLs may end in ".text", as here the attacker's
        #   web server simply has to send the correct Content-Type response header! :)

        # ----- ----- ----- ----- -----

        # Negative examples (more obvious ones where the origin is fixed):
        self.assertFalse(is_an_injected_everywhere_url_pattern("http://example.com/*"))
        self.assertFalse(is_an_injected_everywhere_url_pattern("https://example.org/*"))
        self.assertFalse(is_an_injected_everywhere_url_pattern("*://example.org/*"))
        self.assertFalse(is_an_injected_everywhere_url_pattern("*://www.example.org/dir*"))

        # Negative examples (less obvious ones):
        self.assertFalse(is_an_injected_everywhere_url_pattern("file://*/*.text"))
        self.assertFalse(is_an_injected_everywhere_url_pattern("file:///*/*.text"))
        # => Chrome will display the HTML source code only for these, even if there's a "<!DOCTYPE html>" !!!
        self.assertFalse(is_an_injected_everywhere_url_pattern("file://*/owa/*"))
        self.assertFalse(is_an_injected_everywhere_url_pattern("file:///*/owa/*"))
        # => These examples we deem too difficult to exploit. The attacker not only has to send the victim an HTML
        #    file to open but ALSO has to ensure the user places that HTML file into a folder of a specific name!
        #    Note that we also assume the victim won't open any (ZIP) archives we send him (and THEN open an HTML
        #    file WITHIN that archive).
