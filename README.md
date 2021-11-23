# DoubleX: Statically Detecting Vulnerable Data Flows in Browser Extensions at Scale

This repository contains the code for the [CCS'21 paper: "DoubleX: Statically Detecting Vulnerable Data Flows in Browser Extensions at Scale"](https://swag.cispa.saarland/papers/fass2021doublex.pdf).  
Please note that in its current state, the code is a Poc and not a fully-fledged production-ready API.


## Summary
DoubleX statically detects vulnerable data flows in a browser extension:
- Definition and construction of an Extension Dependence Graph (EDG), i.e., semantic abstraction of extension code (including control and data flows, and pointer analysis) and model of the message interactions within and outside of an extension.
- Data flow analysis to track data from and toward security- and privacy-critical APIs in browser extensions (e.g., `tabs.executeScript`, `downloads.download`, or `topSites.get`).


## Setup

```
install python3 # (tested with 3.7.3 and 3.7.4)
install nodejs
install npm
cd src
npm install esprima # (tested with 4.0.1)
npm install escodegen # (tested with 1.14.2 and 2.0.0)
npm -g install js-beautify
```

To install graphviz (only for drawing graphs, not yet documented, please open an issue if interested)
```
pip3 install graphviz
On MacOS: install brew and then brew install graphviz
On Linux: sudo apt-get install graphviz
```


## Usage

DoubleX can analyze both Chromium-based and Firefox extensions.

### Unpack a Chrome Extension

If you already have extracted the content scripts, background scripts/page, WARs, and manifest, directly move on to the next section `Chrome Extensions`. Otherwise, you can extract these components from a packed extension `CRX_PATH` and store them in `UNPACKED_PATH/extension_name` by running the following command:
```
python3 src/unpack_extension.py -s 'CRX_PATH' -d 'UNPACKED_PATH'
```


### Chrome Extensions

To analyze a Chrome extension with the content script `CONTENT_SCRIPT` and background page `BACKGROUND_PAGE`, run the following command:
```
python3 src/doublex.py -cs 'CONTENT_SCRIPT' -bp 'BACKGROUND_PAGE'
```

By default, DoubleX will consider that the extension `manifest.json` file is located in the same directory as the content script. A custom manifest location can be specified with the `--manifest` command:
```
python3 src/doublex.py -cs 'CONTENT_SCRIPT' -bp 'BACKGROUND_PAGE' --manifest 'CUSTOM_MANIFEST_PATH'
```

For performance reasons, you can generate the PDGs of the content script and background page beforehand. In this case, see the README in `src/pdg_js` and call the function `src/vulnerability_detection/analyze_extension` with 1) the path of the content script's PDG, 2) the path of the background page's PDG, and 3) the attribute `pdg` with the value True.

Note: DoubleX can also analyze Firefox extensions (i.e., not Chromium-based). In this case, add the parameter `--not-chrome`:
```
python3 src/doublex.py -cs 'CONTENT_SCRIPT' -bp 'BACKGROUND_PAGE' --not-chrome
```


### Output of the Analysis

Calling the main function `doublex` does not return anything but will generate 2 JSON files:
1) `extension_doublex_apis.json`, stored in the content script's folder. This JSON file indicates the sensitive APIs that were analyzed for a given extension, based on its permissions (cf. §4.4.1 and §4.4.2 of the paper). Specifically, if the extension has all corresponding permissions, all APIs from Table 5 in the Appendix would be considered. Note that the list of APIs to analyze can be changed (cf. below).
2) `analysis.json`, stored in the content script's folder (configurable with the parameter `--analysis`). This JSON file summarizes DoubleX data flow reports for the analyzed extension (cf. §4.4.3). In particular, this file indicates the sensitive APIs that were detected in the extension and whether DoubleX reported a suspicious data flow or not.
Our data flow reports indicate in which component a sensitive API was detected and, in the case of a detected suspicious data flow, the component that received/sent a message from/to an external actor. Therefore, if DoubleX detects, e.g., a sensitive API in the background page and a data flow between this API and an attacker-controllable message received in the content script, it means that DoubleX detected that the content script forwarded the message (or parts of the message) to the background page.  
Note: DoubleX reports a suspicious data flow when `"dataflow": true` in the analysis JSON file. If `"dataflow": false` it just means that DoubleX detected a suspicious API but without an attacker-controllable flow / data exfiltration to an attacker.


### Case of Web Accessible Resources (WARs)

Instead of background pages, it is also possible to consider Web Accessible Resources (`WAR`).
The WARs are handled slightly differently from background pages (due to their communication with the web application, cf. §2.2 of the paper); therefore, they should be given as parameter instead of the background page with the additional `--war` parameter:
```
python3 src/doublex.py -cs 'CONTENT_SCRIPT' -bp 'WAR' --war
```

### Sensitive APIs Considered

Finally, it is possible to change the sensitive APIs analyzed. By default, we consider the DoubleX selected APIs for which an extension **has the corresponding permissions** (default is: `--apis 'permissions'`).  
To run DoubleX on our ground-truth dataset and compare with EmPoWeb's findings on this dataset, the APIs to consider should be explicitly indicated with `--apis 'empoweb'` (cf. §5.4 of the paper). Note: this setting should *only* be used for the EmPoWeb comparison on the ground-truth dataset. For all other experiments, please use `--apis 'permissions'` (or simply omit this parameter).


