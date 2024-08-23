import tkinter as tk
import tempfile
import os

import get_pdg


def main():
    os.environ['PARSER'] = "espree"
    os.environ['SOURCE_TYPE'] = "module"

    def generate():
        js_code = text_left.get("1.0", tk.END)

        tmp_file = tempfile.NamedTemporaryFile()
        with open(tmp_file.name, 'w') as f:
            f.write(js_code)

        res_dict = dict()
        benchmarks = res_dict['benchmarks'] = dict()
        pdg = get_pdg.get_pdg(file_path=tmp_file.name, res_dict=benchmarks)

        # Set content of the right text area:
        text_right.config(state=tk.NORMAL)
        text_right.delete("1.0", tk.END)
        text_right.insert(tk.END, str(pdg))
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

    text_left = tk.Text(frame, width=40, height=10)
    text_left.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    text_right = tk.Text(frame, width=40, height=10)
    text_right.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
    text_right.config(state=tk.DISABLED)

    generate_button = tk.Button(frame, text="Generate PDG", command=generate)
    generate_button.grid(row=1, column=0, columnspan=2, pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
