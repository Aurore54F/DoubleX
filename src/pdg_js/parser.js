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
 * @param js
 * @param json_path
 * @returns {*}
 */
function js2ast(js, json_path) {
    var text = fs.readFileSync(js).toString('utf-8');
    try {
        var ast = esprima.parseModule(text, {
            range: true,
            loc: true,
            tokens: true,
            tolerant: true,
            comment: true
        });
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

js2ast(process.argv[2], process.argv[3]);
