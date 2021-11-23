# pdg_js

Statically building the enhanced AST (with control and data flow, as well as pointer analysis information) for JavaScript inputs (sometimes referred to as PDG).


## Setup (if not already done for DoubleX)

```
install python3 # (tested with 3.7.3 and 3.7.4)

install nodejs
install npm
cd src/pdg_js
npm install esprima # (tested with 4.0.1)
npm install escodegen # (tested with 1.14.2 and 2.0.0)
cd ..
```

To install graphviz (only for drawing graphs, not yet documented, please open an issue if interested)
```
pip3 install graphviz
On MacOS: install brew and then brew install graphviz
On Linux: sudo apt-get install graphviz
```

## Usage

### PDG Generation - Multiprocessing

Let's consider a directory `EXTENSIONS` containing several extension's folders. For each extension, their corresponding folder contains *.js files for each component. We would like to generate the PDGs (= ASTs enhanced with control and data flow, and pointer analysis) of each file. For each extension, the corresponding PDG will be stored in the folder `PDG`.  
To generate these PDGs, launch the following shell command from the `pdg_js` folder location:
```
$ python3 -c "from build_pdg import store_extension_pdg_folder; store_extension_pdg_folder('EXTENSIONS')"
```

The corresponding PDGs will be stored in EXTENSIONS/\<extension\>/PDG`.

Currently, we are using 1 CPU, but you can change that by modifying the variable NUM\_WORKERS from `pdg_js/utility_df.py` (the one **line 51**).


### Single PDG Generation

To generate the PDG of a specific *.js file, launch the following python3 commands from the `pdg_js` folder location:
```
>>> from build_pdg import get_data_flow
>>> pdg = get_data_flow('INPUT_FILE', benchmarks=dict())
```

Per default, the corresponding PDG will not be stored. To store it in an **existing** PDG\_PATH folder, call:
```
$ python3 -c "from build_pdg import get_data_flow; get_data_flow('INPUT_FILE', benchmarks=dict(), store_pdgs='PDG_PATH')"
```


Note that we added a timeout of 10 min for the data flow/pointer analysis (cf. line 149 of `pdg_js/build_pdg.py`), and a memory limit of 20GB (cf. line 115 of `pdg_js/build_pdg.py`).