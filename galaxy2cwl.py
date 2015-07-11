import xml.dom.minidom
import argparse
import pprint
import os

def inpschema(elm, expands, top=False):
    schema = []

    for e in elm.childNodes:
        if not isinstance(e, xml.dom.minidom.Element):
            continue
        if e.tagName == "conditional":
            sch = {}
            if top:
                sch["id"] = "#" + e.getAttribute("name")
            else:
                sch["name"] = e.getAttribute("name")

            sch["type"] = []

            for when in e.getElementsByTagName("when"):
                f = {"type": "record", "name": when.getAttribute("value")}
                f["fields"] = inpschema(when, expands)
                f["fields"].append({
                    "name": e.getElementsByTagName("param")[0].getAttribute("name"),
                    "type": "enum",
                    "symbols": [when.getAttribute("value")]
                    })
                sch["type"].append(f)

            schema.append(sch)

        elif e.tagName == "cond":
            sch = {}

            if top:
                sch["id"] = "#" + e.getAttribute("name")
            else:
                sch["name"] = e.getAttribute("name")

            sch["label"] = e.getAttribute("label")

            if param["type"] == "data":
                sch["type"] = "File"
            elif param["type"] == "select":
                e = {"type": "enum"}
                e["symbols"] = []
                for opt in e.getElementsByTagName("option"):
                    e["symbols"].append(opt.getAttribute("value"))
                if len(e["symbols"]) == 0:
                    sch = None
                else:
                    sch["type"] = e
            elif param["type"] == "text":
                sch["type"] = "string"
            elif param["type"] == "integer":
                sch["type"] = "int"
            else:
                sch["type"] = "Any"

            if sch:
                if param.get("optional") == "True":
                    sch["type"] = ["null", sch["type"]]
                if param.get("value"):
                    sch["default"] = e.getAttribute("value")
                    if sch["type"] == "int":
                        sch["default"] = int(sch["default"])

                schema.append(sch)

        elif e.tagName == "expand":
            schema.extend(inpschema(expands[e.getAttribute("macro")], expands))

    return schema

def macros(basedir, elm, toks, expands):
    for imp in elm.getElementsByTagName("import"):
        macros(basedir, xml.dom.minidom.parse(os.path.join(basedir, imp.firstChild.data)).documentElement, toks, expands)
    for tok in elm.getElementsByTagName("token"):
        toks[tok.getAttribute("name")] = tok.firstChild.data
    for x in elm.getElementsByTagName("xml"):
        expands[x.getAttribute("name")] = elm

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tool', type=str)
    args = parser.parse_args()

    basedir = os.path.dirname(args.tool)

    dom = xml.dom.minidom.parse(args.tool)

    tool = dom.documentElement

    cwl = {"class":"CommandLineTool"}

    cwl["id"] = "#" + tool.getAttribute("id")
    cwl["label"] = tool.getAttribute("name")

    cwl["baseCommand"] = ["/bin/sh", "-c"]

    interpreter = tool.getElementsByTagName("command")[0].getAttribute("interpreter")

    cwl["arguments"] = [{
        "valueFrom": {
            "engine": "#cheetah",
            "script": interpreter + tool.getElementsByTagName("command")[0].firstChild.data
            }
        }]

    cwl["inputs"] = []

    toks = {}
    expands = {}
    macros(basedir, tool.getElementsByTagName("macros")[0], toks, expands)

    #pprint.pprint(toks)
    #pprint.pprint(expands)

    cwl["inputs"].extend(inpschema(tool.getElementsByTagName("inputs")[0], expands, top=True))

    pprint.pprint(cwl)

main()
