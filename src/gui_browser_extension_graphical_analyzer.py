from tkinter import *  # cf. https://www.geeksforgeeks.org/create-first-gui-application-using-python-tkinter/
from tkinter import ttk  # https://www.geeksforgeeks.org/creating-tabbed-widget-with-python-tkinter/
from tkinter.messagebox import showinfo  # https://blog.furas.pl/python-tkinter-how-to-create-popup-window-or-messagebox-gb.html
import webbrowser  # https://stackoverflow.com/questions/4216985/call-to-operating-system-to-open-url
from tkinter.filedialog import askopenfilename, askdirectory  # https://stackoverflow.com/questions/3579568/choosing-a-file-in-python-with-simple-dialog # https://stackoverflow.com/questions/10993089/opening-and-reading-a-file-with-askopenfilename
import os
import base64
from pathlib import Path  # https://stackoverflow.com/questions/2860153/how-do-i-get-the-parent-directory-in-python

from gui_generate_pdg import syntax_highlighting


def main():
    os.environ['PARSER'] = "espree"
    os.environ['SOURCE_TYPE'] = "module"

    # Tkinter root window:
    root = Tk()
    root.title("BEGA (Browser Extension Graphical Analyzer)")
    # root.geometry('600x400') # width x height

    # All widgets will be here:

    # ##### ##### ##### ##### ##### ##### #####
    # ##### "Open .crx file" #####
    # ##### ##### ##### ##### ##### ##### #####

    def open_crx_file():
        crx_file_path = askopenfilename(filetypes=[("Chromium extension","*.crx")]) # show an "Open" dialog box and return the path to the selected file
        if crx_file_path == "":
            print(f"User selected no file.")
        else:
            print(f"User selected file: '{crx_file_path}'")
            open_main_window(crx_file_path)

    btn1 = Button(root, text="Open .crx file", fg="black", command=open_crx_file)
    btn1.grid(column=0, row=0, padx=10, pady=10)

    # ##### ##### ##### ##### ##### ##### #####
    # ##### "Open unpacked Chrome extension" #####
    # ##### ##### ##### ##### ##### ##### #####

    def open_unpacked_chrome_extension():
        directory = askdirectory()
        if directory == "":
            print(f"User selected no directory.")
        else:
            print(f"User selected directory: '{directory}'")
            open_main_window(directory)

    btn2 = Button(root, text = "Open unpacked Chrome extension", fg = "black", command=open_unpacked_chrome_extension)
    btn2.grid(column=0, row=1, padx=10, pady=10)

    # ##### ##### ##### ##### ##### ##### ##### ##### ##### #####
    # ##### "Download Chrome extension based on extension ID:" #####
    # ##### ##### ##### ##### ##### ##### ##### ##### ##### #####

    extension_ID_text_field = Text(root, height=1, width=33)
    extension_ID_text_field.grid(column=0, row=4, padx=10, pady=10)

    def download_chrome_extension_based_on_extension_ID():
        extension_ID = extension_ID_text_field.get("1.0",'end-1c') # https://stackoverflow.com/questions/14824163/how-to-get-the-input-from-the-tkinter-text-widget
        if len(extension_ID) != 32 or not extension_ID.isalpha():
            showinfo("Incorrect Extension ID", f"'{extension_ID}' is not a valid Chrome extension ID. It must consist of exactly 32 letters.")
        else:
            url = "https://www.crx4chrome.com/search.php?s=" + extension_ID
            webbrowser.open(url, new=0, autoraise=True) # https://stackoverflow.com/questions/4216985/call-to-operating-system-to-open-url

    btn3 = Button(root, text="Download Chrome extension based on extension ID:", fg="black", command=download_chrome_extension_based_on_extension_ID)
    btn3.grid(column=0, row=3, padx=10, pady=10)

    # ##### ##### ##### #####
    # ##### Main window: #####
    # ##### ##### ##### #####

    def unpack_chrome_extension(crx_file_path, destination_folder):
        pass # ToDo

    def unpack_chrome_extension_for_doublex(crx_file_path, destination_folder):
        pass # ToDo

    def pack_chrome_extension(directory, destination_crx_file):
        pass # ToDo

    def open_main_window(extension_path):  # https://www.geeksforgeeks.org/open-a-new-window-with-a-button-in-python-tkinter/
        # Toplevel object which will be treated as a new window:
        mainWindow = Toplevel(root)
        mainWindow.title("BEGA (Browser Extension Graphical Analyzer)")

        # https://stackoverflow.com/questions/15981000/tkinter-python-maximize-window
        w, h = mainWindow.winfo_screenwidth(), mainWindow.winfo_screenheight()
        mainWindow.geometry("%dx%d+0+0" % (w, h))

        # Sometimes we might need the packed .crx file, sometimes we might need the unpacked extension directory, maybe even tool-specific:
        base64_id = str(base64.standard_b64encode(extension_path.encode('utf-8'))).replace("=", "_")  # Use base64-encoded user-specified path for creating uniquely named temp directories.
        path_packed_crx_file = ""
        path_unpacked_extension_directory = ""
        path_unpacked_extension_directory_doublex = ""
        # https://stackoverflow.com/questions/3204782/how-to-check-if-a-file-is-a-directory-or-regular-file-in-python
        if os.path.isfile(extension_path):  # ##### User gave file: #####
            path_packed_crx_file = extension_path
            path_unpacked_extension_directory = os.path.join(os.path.dirname(extension_path), '__bega_unpacked_extension_' + base64_id + "__")
            path_unpacked_extension_directory_doublex = os.path.join(os.path.dirname(extension_path), '__bega_unpacked_extension_doublex_' + base64_id + "__")
            unpack_chrome_extension(crx_file_path=extension_path, destination_folder=path_unpacked_extension_directory)
            unpack_chrome_extension_for_doublex(crx_file_path=extension_path, destination_folder=path_unpacked_extension_directory_doublex)
        elif os.path.isdir(extension_path):  # ##### User gave directory: #####
            path_packed_crx_file = os.path.join(Path(extension_path).parent.absolute(), '__bega_packed_extension_' + base64_id + ".crx")  # https://stackoverflow.com/questions/2860153/how-do-i-get-the-parent-directory-in-python
            path_unpacked_extension_directory = extension_path
            path_unpacked_extension_directory_doublex = os.path.join(Path(extension_path).parent.absolute(), '__bega_reunpacked_extension_doublex_' + base64_id + "__")
            pack_chrome_extension(directory=extension_path, destination_crx_file=path_packed_crx_file)
            # Re-unpack for DoubleX:
            unpack_chrome_extension_for_doublex(crx_file_path=path_packed_crx_file, destination_folder=path_unpacked_extension_directory_doublex)
        else:
            showinfo("Path not found", f"The path '{extension_path}' seems to be neither a file nor a directory.")

        # ToDo: delete temp files on exit; ???save temp files in a temp directory/in the home folder instead???

        # Widgets of new/main window:
        Label(mainWindow, text=f"Extension: {extension_path}").pack()
        # ToDo: add label(s) for name and version of the extension here, extracted from the manifest.json file!

        # Tab control: # https://www.geeksforgeeks.org/creating-tabbed-widget-with-python-tkinter/
        tabControl = ttk.Notebook(mainWindow)

        tab1 = ttk.Frame(tabControl)
        tab2 = ttk.Frame(tabControl)
        tab3 = ttk.Frame(tabControl)
        tab4 = ttk.Frame(tabControl)

        tabControl.add(tab1, text='Files')
        tabControl.add(tab2, text='AST')
        tabControl.add(tab3, text='Advanced Graphs')
        tabControl.add(tab4, text='Vulnerabilities')
        tabControl.pack(expand=1, fill="both")

        # ##### ##### ##### #####
        # ##### Tab 1: Files: #####
        # ##### ##### ##### #####

        # Dummy content: # ttk.Label(tab1, text ="Files").grid(column = 0, row = 0, padx = 30, pady = 30)

        tab1.grid_columnconfigure(0, weight=1) # https://stackoverflow.com/questions/68479586/divide-a-window-into-two-in-tkinter
        tab1.grid_columnconfigure(1, weight=1)
        tab1.grid_rowconfigure(0, weight=1)

        left_frame = Frame(tab1)  # , bg = "red"
        left_frame.grid(column=0, row=0, sticky="nesw")
        file_list = Listbox(left_frame)  # https://www.tutorialspoint.com/python/tk_listbox.htm
        file_list.pack(fill="both", expand=True)
        for file in os.listdir(path_unpacked_extension_directory):
            file_list.insert('end', file)
        # ToDo: color files depending on whether they are content scripts/background scripts/(sub-)directories
        # ToDo: handle directories!

        right_frame = Frame(tab1) # , bg = "green"
        right_frame.grid(column=1, row=0, sticky="nesw")
        file_text_field = Text(right_frame)
        file_text_field.pack(fill="both", expand=True)
        file_text_field.config(state=DISABLED)  # make text field read-only # https://stackoverflow.com/questions/3842155/is-there-a-way-to-make-the-tkinter-text-widget-read-only
        # ToDo: js-beautified! / auto-indented for the manifest.json!, including vulnerability-specific highlighting of dangerous APIs/sinks/etc.!!!

        # Syntax highlighting:
        def on_file_text_change(_event):
            # Check if the text was actually modified
            if file_text_field.edit_modified():
                syntax_highlighting(file_text_field)
                # Reset the modified flag to ensure the event is triggered again
                file_text_field.edit_modified(False)
        file_text_field.bind("<<Modified>>", on_file_text_change)

        def set_displayed_text(text):
            file_text_field.config(state=NORMAL)  # Of course the opposite of "DISABLED" is "NORMAL" ...
            file_text_field.delete(1.0, END)  # https://stackoverflow.com/questions/30957085/how-can-i-set-the-text-widget-contents-to-the-value-of-a-variable-in-python-tkin
            file_text_field.insert(END, text)
            file_text_field.config(state=DISABLED)
            # an absolute and utter absurdity...

        def js_beautify(file):
            pass # ToDo

        def display_file_content(file_name):
            f = os.path.join(path_unpacked_extension_directory, file_name)
            if os.path.isfile(f):
                try:
                    with open(f, "r") as file:
                        set_displayed_text(file.read())
                except Exception as error:
                    set_displayed_text(f"File read error: {error}")
            elif os.path.isdir(f):
                set_displayed_text(f"'{file_name}' is a directory.")
            else:
                set_displayed_text(f"Error: '{file_name}' is neither a file nor a directory.")

        def onselect(event): # https://stackoverflow.com/questions/6554805/getting-a-callback-when-a-tkinter-listbox-selection-is-changed
            w = event.widget
            index = int(w.curselection()[0])
            value = w.get(index)
            print('User selected list item %d: "%s"' % (index, value))
            display_file_content(value)

        file_list.bind('<<ListboxSelect>>', onselect)

        # ##### ##### ##### #####
        # ##### Tab 2: AST: #####
        # ##### ##### ##### #####

        ttk.Label(tab2, text="AST").grid(column=0, row=0, padx=30, pady=30) # ToDo: call Esprima (once user clicks a "Generate AST" button) and show AST (including some stats on # of nodes/edges/leaves/...) here, also allow the execution of graph queries on the AST

        # ##### ##### ##### ##### ##### #####
        # ##### Tab 3: Advanced Graphs: #####
        # ##### ##### ##### ##### ##### #####

        ttk.Label(tab3, text="Advanced Graphs").grid(column=0, row=0, padx=30, pady=30) # ToDo

        # ##### ##### ##### ##### ##### #####
        # ##### Tab 4: Vulnerabilities: #####
        # ##### ##### ##### ##### ##### #####

        ttk.Label(tab4, text="Vulnerabilities").grid(column=0, row=0, padx=30, pady=30) # ToDo

    # Execute Tkinter:
    root.mainloop()


if __name__ == "__main__":
    main()
