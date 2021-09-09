## Sensitive APIs that could lead to vulnerabilities if controlled by an attacker.


`doublex_apis.json`: APIs considered by DoubleX.  
`empoweb_apis.json`: APIs for the ground-truth evaluation, based on the EmPoWeb paper.

By default, we consider the DoubleX selected APIs for which an extension **has the corresponding permissions** (i.e., all APIs from `doublex_apis.json` for which an extension has the corresponding permissions).


Note: it is possible to define a custom list of APIs (in a JSON file) and give it as input to `doublex` (parameter `--apis`).  
The format of a custom list of APIs is the following (see another example in `custom.json`):

```
{
  "cs": {
    "direct_dangers": {
      "CATEGORY1": [
        "API1",
        "API2"
      ]
    },
    "indirect_dangers": {},
    "exfiltration_dangers": {}
  },
  "bp": {
    "direct_dangers": {},
    "indirect_dangers": {},
    "exfiltration_dangers": {}
  }
}
```

cs["direct_dangers"]: Content Script sinks: we will look for attacker-controllable data going into these sinks.

cs["indirect_dangers"]: Content Script sinks+sources: we will look for attacker-controllable data going into these APIs and the results being sent back to an attacker.


bp["direct_dangers"]: Background Page sinks: we will look for attacker-controllable data going into these sinks.

bp["indirect_dangers"]: Background Page sinks+sources: we will look for attacker-controllable data going into these APIs and the results being sent back to an attacker.

bp["exfiltration_dangers"]: Background Page sources: we will look for data going out of these sensitive sources and sent to an attacker.
