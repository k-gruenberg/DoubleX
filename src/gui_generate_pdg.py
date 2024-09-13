import time
import tkinter as tk
import tempfile
import os
import json
from tkinter import WORD, CHAR, NONE
from typing import List, Tuple, Optional
import traceback

import get_pdg
from kim_and_lee_vulnerability_detection import analyze_extension
from add_missing_data_flow_edges import add_missing_data_flow_edges
from pdg_js.tokenizer_espree import tokenize
from pdg_js.node import Node

ADD_MISSING_DATA_FLOW_EDGES = True

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__)))

generated_pdg: Optional[Node] = None


# ToDo: syntax highlighting for comments (why doesn't Espree include comment tokens?!)
# ToDo: remember code snippet from last time?!
# ToDo: double click on the RHS also creates highlighting on the LHS (right now only the other way around)
# ToDo: allow dropping in .js / .json / .crx files
# ToDo: add a 3rd extension list column on the very left (with option to sort by and display different criteria),
#       add an extension content list above the current 2nd column => add "Analyze all..." button, make multi-threaded
# ToDo: afterwards: rename this file simply to "gui.py"


def main():
    os.environ['PARSER'] = "espree"
    os.environ['SOURCE_TYPE'] = "module"
    os.environ['INCLUDE_31_VIOLATIONS_WITHOUT_PRIVILEGED_API_ACCESS'] = "yes"
    os.environ['RETURN_MULTIPLE_FLOW_VARIANTS'] = "yes"
    os.environ['DEBUG'] = "yes"

    def generate_pdg():
        global generated_pdg
        try:
            js_code = text_left.get("1.0", tk.END)

            tmp_file = tempfile.NamedTemporaryFile()
            with open(tmp_file.name, 'w') as f:
                f.write(js_code)

            res_dict = dict()
            benchmarks = res_dict['benchmarks'] = dict()
            pdg = get_pdg.get_pdg(file_path=tmp_file.name, res_dict=benchmarks)
            if ADD_MISSING_DATA_FLOW_EDGES:
                no_added_df_edges_cs = add_missing_data_flow_edges(pdg)
                print(f"{no_added_df_edges_cs} missing data flows edges added to PDG")

            generated_pdg = pdg

            # Set content of the right text area:
            text_right.config(state=tk.NORMAL)
            text_right.delete("1.0", tk.END)
            text_right.insert(tk.END, str(pdg))
            text_right.config(state=tk.DISABLED)
        except Exception as e:
            traceback.print_exc()

            generated_pdg = None
            text_right.tag_delete("pdg_tag")

            # Set content of the right text area to the error:
            text_right.config(state=tk.NORMAL)
            text_right.delete("1.0", tk.END)
            text_right.insert(tk.END, str(e))
            text_right.config(state=tk.DISABLED)

    def analyze_as_bp():
        js_code = text_left.get("1.0", tk.END)

        bp = tempfile.NamedTemporaryFile()
        with open(bp.name, 'w') as f:
            f.write(js_code)

        cs = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'contentscript.js')
        manifest_path = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'manifest.json')

        res_dict = analyze_extension(cs, bp.name, json_analysis=None, chrome=True,
                                     war=False, json_apis="all", manifest_path=manifest_path, return_result=True,
                                     store_result_as_json_file=False)
        result = json.dumps(res_dict, indent=4, sort_keys=False, skipkeys=True)

        global generated_pdg
        generated_pdg = None
        text_right.tag_delete("pdg_tag")

        # Set content of the right text area:
        text_right.config(state=tk.NORMAL)
        text_right.delete("1.0", tk.END)
        text_right.insert(tk.END, str(result))
        text_right.config(state=tk.DISABLED)
        highlight_locations(text_left, extract_locations(res_dict))

    def analyze_as_cs():
        js_code = text_left.get("1.0", tk.END)

        cs = tempfile.NamedTemporaryFile()
        with open(cs.name, 'w') as f:
            f.write(js_code)

        bp = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'background.js')
        manifest_path = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'manifest.json')

        res_dict = analyze_extension(cs.name, bp, json_analysis=None, chrome=True,
                                     war=False, json_apis="all", manifest_path=manifest_path, return_result=True,
                                     store_result_as_json_file=False)
        result = json.dumps(res_dict, indent=4, sort_keys=False, skipkeys=True)

        global generated_pdg
        generated_pdg = None
        text_right.tag_delete("pdg_tag")

        # Set content of the right text area:
        text_right.config(state=tk.NORMAL)
        text_right.delete("1.0", tk.END)
        text_right.insert(tk.END, str(result))
        text_right.config(state=tk.DISABLED)
        highlight_locations(text_left, extract_locations(res_dict))

    def syntax_highlighting(text_area):
        # This is a simple example of text highlighting in Tkinter
        #   (cf. https://www.tutorialspoint.com/how-to-change-the-color-of-certain-words-in-a-tkinter-text-widget):
        # text_area.tag_config("identifier", foreground="red")
        # text_area.tag_add("identifier", "1.6", "1.12")
        js_code = text_left.get("1.0", tk.END)
        tokens = tokenize(js_code=js_code)
        # print(tokens)

        text_area.tag_delete("Highlight", "Keyword", "String", "Numeric", "Punctuator", "Identifier")

        if tokens is None:
            print("Syntax highlighting: tokenization error.")
        else:
            text_area.tag_config("Keyword", foreground="red")
            text_area.tag_config("String", foreground="green")
            text_area.tag_config("Numeric", foreground="blue")
            # text_area.tag_config("Punctuator", foreground="blue")  # token['value'] in ['{', '}', '(', ')', '.', ';']
            # text_area.tag_config("Identifier", foreground="blue")
            for token in tokens:
                start_line = token['loc']['start']['line']
                start_column = token['loc']['start']['column']
                end_line = token['loc']['end']['line']
                end_column = token['loc']['end']['column']
                text_area.tag_add(token["type"], f"{start_line}.{start_column}", f"{end_line}.{end_column}")

    def dict_get_all_values_recursively(dict_or_list, query_key):
        result = []
        if isinstance(dict_or_list, dict):
            for key, value in dict_or_list.items():
                if key == query_key:
                    result.append(value)
                elif isinstance(value, dict):
                    result.extend(dict_get_all_values_recursively(value, query_key))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) or isinstance(item, list):
                            result.extend(dict_get_all_values_recursively(item, query_key))
        elif isinstance(dict_or_list, list):
            for item in dict_or_list:
                if isinstance(item, dict) or isinstance(item, list):
                    result.extend(dict_get_all_values_recursively(item, query_key))
        else:
            raise TypeError("dict_get_all_values_recursively(): 1st argument has to be either a dict or a list!")
        return result

    def extract_locations(res_dict):
        result = []
        for loc in dict_get_all_values_recursively(res_dict, "location"):  # e.g.: "3:17 - 3:24"
            [start, end] = loc.split(" - ")
            [start_line, start_column] = start.split(":")
            [end_line, end_column] = end.split(":")
            result.append((start_line, start_column, end_line, end_column))
        # print(f"Locations: {result}")
        return result

    def highlight_locations(text_area, locations: List[Tuple[int, int, int, int]]):
        text_area.tag_delete("Highlight")
        text_area.tag_config("Highlight", background="gray")
        for (start_line, start_column, end_line, end_column) in locations:
            text_area.tag_add("Highlight", f"{start_line}.{start_column}", f"{end_line}.{end_column}")
            # print(f"Highlighted location {(start_line, start_column, end_line, end_column)}")

    def on_text_left_change(_event):
        # Check if the text was actually modified
        if text_left.edit_modified():
            syntax_highlighting(text_left)
            # Reset the modified flag to ensure the event is triggered again
            text_left.edit_modified(False)

    def on_text_left_selection_change(_event):
        try:
            index_start = text_left.index("sel.first")
            index_end = text_left.index("sel.last")

            # (A): Display the currently selected lines & columns in a label, e.g.: "3.9 - 3.12"
            position_label['text'] = index_start + " – " + index_end

            # (B): If currently displaying a PDG (generated_pdg is not None), highlight the corresponding Node(s) on the
            #      RHS text area (displaying the PDG) whenever some code is selected in the LHS text area:
            text_right.tag_delete("pdg_tag")
            global generated_pdg
            if generated_pdg is not None:
                [start_line, start_col] = index_start.split(".")
                [end_line, end_col] = index_end.split(".")
                nodes_to_highlight: List[Node] = generated_pdg.get_all_nodes_within_code_excerpt(
                    int(start_line), int(start_col), int(end_line), int(end_col)
                )

                for node_to_highlight in nodes_to_highlight:
                    node_id = node_to_highlight.id
                    start_index = "1.0"
                    while True:  # Highlight *every* occurrence of f"[{node_id}]" in the RHS text area:
                        highlight_start = text_right.search(f"[{node_id}]", start_index)
                        # Note that Tkinter's .search() functions exhibits weird behavior:
                        #   It will only ever return the empty string "" if the pattern isn't found *anywhere* in the
                        #   text. If it doesn't find the pattern after start_index, it'll wrap back to the beginning
                        #   of the text and starts searching again from there, creating an infinite loop in our case...
                        if highlight_start == "" or text_right.compare(highlight_start, "<", start_index):
                            break
                        else:
                            highlight_end = text_right.search("]", highlight_start)
                            text_right.tag_add("pdg_tag", highlight_start, highlight_end + "+1c")
                            # "+1c" to include the "]"
                            # cf. https://anzeljg.github.io/rin2/book2/2405/docs/tkinter/text-index.html for "+1c" syntax
                            start_index = highlight_end

                text_right.tag_configure("pdg_tag", background="cornflower blue", foreground="black")
        except tk.TclError:
            # (A): reset:
            position_label['text'] = ""
            # (B): reset:
            text_right.tag_delete("pdg_tag")

    root = tk.Tk()
    root.title("PDG Generator")
    root.state("zoomed")

    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)  #frame.pack(padx=10, pady=10)

    # Configure the grid to allow the text areas to expand
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_columnconfigure(1, weight=1)
    frame.grid_columnconfigure(2, weight=1)
    frame.grid_columnconfigure(3, weight=1)

    text_left = tk.Text(frame, width=40, height=10, wrap=NONE)
    text_left.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
    text_left.bind("<<Modified>>", on_text_left_change)
    text_left.bind("<<Selection>>", on_text_left_selection_change)

    text_right = tk.Text(frame, width=40, height=10, wrap=NONE)
    text_right.grid(row=0, column=2, columnspan=2, padx=5, pady=5, sticky="nsew")
    text_right.config(state=tk.DISABLED)

    position_label = tk.Label(frame, text="")
    position_label.grid(row=1, column=0, columnspan=1, pady=10)

    generate_button = tk.Button(frame, text="Generate PDG", command=generate_pdg)
    generate_button.grid(row=1, column=1, columnspan=1, pady=10)

    analyze_as_bp_button = tk.Button(frame, text="Analyze as BP", command=analyze_as_bp)
    analyze_as_bp_button.grid(row=1, column=2, columnspan=1, pady=10)

    analyze_as_cs_button = tk.Button(frame, text="Analyze as CS", command=analyze_as_cs)
    analyze_as_cs_button.grid(row=1, column=3, columnspan=1, pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
