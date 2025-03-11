import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
import dukpy
from typing import List, Optional, Dict
import sys
import os
import subprocess
import webbrowser
import re
import platform
import tempfile
import json
import shutil

from AnalysisRendererAttackerJSON import AnalysisRendererAttackerJSON
from AnnotationsCSV import AnnotationsCSV
from ManifestJSON import ManifestJSON
from gui_generate_pdg import syntax_highlighting
from INJECTED_EVERYWHERE_PATTERNS import is_an_injected_everywhere_url_pattern


# Change this to "NAME" if you used the "--analysis-outfile-name NAME" argument when running doublex.py:
ANALYSIS_OUTFILE_NAME = "analysis_renderer_attacker"  # .json


annotations_csv: Optional[AnnotationsCSV] = None

selected_extension: Optional[str] = None
selected_extension_version: Optional[str] = None

# "Load ext. into Chrome..." settings:
setting_chrome_path: str = ""
setting_add_renderer_attacker_sim_code_snippet: bool = True
setting_detach_process: bool = True

detached_chrome_process: Optional[subprocess.Popen] = None

temp_folder_to_delete: Optional[str] = None

# The two numbers displayed by the extensions_list_label (the label on the very top-left):
no_of_ext_annotated: int = -1
no_of_ext_to_annotate: int = -1


def on_exit(_event):
    # Before exiting, delete the remaining temp folder (if one exists):
    global temp_folder_to_delete
    if temp_folder_to_delete is not None and os.path.isdir(temp_folder_to_delete):
        print(f"Before exiting, deleting temp folder {temp_folder_to_delete} ...")
        shutil.rmtree(temp_folder_to_delete)
        print(f"Temp folder deleted.")


