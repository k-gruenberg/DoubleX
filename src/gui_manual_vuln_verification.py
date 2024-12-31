import tkinter as tk
import dukpy
from typing import List, Optional
import sys
import os
import json

from AnalysisRendererAttackerJSON import AnalysisRendererAttackerJSON
from ManifestJSON import ManifestJSON


selected_extension: Optional[str] = None


def main():
    def on_button_click(_event):  # ToDo: replace with actual implementation for each button click!!!
        # Example button functionality
        print("Button clicked")

    def on_extension_selected(event):
        w = event.widget
        curselection = w.curselection()
        # curselection():
        #    "Returns a tuple containing the line numbers of the selected element or elements, counting from 0.
        #     If nothing is selected, returns an empty tuple."
        if not curselection:
            return  # prevents an "IndexError: tuple index out of range" in the line below!
        index = int(curselection[0])
        subdir_name = w.get(index)
        # print('You selected item %d: "%s"' % (index, subdir_name))

        # Remember selected extension in a separate variable
        #   (this is needed because selecting an item in one of the other Listboxes will unselect the item!):
        global selected_extension
        selected_extension = subdir_name

        # 0. Reset displayed "File content:" after changing the extension:
        file_content_text.config(state=tk.NORMAL)
        file_content_text.delete("1.0", tk.END)
        file_content_text.config(state=tk.DISABLED)

        # 1. Show all files in selected directory under "Unpacked extension:":
        subdir_item_names: List[str] = list()
        extension_dir = os.path.join(sys.argv[1], subdir_name)
        with os.scandir(extension_dir) as subdirectory_items:
            for subdir_item in subdirectory_items:
                subdir_item_names.append(subdir_item.name)
        subdir_item_names.sort()
        unpacked_extension_listbox.delete(0, tk.END)  # clear Listbox
        for subdir_item_name in subdir_item_names:
            unpacked_extension_listbox.insert(tk.END, subdir_item_name)

        # 2. Read manifest.json and update "Name: " and "Description: ":
        manifest_file = os.path.join(extension_dir, "manifest.json")
        manifest = ManifestJSON(path=manifest_file)
        ext_name_label.config(text=f"Name: {manifest.get_name_or_else('<???>')} (v{manifest['version']})")
        ext_description_label.config(text=f"Description: {manifest.get_description_or_else('<???>')[:66]}")

        # 3. Read analysis_renderer_attacker.json and update "Injected into: ":
        analysis_file = os.path.join(extension_dir, "analysis_renderer_attacker.json")
        analysis_result = AnalysisRendererAttackerJSON(path=analysis_file)
        ext_injected_into_label.config(text=f"Injected into: {str(analysis_result['content_script_injected_into'])[:66]}")
        # ToDo: allow user to see full list using a tooltip, popup, or similar...

        # 4. Read analysis_renderer_attacker.json and update "Potential vulnerabilities found:":
        dangers: List[str] = analysis_result.get_dangers_in_str_repr()
        vulnerabilities_listbox.delete(0, tk.END)  # clear Listbox
        for danger in dangers:
            vulnerabilities_listbox.insert(tk.END, danger)

    def on_file_selected(event):
        w = event.widget
        curselection = w.curselection()
        # curselection():
        #    "Returns a tuple containing the line numbers of the selected element or elements, counting from 0.
        #     If nothing is selected, returns an empty tuple."
        if not curselection:
            return  # prevents an "IndexError: tuple index out of range" in the line below!
        index = int(curselection[0])
        file_name = w.get(index)
        # print('You selected item %d: "%s"' % (index, file_name))

        # Read the file content:
        global selected_extension
        file_path = os.path.join(sys.argv[1], selected_extension, file_name)
        with open(file_path, 'r') as file:
            file_content = file.read()

        # Display the file content on the right:
        file_content_text.config(state=tk.NORMAL)
        file_content_text.delete("1.0", tk.END)
        file_content_text.insert(tk.END, str(file_content))
        file_content_text.config(state=tk.DISABLED)

        # ToDo: syntax highlighting !!!

    def eval_js(_event):
        js_input = js_input_text.get("1.0", tk.END)
        print(f"JS input: {js_input}")
        try:
            js_output = dukpy.evaljs(js_input)
        except Exception as e:
            js_output = f"Error: {e}"
        print(f"JS output: {js_output}")
        js_output_text.config(state=tk.NORMAL)
        js_output_text.delete("1.0", tk.END)
        js_output_text.insert(tk.END, str(js_output))
        js_output_text.config(state=tk.DISABLED)
        return "break"  # returning "break" prevents the ENTER press from appending a newline char to the text!

    root = tk.Tk()
    root.title("Manual vulnerability verification GUI")

    # Configure grid layout:
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=2)
    root.grid_columnconfigure(2, weight=1)
    for i in range(7):
        root.grid_rowconfigure(i, weight=0)
    root.grid_rowconfigure(4, weight=1)
    root.grid_rowconfigure(6, weight=1)

    # Left column:
    tk.Label(root, text="Extensions flagged as potentially vulnerable:", anchor="w").grid(row=0, column=0, sticky="ew", padx=5, pady=5)
    extensions_listbox = tk.Listbox(root)
    subdirectory_names: List[str] = []
    with os.scandir(sys.argv[1]) as directory_items:
        for dir_item in directory_items:
            # 1. Is directory?
            # 2. Contains a "manifest.json" file?
            # 3. Contains an "analysis_renderer_attacker.json" file?
            # 4. Does the "analysis_renderer_attacker.json" file contain any dangers?
            if (
                dir_item.is_dir() and
                os.path.isfile(os.path.join(dir_item, "manifest.json")) and
                os.path.isfile(os.path.join(dir_item, "analysis_renderer_attacker.json"))
            ):
                analysis_file = os.path.join(dir_item, "analysis_renderer_attacker.json")
                analysis_result = AnalysisRendererAttackerJSON(path=analysis_file)
                # Only append if analysis_result contains at least 1 danger (all the other ones we don't care about):
                if analysis_result.total_danger_count() > 0:
                    subdirectory_names.append(dir_item.name)
    subdirectory_names.sort()
    for subdir_name in subdirectory_names:
        extensions_listbox.insert(tk.END, subdir_name)
    # ToDo: include checkbox/cross to indicate whether an extension has already been manually checked

    extensions_listbox.grid(row=1, column=0, rowspan=8, sticky="nsew", padx=5, pady=5)
    extensions_listbox.bind('<<ListboxSelect>>', on_extension_selected)
    tk.Label(root, text="Annotations are stored in annotations.csv.", anchor="w").grid(row=9, column=0, sticky="ew", padx=5, pady=5)

    # Center column:
    ext_name_label = tk.Label(root, text="Name: ", anchor="w")
    ext_name_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
    ext_description_label = tk.Label(root, text="Description: ", anchor="w")
    ext_description_label.grid(row=1, column=1, padx=5, pady=5, sticky="w")
    ext_injected_into_label = tk.Label(root, text="Injected into: ", anchor="w")
    ext_injected_into_label.grid(row=2, column=1, padx=5, pady=5, sticky="w")

    tk.Label(root, text="Unpacked extension:", anchor="w").grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    unpacked_extension_listbox = tk.Listbox(root)
    unpacked_extension_listbox.grid(row=4, column=1, sticky="nsew", padx=5, pady=5)
    unpacked_extension_listbox.bind('<<ListboxSelect>>', on_file_selected)

    tk.Label(root, text="Potential vulnerabilities found:", anchor="w").grid(row=5, column=1, sticky="ew", padx=5, pady=5)
    vulnerabilities_listbox = tk.Listbox(root)
    vulnerabilities_listbox.grid(row=6, column=1, sticky="nsew", padx=5, pady=5)

    tk.Label(root, text="Comment:", anchor="w").grid(row=7, column=1, sticky="ew", padx=5, pady=5)
    comment_text = tk.Text(root, height=1)
    comment_text.grid(row=8, column=1, sticky="nsew", padx=5, pady=5)

    # Buttons in the center:
    button_frame = tk.Frame(root)
    button_frame.grid(row=9, column=1, sticky="nsew", padx=5, pady=5)
    button_frame.grid_columnconfigure((0, 1, 2), weight=1)

    tk.Button(button_frame, text="Mark as TP", command=on_button_click).grid(row=0, column=0, padx=5, pady=5)
    tk.Button(button_frame, text="Mark as FP", command=on_button_click).grid(row=0, column=1, padx=5, pady=5)
    # ToDo: "Mark as 'not injected everywhere'" !!!
    tk.Button(button_frame, text="Load ext. into Chrome...", command=on_button_click).grid(row=0, column=2, padx=5, pady=5)

    # Right column:
    tk.Label(root, text="File content:", anchor="w").grid(row=0, column=2, sticky="ew", padx=5, pady=5)
    file_content_text = tk.Text(root, state="disabled")
    file_content_text.grid(row=1, column=2, rowspan=6, sticky="nsew", padx=5, pady=5)

    tk.Label(root, text="JavaScript eval:", anchor="w").grid(row=7, column=2, sticky="ew", padx=5, pady=5)
    js_input_text = tk.Text(root, height=1)
    js_input_text.grid(row=8, column=2, sticky="nsew", padx=5, pady=5)
    js_input_text.bind("<Return>", eval_js)

    js_output_text = tk.Text(root, height=1, state="disabled")
    js_output_text.grid(row=9, column=2, sticky="nsew", padx=5, pady=5)

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