## Examples

As an illustration of DoubleX's capabilities (e.g., aliasing, APIs not written in plain text, dynamic sink invocations, message forwarding between extension components, or confused deputy), we wrote some custom examples in the `examples` folder:

- `examples/listing4/` contains the vulnerable content script example from Listing 4 of the paper. The analysis can be run with:
```
python3 src/doublex.py -cs 'examples/listing4/contentscript.js' -bp 'examples/listing4/background.js'
```
Two files will be generated in `examples/listing4/`, namely `extension_doublex_apis.json` (i.e., sensitive APIs for which the extension has the corresponding permissions) and `analysis.json` (i.e., DoubleX data flow reports). The expected results are in the `expected` folder.  
As discussed in §4.4.2 and §4.4.3, DoubleX correctly detects the two calls to `eval` (despite dynamic invocation for the first one) and correctly flags only the first one as attacker controllable.

- `examples/alias/` contains an example with aliasing (as discussed in §5.3 of the paper). The analysis can be run with:
```
python3 src/doublex.py -cs 'examples/alias/contentscript.js' -bp 'examples/alias/background.js'
```
In particular, DoubleX accurately detects the message-passing API in the content script, despite aliasing. This can be read from the following lines of the analysis file: 1) lines 12-16: the sensitive API `eval` was detected in the background page, 2) line 17: a suspicious data flow (i.e., attacker-controlled) is going into `eval`, and 3) lines 19-24: this attacker-controllable data was received line 2 of the content script. Since there is a data flow from attacker-controlled data in the content script to `eval` in the background page, this means that DoubleX correctly detected the fact that the content script forwarded this attacker-controllable message to the background.

- `examples/dynamic-invocation/` contains an example with a dynamic sink invocation (as discussed in §4.4.2 of the paper). The analysis can be run with:
```
python3 src/doublex.py -cs 'examples/dynamic-invocation/contentscript.js' -bp 'examples/dynamic-invocation/background.js'
```
As previously, DoubleX detects that the content script forwards an attacker-controllable message to the background (as indicated in the analysis file: message received in the content script but sink invoked in the background). In addition, DoubleX pointer analysis module correctly computes and identifies the call to "chrome.tabs.executeScript(attackerData)" in the background page (string concatenation and detection of the dynamic invocation with the bracket notation, similarly to the example of §4.4.2).

- `examples/externally-connectable/` is a Confused Deputy example, i.e., this extension can be exploited by any extension, as it does not specify the `externally_connectable` entry in its manifest (as discussed in §2.2 and §3 of the paper). The analysis can be run with:
```
python3 src/doublex.py -cs 'examples/externally-connectable/contentscript.js' -bp 'examples/externally-connectable/background.js'
```
As indicated in the analysis file, this extension exfiltrates a user's browsing history.


## Vulnerable Extensions Detected

We can provide a list of the 184 vulnerable extensions we detected, their source code, as well as DoubleX generated reports upon request (in this case, please send me an email).


## Ground-Truth Extension Set

We can provide a list of the 73 ground-truth vulnerable extensions from the EmPoWeb paper that were still vulnerable in March 2021, their source code, as well as DoubleX generated reports upon request (in this case, please send me an email).


## Cite this work
If you use DoubleX for academic research, you are highly encouraged to cite the following [paper](https://swag.cispa.saarland/papers/fass2021doublex.pdf):
```
@inproceedings{fass2021doublex,
    author="Aurore Fass and Doli{\`e}re Francis Som{\'e} and Michael Backes and Ben Stock",
    title="{\textsc{DoubleX}: Statically Detecting Vulnerable Data Flows in Browser Extensions at Scale}",
    booktitle="ACM CCS",
    year="2021"
}
```

### Abstract:

Browser extensions are popular to enhance users' browsing experience. By design, they have access to security- and privacy-critical APIs to perform tasks that web applications cannot traditionally do. Even though web pages and extensions are isolated, they can communicate through messages. Specifically, a vulnerable extension can receive messages from another extension or web page, under the control of an attacker. Thus, these communication channels are a way for a malicious actor to elevate their privileges to the capabilities of an extension, which can lead to, e.g., universal cross-site scripting or sensitive user data exfiltration. To automatically detect such security and privacy threats in benign-but-buggy extensions, we propose our static analyzer DoubleX. DoubleX defines an Extension Dependence Graph (EDG), which abstracts extension code with control and data flows, pointer analysis, and models the message interactions within and outside of an extension. This way, we can leverage this graph to track and detect suspicious data flows between external actors and sensitive APIs in browser extensions.

We evaluated DoubleX on 154,484 Chrome extensions, where it flags 278 extensions as having a suspicious data flow. Overall, we could verify that 89% of these flows can be influenced by external actors (i.e., an attacker). Based on our threat model, we subsequently demonstrate exploitability for 184 extensions. Finally, we evaluated DoubleX on a labeled vulnerable extension set, where it accurately detects almost 93% of known flaws.


## License

This project is licensed under the terms of the AGPL3 license, which you can find in ```LICENSE```.