def main():
    def update_extensions_list_label():  # TODO: update not only at every restart but each time an annotation is added!
        global no_of_ext_annotated
        global no_of_ext_to_annotate
        extensions_list_label.config(text=f"Flagged Extensions ({no_of_ext_annotated}/{no_of_ext_to_annotate} annotated):")

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

    def remove_current_selection_marking():
        for idx, listbox_entry in enumerate(extensions_listbox.get(0, tk.END)):
            if listbox_entry.startswith("🟣 "):
                annotations: List[str] = annotations_csv.get_annotations(listbox_entry.lstrip("🟣 "))
                extension_dir = os.path.join(sys.argv[1], listbox_entry.lstrip("🟣 "))
                analysis_file: str = os.path.join(extension_dir, f"{ANALYSIS_OUTFILE_NAME}.json")
                danger_count = AnalysisRendererAttackerJSON(path=analysis_file).total_danger_count()
                if len(annotations) == 0:
                    restored_circle_indicator = "🔴"
                elif len(annotations) == danger_count:
                    restored_circle_indicator = "🟢"
                else:
                    restored_circle_indicator = "🟡"
                extensions_listbox.delete(idx)
                extensions_listbox.insert(idx, restored_circle_indicator + " " + listbox_entry.lstrip("🟣 "))

    def on_extension_selected(event):
        w: tk.Listbox = event.widget
        curselection = w.curselection()
        # curselection():
        #    "Returns a tuple containing the line numbers of the selected element or elements, counting from 0.
        #     If nothing is selected, returns an empty tuple."
        if not curselection:
            return  # prevents an "IndexError: tuple index out of range" in the line below!
        index = int(curselection[0])
        subdir_name = w.get(index)
        # print('You selected item %d: "%s"' % (index, subdir_name))
        subdir_name = subdir_name.lstrip("🟣 ").lstrip("🔴 ").lstrip("🟡 ").lstrip("🟢 ")

        # Remember selected extension in a separate variable
        #   (this is needed because selecting an item in one of the other Listboxes will unselect the item!):
        global selected_extension
        selected_extension = subdir_name

        # Remove the current "🟣" selection marking (if present):
        remove_current_selection_marking()

        # Mark selection using a "🟣":
        w.delete(curselection[0])
        w.insert(index, "🟣 " + subdir_name)

        # Enable the "Open in Web Store" button:
        open_in_web_store_button.config(state=tk.NORMAL)

        # 0a. Reset displayed "File content:" after changing the extension:
        file_content_text.config(state=tk.NORMAL)
        file_content_text.delete("1.0", tk.END)
        file_content_text.config(state=tk.DISABLED)

        # 0b. Reset displayed annotation comment after changing the extension:
        comment_text.delete("1.0", tk.END)

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
        analysis_file = os.path.join(extension_dir, f"{ANALYSIS_OUTFILE_NAME}.json")
        analysis_result = AnalysisRendererAttackerJSON(path=analysis_file)
        ext_injected_into_label.config(text=f"Injected into: {str(analysis_result['content_script_injected_into'])[:66]}")
        # Allow user to see full list of injection URL patterns by double-clicking:
        ext_injected_into_label.bind(
            '<Double-Button-1>',
            lambda _event: tk.messagebox.showinfo(title="Injected into:",
                                                  message=str(analysis_result['content_script_injected_into']))
        )

        # 4. Read analysis_renderer_attacker.json and update "Potential vulnerabilities found:":
        update_vulnerabilities_listbox()

    def update_vulnerabilities_listbox():
        global selected_extension
        extension_dir = os.path.join(sys.argv[1], selected_extension)
        analysis_file = os.path.join(extension_dir, f"{ANALYSIS_OUTFILE_NAME}.json")
        analysis_result = AnalysisRendererAttackerJSON(path=analysis_file)
        dangers: List[str] = analysis_result.get_dangers_in_str_repr()
        vulnerabilities_listbox.delete(0, tk.END)  # clear Listbox
        global annotations_csv
        for danger in dangers:
            annotation_bool: Optional[bool] = annotations_csv.get_annotation_bool(
                extension=selected_extension,
                vulnerability=danger,
            )
            prefix: str = ""
            if annotation_bool is True:
                prefix = "✅ "
            elif annotation_bool is False:
                prefix = "❌ "
            else:
                print(f"No annotation present for {danger} of {selected_extension}")
            vulnerabilities_listbox.insert(tk.END, prefix + danger)

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

    def on_vulnerability_selected(event):
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

        # Strip the checkbox/cross prefix (marking TP/FP) of the vulnerability list item:
        vulnerability = vulnerability.lstrip("✅ ").lstrip("❌ ")

        # Determine and show the comment that has been associated with the vulnerability in the annotations.csv file
        #   (if present):
        global annotations_csv
        global selected_extension
        comment: str = annotations_csv.get_annotation_comment(
            extension=selected_extension,
            vulnerability=vulnerability,
        )
        # Note that the value returned by get_annotation_comment() will never be None,
        #   instead it will return the empty string "" if no comment is present in the annotations.csv file!
        if comment != "":
            # Note: Sometimes the vulnerability list box will lose focus (e.g. when selecting code on the right).
            #       The check above is to prevent the user's WIP comment from getting deleted when re-selecting
            #       the (not yet annotated) vulnerability.
            comment_text.delete("1.0", tk.END)
            comment_text.insert(tk.END, str(comment))

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

        # Determine index of vulnerability (#1, #2, #3, etc.):
        vuln_index: int = int(vulnerability.split("#")[1].split(" ")[0])

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

        # Retrieve corresponding "from flow" and "to flow" from the analysis_renderer_attacker.json file:
        extension_dir = os.path.join(sys.argv[1], selected_extension)
        analysis_file = os.path.join(extension_dir, f"{ANALYSIS_OUTFILE_NAME}.json")
        analysis_result = AnalysisRendererAttackerJSON(path=analysis_file)
        vulnerabilities = analysis_result["bp" if vulnerability.startswith("BP") else "cs"]["exfiltration_dangers" if "exfiltration danger" in vulnerability else "infiltration_dangers"]
        try:
            vuln = vulnerabilities[vuln_index-1]
            assert vuln["rendezvous"]["location"] == vuln_location  # e.g.: "12:34 - 56:78"
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Error: {e}"
            )
            return
        from_flow = vuln["from_flow"]
        to_flow = vuln["to_flow"]

        # Highlight each node of the "from flow" in red:
        file_content_text.tag_delete("RedHighlight")
        file_content_text.tag_config("RedHighlight", background="red")
        for node in from_flow:
            node_location: str = node["location"]  # e.g.: "12:34 - 56:78"
            [start_loc, end_loc] = node_location.split(" - ")
            [start_line, start_col] = start_loc.split(":")
            [end_line, end_col] = end_loc.split(":")
            file_content_text.tag_add("RedHighlight", f"{start_line}.{start_col}", f"{end_line}.{end_col}")

        # Highlight each node of the "to flow" in green:
        file_content_text.tag_delete("GreenHighlight")
        file_content_text.tag_config("GreenHighlight", background="green")
        for node in to_flow:
            node_location: str = node["location"]  # e.g.: "12:34 - 56:78"
            [start_loc, end_loc] = node_location.split(" - ")
            [start_line, start_col] = start_loc.split(":")
            [end_line, end_col] = end_loc.split(":")
            file_content_text.tag_add("GreenHighlight", f"{start_line}.{start_col}", f"{end_line}.{end_col}")

    def mark_as_TP_or_FP(true_positive: bool):
        global annotations_csv
        global selected_extension

        curselection = vulnerabilities_listbox.curselection()
        if not curselection:
            messagebox.showerror("Error", "Error: No vulnerability selected.")
        else:
            index: int = int(curselection[0])
            selected_vulnerability: str = vulnerabilities_listbox.get(index)
            # Remove prefix (only needed for updating functionality):
            selected_vulnerability = selected_vulnerability.lstrip("✅ ").lstrip("❌ ")
            annotations_csv.add_or_update_annotation(
                extension=selected_extension,
                vulnerability=selected_vulnerability,
                true_positive=true_positive,
                comment=comment_text.get("1.0", tk.END)
            )
            # Update checkmarks in Listboxes (also acts as a visual feedback to the user!):
            update_vulnerabilities_listbox()

    def on_mark_as_TP_click():
        mark_as_TP_or_FP(true_positive=True)

    def on_mark_as_FP_click():
        mark_as_TP_or_FP(true_positive=False)

    def on_load_ext_into_Chrome_click():
        global selected_extension  # e.g.: "aapbdbdomjkkjkaonfhkkikfgjllcleb-2.0.12-Crx4Chrome.com"
        global setting_chrome_path
        global setting_add_renderer_attacker_sim_code_snippet
        global setting_detach_process
        global detached_chrome_process

        if selected_extension is None:
            tk.messagebox.showerror(title="", message="No extension selected!")
            return

        # Refuse when there's still another detached Chrome process running:
        if detached_chrome_process is not None and detached_chrome_process.poll() is None:
            tk.messagebox.showerror(
                title="",
                message="Another Chrome process is still running, please quit before continuing!"
            )
            return
        # TODO: also refuse if there's another Chrome process that wasn't started by *us* !!!

        # 1. Locate the original .CRX file (should be one folder above):
        crx_path: str = os.path.join(sys.argv[1], os.pardir, selected_extension + ".crx")

        # 2. Unpack the .CRX file:
        crx_unpacked_path: str = tempfile.mkdtemp()
        print(f"Unpacking CRX into temp directory: {crx_unpacked_path} ...")
        subprocess.call(["unzip", crx_path, "-d", crx_unpacked_path])
        print("CRX unpacked.")

        # 3. Add https://github.com/k-gruenberg/renderer_attacker_sim code snippet (unless explicitly disabled):
        if setting_add_renderer_attacker_sim_code_snippet:
            # The code snippet:
            with open('code_snippet.js', 'r') as code_snippet_js_file:
                code_snippet: str = code_snippet_js_file.read()

            # Read the manifest.json file of the extension that we just unpacked into a temp folder:
            with open(os.path.join(crx_unpacked_path, 'manifest.json'), 'r') as manifest_json_file:
                manifest = json.load(manifest_json_file)

            # Pick one(!) content script to paste the code snippet into, ...:
            code_snippet_injected: bool = False
            # ...preferably one that is injected into "<all_urls>":
            for content_script in manifest["content_scripts"]:
                if any(url_pattern == "<all_urls>" for url_pattern in content_script["matches"]):
                    cs_js_file_path = content_script["js"][0]
                    cs_js_file_full_path = os.path.join(crx_unpacked_path, cs_js_file_path)
                    # Before appending the code snippet to the content script, ensure that we have permission to do so:
                    subprocess.run(['chmod', '+w', cs_js_file_full_path])
                    # Append the code snippet to said content script:
                    with open(cs_js_file_full_path, 'a') as cs_js_file:
                        cs_js_file.write(code_snippet)
                    code_snippet_injected = True
                    break
            # ...otherwise one that is injected everywhere:
            if not code_snippet_injected:
                for content_script in manifest["content_scripts"]:
                    if any(is_an_injected_everywhere_url_pattern(url_pattern) for url_pattern in content_script["matches"]):
                        cs_js_file_path = content_script["js"][0]
                        cs_js_file_full_path = os.path.join(crx_unpacked_path, cs_js_file_path)
                        # Before appending the code snippet to the content script, ensure that we have permission to do so:
                        subprocess.run(['chmod', '+w', cs_js_file_full_path])
                        # Append the code snippet to said content script:
                        with open(cs_js_file_full_path, 'a') as cs_js_file:
                            cs_js_file.write(code_snippet)
                        break

        # 4. Determine the path to Chrome:
        path_to_chrome: str
        system: str = platform.system()
        if system == "Darwin":  # On macOS, we know where Google Chrome is located:
            path_to_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        else:  # On other platforms, we'll ask the user once for the path and then remember it for the session:
            if setting_chrome_path == "":
                if user_given_path := tk.simpledialog.askstring('Enter path to Chrome', 'Please enter the path to Google Chrome on your machine:'):
                    setting_chrome_path = user_given_path
                else:  # User pressed "Cancel" or entered an empty string:
                    return
            path_to_chrome = setting_chrome_path

        # 5. Load the unpacked .CRX file into Chrome (and also immediately open the attacker/exploit console):
        #    => https://stackoverflow.com/questions/16800696/how-install-crx-chrome-extension-via-command-line
        #       => <path to chrome> --load-extension=<path to extension directory>
        cmd = [path_to_chrome, os.path.join(__file__, "../exploit_console.html"), f"--load-extension={crx_unpacked_path}"]
        print(f"Starting {'detached' if setting_detach_process else ''} Chrome with command {cmd} ...")
        if setting_detach_process:
            # Delete the temp folder from last time (not needed anymore):
            global temp_folder_to_delete
            if temp_folder_to_delete is not None:
                print(f"Deleting now unneeded temp folder {temp_folder_to_delete} ...")
                shutil.rmtree(temp_folder_to_delete)
                print(f"Temp folder deleted.")
            # Start the Chrome process as a separate detached process using subprocess.Popen():
            detached_chrome_process = subprocess.Popen(cmd)
            # Next time, this folder will be up for deletion:
            temp_folder_to_delete = crx_unpacked_path
        else:
            subprocess.call(cmd)
            print(f"Subprocess call ended. Deleting now unneeded temp folder {crx_unpacked_path} ...")
            shutil.rmtree(crx_unpacked_path)
            print(f"Temp folder deleted.")

    def on_load_ext_into_Chrome_settings_button_click():
        # Create settings window:
        settings_dialog = tk.Toplevel(root)
        settings_dialog.title("'Load ext. into Chrome...' settings:")

        # Add widgets:
        tk.Label(settings_dialog, text="Chrome Path: ").grid(row=0, column=0, padx=10, pady=10)
        chrome_path_text = tk.Text(settings_dialog, height=1, width=35, wrap=tk.NONE)
        chrome_path_text.grid(row=0, column=1, padx=10, pady=10)
        add_code_snippet_bool_var = tk.BooleanVar()
        add_code_snippet_check_button = tk.Checkbutton(settings_dialog, text="Add renderer_attacker_sim code snippet", variable=add_code_snippet_bool_var)
        add_code_snippet_check_button.grid(row=1, column=0, columnspan=2, padx=10, pady=10)
        detach_process_bool_var = tk.BooleanVar()
        detach_process_check_button = tk.Checkbutton(settings_dialog, text="Detach process", variable=detach_process_bool_var)
        detach_process_check_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

        def load():
            global setting_chrome_path
            global setting_add_renderer_attacker_sim_code_snippet
            global setting_detach_process
            chrome_path_text.delete("1.0", tk.END)
            chrome_path_text.insert(tk.END, setting_chrome_path)
            add_code_snippet_bool_var.set(setting_add_renderer_attacker_sim_code_snippet)
            detach_process_bool_var.set(setting_detach_process)

        load()

        def save():
            global setting_chrome_path
            global setting_add_renderer_attacker_sim_code_snippet
            global setting_detach_process
            setting_chrome_path = chrome_path_text.get("1.0", tk.END)
            setting_add_renderer_attacker_sim_code_snippet = add_code_snippet_bool_var.get()
            setting_detach_process = detach_process_bool_var.get()
            settings_dialog.destroy()

        tk.Button(settings_dialog, text="Save", command=save).grid(row=3, column=0, pady=10)
        tk.Button(settings_dialog, text="Cancel", command=settings_dialog.destroy).grid(row=3, column=1, pady=10)

        # Ensure dialog stays on top and wait for it to close:
        settings_dialog.transient(root)  # Keep the dialog on top of the main window.
        settings_dialog.grab_set()  # Make the dialog modal.
        settings_dialog.wait_window()  # Wait until the dialog is closed.

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
    photo = tk.PhotoImage(file='icon_gui_manual_vuln_verification.png')
    root.wm_iconphoto(False, photo)
    root.title(f"Manual vulnerability verification GUI: {sys.argv[1]}")
    root.bind('<Destroy>', on_exit)

    # Set up annotations.csv:
    global annotations_csv
    annotations_csv = AnnotationsCSV(path=os.path.join(sys.argv[1], "annotations.csv"))
    annotations_csv.print_stats()

    # Configure grid layout:
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=2)
    root.grid_columnconfigure(2, weight=1)
    for i in range(7):
        root.grid_rowconfigure(i, weight=0)
    root.grid_rowconfigure(4, weight=1)
    root.grid_rowconfigure(6, weight=1)

    # Left column:
    extensions_list_label = tk.Label(root, text="Flagged Extensions (?/? annotated):", anchor="w")
    extensions_list_label.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
    extensions_listbox = tk.Listbox(root)
    subdirectory_names: List[str] = []
    danger_counts: Dict[str, int] = dict()
    count_extension_cs_not_injected_everywhere: int = 0
    with os.scandir(sys.argv[1]) as directory_items:
        for dir_item in directory_items:
            # 1. Is directory?
            # 2. Contains a "manifest.json" file?
            # 3. Contains an "analysis_renderer_attacker.json" file?
            # 4. Does the "analysis_renderer_attacker.json" file contain any dangers?
            # 5. Is the CS of the extension injected everywhere (according to the "analysis_renderer_attacker.json" file) ?
            if (
                dir_item.is_dir() and
                os.path.isfile(os.path.join(dir_item, "manifest.json")) and
                os.path.isfile(os.path.join(dir_item, f"{ANALYSIS_OUTFILE_NAME}.json"))
            ):
                analysis_file = os.path.join(dir_item, f"{ANALYSIS_OUTFILE_NAME}.json")
                analysis_result = AnalysisRendererAttackerJSON(path=analysis_file)
                # Only append if analysis_result contains at least 1 danger and if the extension's content script is
                #   injected everywhere (all the other ones we don't care about):
                total_danger_count: int = analysis_result.total_danger_count()
                danger_counts[dir_item.name] = total_danger_count
                if total_danger_count > 0:
                    if analysis_result.extension_cs_is_injected_everywhere():
                        subdirectory_names.append(dir_item.name)
                    else:
                        count_extension_cs_not_injected_everywhere += 1
    print(f"Info: {count_extension_cs_not_injected_everywhere} vulnerable extensions are not shown because their "
          f"content script is not injected everywhere. "
          f"{len(subdirectory_names)} vulnerable exploitable(!) extensions are left.")
    global no_of_ext_annotated
    global no_of_ext_to_annotate
    no_of_ext_annotated = 0
    no_of_ext_to_annotate = len(subdirectory_names)
    subdirectory_names.sort()
    for subdir_name in subdirectory_names:
        # In front of every extension subdirectory name, indicate the annotation state using a colored circle emoji:
        #   🔴 = no annotations yet
        #   🟡 = partially annotated
        #   🟢 = fully annotated
        #   🟣 = marks current selection (initially, no selection will be selected!)
        annotations: List[str] = annotations_csv.get_annotations(subdir_name)
        if len(annotations) == 0:
            circle_indicator = "🔴"
        elif len(annotations) == danger_counts[subdir_name]:
            circle_indicator = "🟢"
            no_of_ext_annotated += 1
        else:
            circle_indicator = "🟡"
        extensions_listbox.insert(tk.END, circle_indicator + " " + subdir_name)
    update_extensions_list_label()

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
    load_ext_into_chrome_frame = tk.Frame(center_button_frame)
    load_ext_into_chrome_frame.grid(row=0, column=2, padx=5, pady=5)
    tk.Button(load_ext_into_chrome_frame, text="Load ext. into Chrome...", command=on_load_ext_into_Chrome_click).grid(row=0, column=0)
    tk.Button(load_ext_into_chrome_frame, text="⛭", command=on_load_ext_into_Chrome_settings_button_click).grid(row=0, column=1)

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
        print("Usage: python3 gui_manual_vuln_verification.py <UNPACKED_FOLDER>")
        exit(1)
    elif not os.path.isdir(sys.argv[1]):
        print(f"Error: {sys.argv[1]} is not a directory!")
        exit(1)
    else:
        main()
