import xml.dom.minidom
import argparse
import pprint
import os

def dictify(elm):
    d = {}
    for i in xrange(0, elm.attributes.length):
        attr = elm.attributes.item(i)
        d[attr.name] = attr.value
    for i in elm.childNodes:
        if isinstance(i, xml.dom.minidom.Element):
            if i.tagName not in d:
                d[i.tagName] = []
            if len(i.childNodes) == 1 and isinstance(i.firstChild, xml.dom.minidom.Text):
                if i.attributes.length == 0:
                    d[i.tagName].append(i.firstChild.data)
                else:
                    d[i.tagName].append(dictify(i))
                    d[i.tagName][-1]["data"] = i.firstChild.data
            else:
                d[i.tagName].append(dictify(i))

    return d

def inpschema(elm, expands, top=False):
    schema = []

    for cond in elm.get("conditional", []):
        sch = {}
        if top:
            sch["id"] = "#" + cond["name"]
        else:
            sch["name"] = cond["name"]

        sch["type"] = []

        for when in cond["when"]:
            f = {"type": "record", "name": when["value"]}
            f["fields"] = inpschema(when, expands)
            f["fields"].append({
                "name": cond["param"][0]["name"],
                "type": "enum",
                "symbols": [when["value"]]
                })
            sch["type"].append(f)

        schema.append(sch)

    for param in elm.get("param", []):
        sch = {}

        if top:
            sch["id"] = "#" + param["name"]
        else:
            sch["name"] = param["name"]

        sch["label"] = param.get("label")

        if param["type"] == "data":
            sch["type"] = "File"
        elif param["type"] == "select":
            e = {"type": "enum"}
            e["symbols"] = []
            for opt in param.get("option", []):
                e["symbols"].append(opt["value"])
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
                sch["default"] = param.get("value")
                if sch["type"] == "int":
                    sch["default"] = int(sch["default"])

            schema.append(sch)

    for ex in elm.get("expand", []):
        schema.extend(inpschema(expands[ex["macro"]], expands))

    return schema

def macros(basedir, elm, toks, expands):
    for imp in elm.get("import", []):
        macros(basedir, dictify(xml.dom.minidom.parse(os.path.join(basedir, imp)).documentElement), toks, expands)
    for tok in elm.get("token", []):
        toks[tok["name"]] = tok["data"]
    for x in elm.get("xml", []):
        expands[x["name"]] = x

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tool', type=str)
    args = parser.parse_args()

    basedir = os.path.dirname(args.tool)

    dom = xml.dom.minidom.parse(args.tool)

    tool = dictify(dom.documentElement)

    cwl = {"class":"CommandLineTool"}

    cwl["id"] = "#" + tool["id"]
    cwl["label"] = tool["name"]

    cwl["baseCommand"] = ["/bin/sh", "-c"]

    if "interpreter" in tool["command"][0]:
        interpreter = tool["command"][0]["interpreter"] + " "
    else:
        interpreter = ""

    cwl["arguments"] = [{
        "valueFrom": {
            "engine": "#cheetah",
            "script": interpreter + tool["command"][0]
            }
        }]

    cwl["inputs"] = []

    toks = {}
    expands = {}
    macros(basedir, tool["macros"][0], toks, expands)

    #pprint.pprint(toks)
    #pprint.pprint(expands)

    cwl["inputs"].extend(inpschema(tool["inputs"][0], expands, top=True))

    pprint.pprint(cwl)

main()
