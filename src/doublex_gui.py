# On macOS, when using system-wide Dark mode, you will have to disable it for Python using this command:
# $ defaults write org.python.python NSRequiresAquaSystemAppearance -boolean true
if __name__ == "__main__":
    with open("doublex.py", "r") as f:
        python_code = f.read()
        python_code = python_code.replace("def main():", "@Gooey("
                                                         "program_name='DoubleX',"
                                                         "body_bg_color='white',"
                                                         "header_bg_color='gray',"
                                                         "terminal_panel_color='white',"
                                                         "terminal_font_color='black'"
                                                         ")\n"
                                                         "def main():")
        python_code = "from gooey import Gooey\n" + python_code
        exec(python_code)
