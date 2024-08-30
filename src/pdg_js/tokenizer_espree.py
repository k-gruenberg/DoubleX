# cf. get_extended_ast() function in build_ast.py
import json
import logging
import os
import subprocess
import tempfile

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def tokenize(js_code): # ToDo
    """
    Returns the tokenization of the given JavaScript code.
    Unlike parsing, tokenization is faster and robust to syntax errors.
    Ideal for syntax highlighting.
    Returns `None` on error.
    """
    input_file = tempfile.NamedTemporaryFile()
    with open(input_file.name, 'w') as f:
        f.write(js_code)

    json_path = tempfile.NamedTemporaryFile()  # Path of the JSON file to temporary store the AST in.

    try:
        produce_ast = subprocess.run(['node', os.path.join(SRC_PATH, f"tokenizer_espree.js"),
                                      input_file.name, json_path.name, os.environ['SOURCE_TYPE']],
                                     stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        logging.critical(f"tokenize(): Espree tokenization error")
        return None

    if produce_ast.returncode == 0:

        with open(json_path.name) as json_data:
            json_result = json.loads(json_data.read())
        os.remove(json_path.name)

        return json_result

    logging.critical('tokenize(): Espree could not produce a tokenization')
    return None
