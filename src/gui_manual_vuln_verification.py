import tkinter as tk
import dukpy
from typing import List, Optional
import sys
import os
import subprocess
import webbrowser
import re
import platform
import tempfile

from AnalysisRendererAttackerJSON import AnalysisRendererAttackerJSON
from ManifestJSON import ManifestJSON
from gui_generate_pdg import syntax_highlighting

selected_extension: Optional[str] = None
selected_extension_version: Optional[str] = None


def main():
    def on_show_in_finder_click():
        global selected_extension
        if selected_extension is None:
            # Open main directory (containing all unpacked extensions):
            directory = sys.argv[1]
        else:
            # Open subdirectory of selected extension:
            directory = os.path.join(sys.argv[1], selected_extension)
        # Open:
        subprocess.call(["open", "-R", directory])

    def on_open_in_web_store_click():
        global selected_extension  # e.g.: "aapbdbdomjkkjkaonfhkkikfgjllcleb-2.0.12-Crx4Chrome.com"
        extension_id: str = re.search("[a-z]{32}", selected_extension).group()  # = selected_extension[0:32]
        web_store_url: str = f"https://chromewebstore.google.com/detail/{extension_id}"
        webbrowser.open(web_store_url, new=2, autoraise=True)

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

        # Enable the "Open in Web Store" button:
        open_in_web_store_button.config(state=tk.NORMAL)

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

        global selected_extension_version
        selected_extension_version = manifest['version']

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

    def show_file_content(file_name: str):
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

        show_file_content(file_name=file_name)

    def on_vulnerability_selected(event):  # ToDo: also highlight "from flow" (in red) and "to flow" (in green) !!!!!
        w = event.widget
        curselection = w.curselection()
        # curselection():
        #    "Returns a tuple containing the line numbers of the selected element or elements, counting from 0.
        #     If nothing is selected, returns an empty tuple."
        if not curselection:
            return  # prevents an "IndexError: tuple index out of range" in the line below!
        index = int(curselection[0])
        vulnerability: str = w.get(index)
        # print('You selected item %d: "%s"' % (index, vulnerability))

        # Determine name of file with vulnerability:
        file_name: str
        if vulnerability.startswith("BP"):
            file_name = "background.js"
        elif vulnerability.startswith("CS"):
            file_name = "content_scripts.js"
        else:
            raise Exception("vulnerability list item starts neither with 'BP' nor with 'CS'")

        # Show content of file with vulnerability:
        show_file_content(file_name=file_name)

        # Determine location of vulnerability:
        vuln_location: str = vulnerability.split(" @ ")[1]  # e.g.: "12:34 - 56:78"
        [start_loc, end_loc] = vuln_location.split(" - ")
        [start_line, start_col] = start_loc.split(":")
        [end_line, end_col] = end_loc.split(":")

        # Scroll to vulnerability:
        file_content_text.see(f'{start_line}.0')

        # Highlight vulnerability in yellow:
        file_content_text.tag_delete("YellowHighlight")
        file_content_text.tag_config("YellowHighlight", background="yellow")
        file_content_text.tag_add("YellowHighlight", f"{start_line}.{start_col}", f"{end_line}.{end_col}")
        # print(f"Highlighted location {(start_line, start_col, end_line, end_col)}")

    def on_mark_as_TP_click():  # ToDo:
        pass

    def on_mark_as_FP_click():  # ToDo:
        pass

    def on_load_ext_into_Chrome_click():
        global selected_extension  # e.g.: "aapbdbdomjkkjkaonfhkkikfgjllcleb-2.0.12-Crx4Chrome.com"

        # 1. Locate the original .CRX file (should be one folder above):
        crx_path: str = os.path.join(sys.argv[1], os.pardir, selected_extension + ".crx")

        # 2. Unpack the .CRX file:
        crx_unpacked_path: str = tempfile.mkdtemp()
        print(f"Unpacking CRX into temp directory: {crx_unpacked_path} ...")
        subprocess.call(["unzip", crx_path, "-d", crx_unpacked_path])
        print("CRX unpacked.")

        # ToDo: add https://github.com/k-gruenberg/renderer_attacker_sim code snippet ?!

        # 3. Load the unpacked .CRX file into Chrome:
        #    => https://stackoverflow.com/questions/16800696/how-install-crx-chrome-extension-via-command-line
        #       => <path to chrome> --load-extension=<path to extension directory>
        path_to_chrome: str
        system: str = platform.system()
        if system == "Darwin":  # macOS:
            path_to_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        else:
            raise Exception(f"unsupported platform: {system}")
        cmd = [path_to_chrome, f"--load-extension={crx_unpacked_path}"]
        print(f"Starting Chrome with command {cmd} ...")
        subprocess.call(cmd)
        # ToDo: clear temp dir
        # (ToDo?: detach process or deliberately wait for the user to close Chrome again?!)
        # (ToDo?: handle case where Chrome is already open?!)

    def on_file_content_change(_event):
        # Check if the text was actually modified
        if file_content_text.edit_modified():
            syntax_highlighting(file_content_text)
            # Reset the modified flag to ensure the event is triggered again
            file_content_text.edit_modified(False)

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

    extensions_listbox.grid(row=1, column=0, rowspan=7, sticky="nsew", padx=5, pady=5)
    extensions_listbox.bind('<<ListboxSelect>>', on_extension_selected)
    tk.Label(root, text="Annotations are stored in annotations.csv.", anchor="w").grid(row=8, column=0, sticky="ew", padx=5, pady=5)

    # Buttons on the left:
    left_button_frame = tk.Frame(root)
    left_button_frame.grid(row=9, column=0, sticky="nsew", padx=5, pady=5)
    left_button_frame.grid_columnconfigure((0, 1), weight=1)
    tk.Button(left_button_frame, text="Show in Finder", command=on_show_in_finder_click).grid(row=0, column=0, padx=5, pady=5)
    open_in_web_store_button = tk.Button(left_button_frame, text="Open in Web Store", command=on_open_in_web_store_click)
    open_in_web_store_button.grid(row=0, column=1, padx=5, pady=5)
    # When no extension is selected yet, there is no meaningful action for the "Open in Web Store" button:
    open_in_web_store_button.config(state=tk.DISABLED)

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
    vulnerabilities_listbox.bind('<<ListboxSelect>>', on_vulnerability_selected)

    tk.Label(root, text="Comment:", anchor="w").grid(row=7, column=1, sticky="ew", padx=5, pady=5)
    comment_text = tk.Text(root, height=1, wrap=tk.NONE)
    comment_text.grid(row=8, column=1, sticky="nsew", padx=5, pady=5)

    # Buttons in the center:
    center_button_frame = tk.Frame(root)
    center_button_frame.grid(row=9, column=1, sticky="nsew", padx=5, pady=5)
    center_button_frame.grid_columnconfigure((0, 1, 2), weight=1)

    tk.Button(center_button_frame, text="Mark as TP", fg='green', command=on_mark_as_TP_click).grid(row=0, column=0, padx=5, pady=5)
    tk.Button(center_button_frame, text="Mark as FP", fg='red', command=on_mark_as_FP_click).grid(row=0, column=1, padx=5, pady=5)
    # ToDo: "Mark as 'not injected everywhere'" !!!
    tk.Button(center_button_frame, text="Load ext. into Chrome...", command=on_load_ext_into_Chrome_click).grid(row=0, column=2, padx=5, pady=5)

    # Right column:
    tk.Label(root, text="File content:", anchor="w").grid(row=0, column=2, sticky="ew", padx=5, pady=5)
    file_content_text = tk.Text(root, state="disabled", wrap=tk.NONE)
    file_content_text.grid(row=1, column=2, rowspan=6, sticky="nsew", padx=5, pady=5)
    file_content_text.bind("<<Modified>>", on_file_content_change)

    tk.Label(root, text="JavaScript eval:", anchor="w").grid(row=7, column=2, sticky="ew", padx=5, pady=5)
    js_input_text = tk.Text(root, height=1, wrap=tk.NONE)
    js_input_text.grid(row=8, column=2, sticky="nsew", padx=5, pady=5)
    js_input_text.bind("<Return>", eval_js)

    js_output_text = tk.Text(root, height=1, state="disabled", wrap=tk.NONE)
    js_output_text.grid(row=9, column=2, sticky="nsew", padx=5, pady=5)

    root.mainloop()


if __name__ == "__main__":
    # Needed for tokenization, which is needed for syntax highlighting (cf. gui_generate_pdg.py):
    os.environ['SOURCE_TYPE'] = "module"

    if len(sys.argv) != 2:
        print("Usage: python3 gui_manual_vuln_verification.py <FOLDER>")
        exit(1)
    elif not os.path.isdir(sys.argv[1]):
        print(f"Error: {sys.argv[1]} is not a directory!")
        exit(1)
    else:
        main()
