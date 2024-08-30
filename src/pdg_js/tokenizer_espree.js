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


// Conversion of a JS file into its Espree AST.


module.exports = {
    js2ast: js2ast,
};


const espree = require("espree"); // cf. README on https://github.com/eslint/espree/tree/main/packages/espree
var es = require("escodegen");
var fs = require("fs");
var process = require("process");


/**
 * Extraction of the AST of an input JS file using Espree.
 *
 * @param js input file (.js)
 * @param json_path output file (.json)
 * @param source_type either "script", "module", or "commonjs"; please use the value os.environ['SOURCE_TYPE'] (Python)
 * @returns {*}
 */
function js2ast(js, json_path, source_type) {
    var text = fs.readFileSync(js).toString('utf-8');
    try {
        var tokens = espree.tokenize(text, {
            range: true,
            loc: true,
            tokens: true,
            tolerant: true,
            comment: true,
            ecmaVersion: "latest", // (!!!) VERY IMPORTANT TO SET; DEFAULT=5 (!!!)
            sourceType: source_type
            // Some extensions can only be parsed WITH sourceType: "module", while others can only be parsed WITHOUT it!
            // => cf. https://github.com/eslint/espree/tree/main/packages/espree - Section "Options"
        });
    } catch(e) {
        console.error(js, e);
        process.exit(1);
    }

    // // Attaching comments is a separate step for Escodegen
    // ast = es.attachComments(ast, ast.comments, ast.tokens);

    fs.writeFile(json_path, JSON.stringify(tokens), function (err) {
        if (err) {
            console.error(err);
        }
    });

    return tokens;
}

js2ast(process.argv[2], process.argv[3], process.argv[4]);
