import unittest
import os

from pdg_js.MessageListener import RuntimeOnMessageListener, PortOnMessageListener
from src.pdg_js.node import Node


os.environ['PARSER'] = "espree"
os.environ['SOURCE_TYPE'] = "module"
os.environ['DEBUG'] = "yes"
os.environ['TIMEOUT'] = "600"


def generate_pdg(code: str, ast_only=False) -> Node:
    res_dict = dict()
    benchmarks = res_dict['benchmarks'] = dict()

    return Node.pdg_from_string(
        js_code=code,
        benchmarks=benchmarks,
        add_my_data_flows=not ast_only,
    )


class TestMessageListener(unittest.TestCase):
    def test_RuntimeOnMessageListener_sender_identifiers(self):
        code = """
        chrome.runtime.onMessage.addListener((msg, sender1, sendResponse) => {
            chrome.cookies.getAll({},
                function(cookies) {
                    sendResponse(cookies);
                }
            );
            return true;
        });
        """
        pdg: Node = generate_pdg(code)
        print(pdg)
        arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
        sender1: Node = arrow_func_expr.children[1]
        self.assertEqual(sender1.name, "Identifier")
        self.assertEqual(sender1.attributes['name'], "sender1")
        msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
        self.assertEqual(msg_listener.get_all_sender_identifiers(), [sender1])

    def test_RuntimeOnMessageListener_url_identifiers(self):
        try:
            code = """
            chrome.runtime.onMessage.addListener((msg, sender1, sendResponse) => {
                let url1 = sender1.url;
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onMessage.addListener((msg, {url: url1}, sendResponse) => {
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onMessage.addListener((msg, {url}, sendResponse) => {
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url: Node = pdg.get_all_identifiers_by_name("url")[1]
            self.assertEqual(url.name, "Identifier")
            self.assertEqual(url.attributes['name'], "url")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url])
        except NotImplementedError:
            pass  # have this test pass as long as get_all_url_identifiers() is still un-implemented

    def test_RuntimeOnMessageListener_tab_url_identifiers(self):
        try:
            code = """
            chrome.runtime.onMessage.addListener((msg, sender1, sendResponse) => {
                let url1 = sender1.tab.url;
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onMessage.addListener((msg, sender1, sendResponse) => {
                let tab1 = sender1.tab;
                let url1 = tab1.url;
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onMessage.addListener((msg, {tab: tab1}, sendResponse) => {
                let url1 = tab1.url;
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onMessage.addListener((msg, {tab}, sendResponse) => {
                let url1 = tab.url;
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_all_identifiers_by_name("url1")[1]
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onMessage.addListener((msg, {tab: {url: url1}}, sendResponse) => {
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onMessage.addListener((msg, {tab: {url}}, sendResponse) => {
                chrome.cookies.getAll({},
                    function(cookies) {
                        sendResponse(cookies);
                    }
                );
                return true;
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url: Node = pdg.get_identifier_by_name("url")
            self.assertEqual(url.name, "Identifier")
            self.assertEqual(url.attributes['name'], "url")
            msg_listener: RuntimeOnMessageListener = RuntimeOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url])
        except NotImplementedError:
            pass  # have this test pass as long as get_all_url_identifiers() is still un-implemented

    def test_PortOnMessageListener_sender_identifiers(self):
        code = """
        chrome.runtime.onConnect.addListener(function(port) {
            port.onMessage.addListener((msg, port) => {
                let sender1 = port.sender;
                port.postMessage("answer");
            });   
        });
        """
        pdg: Node = generate_pdg(code)
        print(pdg)
        arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
        sender1: Node = pdg.get_identifier_by_name("sender1")
        self.assertEqual(sender1.name, "Identifier")
        self.assertEqual(sender1.attributes['name'], "sender1")
        msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
        self.assertEqual(msg_listener.get_all_sender_identifiers(), [sender1])

        code = """
        chrome.runtime.onConnect.addListener(function(port) {
            port.onMessage.addListener((msg, {sender: sender1}) => {
                port.postMessage("answer");
            });   
        });
        """
        pdg: Node = generate_pdg(code)
        print(pdg)
        arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
        sender1: Node = pdg.get_identifier_by_name("sender1")
        self.assertEqual(sender1.name, "Identifier")
        self.assertEqual(sender1.attributes['name'], "sender1")
        msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
        self.assertEqual(msg_listener.get_all_sender_identifiers(), [sender1])

        code = """
        chrome.runtime.onConnect.addListener(function(port) {
            port.onMessage.addListener((msg, {sender}) => {
                port.postMessage("answer");
            });   
        });
        """
        pdg: Node = generate_pdg(code)
        print(pdg)
        arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
        sender: Node = pdg.get_all_identifiers_by_name("sender")[1]
        self.assertEqual(sender.name, "Identifier")
        self.assertEqual(sender.attributes['name'], "sender")
        msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
        self.assertEqual(msg_listener.get_all_sender_identifiers(), [sender])

    def test_PortOnMessageListener_url_identifiers(self):
        try:
            code = """
            chrome.runtime.onConnect.addListener(function(port) {
                port.onMessage.addListener((msg, port) => {
                    let sender1 = port.sender;
                    let url1 = sender1.url;
                    port.postMessage("answer");
                });   
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onConnect.addListener(function(port) {
                port.onMessage.addListener((msg, {sender: sender1}) => {
                    let url1 = sender1.url;
                    port.postMessage("answer");
                });   
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onConnect.addListener(function(port) {
                port.onMessage.addListener((msg, {sender: {url: url1}}) => {
                    port.postMessage("answer");
                });   
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onConnect.addListener(function(port) {
                port.onMessage.addListener((msg, {sender: {url}}) => {
                    port.postMessage("answer");
                });   
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url: Node = pdg.get_all_identifiers_by_name("url")[1]
            self.assertEqual(url.name, "Identifier")
            self.assertEqual(url.attributes['name'], "url")
            msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url])
        except NotImplementedError:
            pass  # have this test pass as long as get_all_url_identifiers() is still un-implemented

    def test_PortOnMessageListener_tab_url_identifiers(self):
        try:
            code = """
            chrome.runtime.onConnect.addListener(function(port) {
                port.onMessage.addListener((msg, port) => {
                    let sender1 = port.sender;
                    let url1 = sender1.tab.url;
                    port.postMessage("answer");
                });   
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onConnect.addListener(function(port) {
                port.onMessage.addListener((msg, {sender: sender1}) => {
                    let url1 = sender1.tab.url;
                    port.postMessage("answer");
                });   
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url1: Node = pdg.get_identifier_by_name("url1")
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url1")
            msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url1])

            code = """
            chrome.runtime.onConnect.addListener(function(port) {
                port.onMessage.addListener((msg, {sender: {tab: {url}}}) => {
                    port.postMessage("answer");
                });   
            });
            """
            pdg: Node = generate_pdg(code)
            print(pdg)
            arrow_func_expr: Node = pdg.get_all("ArrowFunctionExpression")[0]
            url: Node = pdg.get_all_identifiers_by_name("url")[1]
            self.assertEqual(url1.name, "Identifier")
            self.assertEqual(url1.attributes['name'], "url")
            msg_listener: PortOnMessageListener = PortOnMessageListener(arrow_func_expr)
            self.assertEqual(msg_listener.get_all_url_identifiers(), [url])
        except NotImplementedError:
            pass  # have this test pass as long as get_all_url_identifiers() is still un-implemented
