// Copyright (C) 2021 Aurore Fass
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.


// Conversion of a JS file into its Esprima AST.


module.exports = {
    js2ast: js2ast,
};


var esprima = require("esprima");
var es = require("escodegen");
var fs = require("fs");
var process = require("process");


/**
 * Extraction of the AST of an input JS file using Esprima.
 *
 * @param js input file (.js)
 * @param json_path output file (.json)
 * @param source_type "script" or "module", no(!) "commonjs"; please use the value os.environ['SOURCE_TYPE'] (Python)
 * @returns {*}
 */
function js2ast(js, json_path, source_type) {
    var text = fs.readFileSync(js).toString('utf-8');
    try {
        if (source_type === "script") {
            var ast = esprima.parseScript(text, {
                range: true,
                loc: true,
                tokens: true,
                tolerant: true,
                comment: true
            });
        } else if (source_type === "module") {
            var ast = esprima.parseModule(text, { // <=== THIS IS WHAT THE ORIGINAL DOUBLEX USED!
                range: true,
                loc: true,
                tokens: true,
                tolerant: true,
                comment: true
            });
        } else {
            console.error("Esprima only supports 'script' and 'module' source types.");
            process.exit(1);
        }
    } catch(e) {
        console.error(js, e);
        process.exit(1);
    }

    // Attaching comments is a separate step for Escodegen
    ast = es.attachComments(ast, ast.comments, ast.tokens);

    fs.writeFile(json_path, JSON.stringify(ast), function (err) {
        if (err) {
            console.error(err);
        }
    });

    return ast;
}

js2ast(process.argv[2], process.argv[3], process.argv[4]);
