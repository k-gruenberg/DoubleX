import tkinter as tk
import tempfile
import os
import json

import get_pdg
from kim_and_lee_vulnerability_detection import analyze_extension, add_missing_data_flow_edges

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def main():
    os.environ['PARSER'] = "espree"
    os.environ['SOURCE_TYPE'] = "module"

    def generate_pdg():
        js_code = text_left.get("1.0", tk.END)

        tmp_file = tempfile.NamedTemporaryFile()
        with open(tmp_file.name, 'w') as f:
            f.write(js_code)

        res_dict = dict()
        benchmarks = res_dict['benchmarks'] = dict()
        pdg = get_pdg.get_pdg(file_path=tmp_file.name, res_dict=benchmarks)
        no_added_df_edges_cs = add_missing_data_flow_edges(pdg)
        print(f"{no_added_df_edges_cs} missing data flows edges added to PDG")

        # Set content of the right text area:
        text_right.config(state=tk.NORMAL)
        text_right.delete("1.0", tk.END)
        text_right.insert(tk.END, str(pdg))
        text_right.config(state=tk.DISABLED)

    def analyze_as_bp():
        js_code = text_left.get("1.0", tk.END)

        bp = tempfile.NamedTemporaryFile()
        with open(bp.name, 'w') as f:
            f.write(js_code)

        cs = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'contentscript.js')
        manifest_path = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'manifest.json')

        res_dict = analyze_extension(cs, bp.name, json_analysis=None, chrome=True,
                                     war=False, json_apis="all", manifest_path=manifest_path, return_result=True)
        result = json.dumps(res_dict, indent=4, sort_keys=False, skipkeys=True)

        # Set content of the right text area:
        text_right.config(state=tk.NORMAL)
        text_right.delete("1.0", tk.END)
        text_right.insert(tk.END, str(result))
        text_right.config(state=tk.DISABLED)

    def analyze_as_cs():
        js_code = text_left.get("1.0", tk.END)

        cs = tempfile.NamedTemporaryFile()
        with open(cs.name, 'w') as f:
            f.write(js_code)

        bp = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'background.js')
        manifest_path = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'manifest.json')

        res_dict = analyze_extension(cs.name, bp, json_analysis=None, chrome=True,
                                     war=False, json_apis="all", manifest_path=manifest_path, return_result=True)
        result = json.dumps(res_dict, indent=4, sort_keys=False, skipkeys=True)

        # Set content of the right text area:
        text_right.config(state=tk.NORMAL)
        text_right.delete("1.0", tk.END)
        text_right.insert(tk.END, str(result))
        text_right.config(state=tk.DISABLED)

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

    text_left = tk.Text(frame, width=40, height=10)
    text_left.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

    text_right = tk.Text(frame, width=40, height=10)
    text_right.grid(row=0, column=2, columnspan=2, padx=5, pady=5, sticky="nsew")
    text_right.config(state=tk.DISABLED)

    generate_button = tk.Button(frame, text="Generate PDG", command=generate_pdg)
    generate_button.grid(row=1, column=0, columnspan=1, pady=10)

    generate_button = tk.Button(frame, text="Analyze as BP", command=analyze_as_bp)
    generate_button.grid(row=1, column=1, columnspan=1, pady=10)

    generate_button = tk.Button(frame, text="Analyze as CS", command=analyze_as_cs)
    generate_button.grid(row=1, column=2, columnspan=1, pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
