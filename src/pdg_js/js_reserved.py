# Copyright (C) 2021 Aurore Fass
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""
    JavaScript reserved keywords or words known by the interpreter.
"""

# Note: slightly improved from HideNoSeek (browser extension keywords)


RESERVED_WORDS = ["abstract", "arguments", "await", "boolean", "break", "byte", "case", "catch",
                  "char", "class", "const", "continue", "debugger", "default", "delete", "do",
                  "double", "else", "enum", "eval", "export", "extends", "false", "final",
                  "finally", "float", "for", "function", "goto", "if", "implements", "import", "in",
                  "instanceof", "int", "interface", "let", "long", "native", "new", "null",
                  "package", "private", "protected", "public", "return", "short", "static", "super",
                  "switch", "synchronized", "this", "throw", "throws", "transient", "true", "try",
                  "typeof", "var", "void", "volatile", "while", "with", "yield", "Array",
                  "Date", "eval", "function", "hasOwnProperty", "Infinity", "isFinite", "isNaN",
                  "isPrototypeOf", "length", "Math", "NaN", "name", "Number", "Object", "prototype",
                  "String", "toString", "undefined", "valueOf", "getClass", "java", "JavaArray",
                  "javaClass", "JavaObject", "JavaPackage", "alert", "all", "anchor", "anchors",
                  "area", "assign", "blur", "button", "checkbox", "clearInterval", "clearTimeout",
                  "clientInformation", "close", "closed", "confirm", "constructor", "crypto",
                  "decodeURI", "decodeURIComponent", "defaultStatus", "document", "element",
                  "elements", "embed", "embeds", "encodeURI", "encodeURIComponent", "escape",
                  "event", "fileUpload", "focus", "form", "forms", "frame", "innerHeight",
                  "innerWidth", "layer", "layers", "link", "location", "mimeTypes", "navigate",
                  "navigator", "frames", "frameRate", "hidden", "history", "image", "images",
                  "offscreenBuffering", "open", "opener", "option", "outerHeight", "outerWidth",
                  "packages", "pageXOffset", "pageYOffset", "parent", "parseFloat", "parseInt",
                  "password", "pkcs11", "plugin", "prompt", "propertyIsEnum", "radio", "reset",
                  "screenX", "screenY", "scroll", "secure", "select", "self", "setInterval",
                  "setTimeout", "status", "submit", "taint", "text", "textarea", "top", "unescape",
                  "untaint", "window", "onblur", "onclick", "onerror", "onfocus", "onkeydown",
                  "onkeypress", "onkeyup", "onmouseover", "onload", "onmouseup", "onmousedown",
                  "onsubmit",
                  "define", "exports", "require", "each", "ActiveXObject", "console", "module",
                  "Error", "TypeError", "RangeError", "RegExp", "Symbol", "Set"]


BROWSER_EXTENSIONS = ['addEventListener', 'browser', 'chrome', 'localStorage', 'postMessage',
                      'Promise', 'JSON', 'XMLHttpRequest', '$', 'screen', 'CryptoJS']

KNOWN_WORDS_LOWER = [word.lower() for word in RESERVED_WORDS + BROWSER_EXTENSIONS]
