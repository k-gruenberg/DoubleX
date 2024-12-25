import tkinter as tk
import sys
import os


def main():
    def on_button_click():
        # Example button functionality
        print("Button clicked")

    root = tk.Tk()
    root.title("Manual vulnerability verification GUI")

    # Configure grid layout:
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=2)
    root.grid_columnconfigure(2, weight=1)
    for i in range(7):
        root.grid_rowconfigure(i, weight=0)
    root.grid_rowconfigure(1, weight=1)
    root.grid_rowconfigure(3, weight=1)

    # Left column:
    tk.Label(root, text="Extensions flagged as potentially vulnerable:", anchor="w").grid(row=0, column=0, sticky="ew", padx=5, pady=5)
    extensions_listbox = tk.Listbox(root)
    extensions_listbox.grid(row=1, column=0, rowspan=5, sticky="nsew", padx=5, pady=5)
    tk.Label(root, text="Annotations are stored in annotations.csv.", anchor="w").grid(row=6, column=0, sticky="ew", padx=5, pady=5)

    # Center column:
    tk.Label(root, text="Unpacked extension:", anchor="w").grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    unpacked_extension_listbox = tk.Listbox(root)
    unpacked_extension_listbox.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

    tk.Label(root, text="Potential vulnerabilities found:", anchor="w").grid(row=2, column=1, sticky="ew", padx=5, pady=5)
    vulnerabilities_listbox = tk.Listbox(root)
    vulnerabilities_listbox.grid(row=3, column=1, sticky="nsew", padx=5, pady=5)

    tk.Label(root, text="Comment:", anchor="w").grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    comment_text = tk.Text(root, height=1)
    comment_text.grid(row=5, column=1, sticky="nsew", padx=5, pady=5)

    # Buttons in the center:
    button_frame = tk.Frame(root)
    button_frame.grid(row=6, column=1, sticky="nsew", padx=5, pady=5)
    button_frame.grid_columnconfigure((0, 1, 2), weight=1)

    tk.Button(button_frame, text="Mark as TP", command=on_button_click).grid(row=0, column=0, padx=5, pady=5)
    tk.Button(button_frame, text="Mark as FP", command=on_button_click).grid(row=0, column=1, padx=5, pady=5)
    tk.Button(button_frame, text="Load ext. into Chrome...", command=on_button_click).grid(row=0, column=2, padx=5, pady=5)

    # Right column:
    tk.Label(root, text="File content:", anchor="w").grid(row=0, column=2, sticky="ew", padx=5, pady=5)
    file_content_text = tk.Text(root, state="disabled")
    file_content_text.grid(row=1, column=2, rowspan=3, sticky="nsew", padx=5, pady=5)

    tk.Label(root, text="JavaScript console:", anchor="w").grid(row=4, column=2, sticky="ew", padx=5, pady=5)
    js_input_text = tk.Text(root, height=1)
    js_input_text.grid(row=5, column=2, sticky="nsew", padx=5, pady=5)

    js_output_text = tk.Text(root, height=1, state="disabled")
    js_output_text.grid(row=6, column=2, sticky="nsew", padx=5, pady=5)

    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 gui_manual_vuln_verification.py <FOLDER>")
        exit(1)
    elif not os.path.isdir(sys.argv[1]):
        print(f"Error: {sys.argv[1]} is not a directory!")
        exit(1)
    else:
        main()
