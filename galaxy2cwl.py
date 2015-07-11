import xml.dom.minidom
import argparse
import pprint
import os
import yaml
import sys

# def literal_unicode_representer(dumper, data):
#     if '\n' in data:
#         return dumper.represent_scalar(u'tag:yaml.org,2002:str', data, style='|')
#     else:
#         return dumper.represent_scalar(u'tag:yaml.org,2002:str', data)

# yaml.add_representer(unicode, literal_unicode_representer)
# yaml.add_representer(str, literal_unicode_representer)

def uniq(names, n):
    stem = n
    i = 1
    while n in names:
        i += 1
        n = stem + str(i)
    names.add(n)
    return n

def inpschema(elm, expands, names, top=False):
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
                f = {"type": "record", "name": uniq(names, when.getAttribute("value"))}
                f["fields"] = inpschema(when, expands, names)
                f["fields"].append({
                    "name": e.getElementsByTagName("param")[0].getAttribute("name"),
                    "type": {
                        "type": "enum",
                        "symbols": [when.getAttribute("value")],
                        "name": uniq(names, when.getAttribute("value"))
                    }
                })
                sch["type"].append(f)

            schema.append(sch)

        elif e.tagName == "param":
            sch = {}

            if top:
                sch["id"] = "#" + e.getAttribute("name")
            else:
                sch["name"] = e.getAttribute("name")

            sch["label"] = e.getAttribute("label")

            if e.getAttribute("type") == "data":
                sch["type"] = "File"
            elif e.getAttribute("type") == "select":
                en = {
                    "type": "enum",
                    "name": uniq(names, e.getAttribute("name"))
                }
                en["symbols"] = []
                for opt in e.getElementsByTagName("option"):
                    en["symbols"].append(opt.getAttribute("value"))
                if len(en["symbols"]) == 0:
                    sch = None
                else:
                    sch["type"] = en
            elif e.getAttribute("type") == "text":
                sch["type"] = "string"
            elif e.getAttribute("type") == "integer":
                sch["type"] = "int"
            else:
                sch["type"] = "Any"

            if sch:
                if e.getAttribute("optional") == "True":
                    sch["type"] = ["null", sch["type"]]
                if e.getAttribute("value"):
                    sch["default"] = e.getAttribute("value")
                    if sch["type"] == "int":
                        sch["default"] = int(sch["default"])

                schema.append(sch)

        elif e.tagName == "expand":
            m = inpschema(expands[e.getAttribute("macro")], expands, names, top=top)
            schema.extend(m)

    return schema

def outschema(inputs, elm, expands, names, top=False):
    schema = []

    for e in elm.childNodes:
        if not isinstance(e, xml.dom.minidom.Element):
            continue

        if e.tagName == "data":
            sch = {}
            if e.getAttribute("from_work_dir"):
                u = e.getAttribute("from_work_dir")
            else:
                u = e.getAttribute("name")

            inputs.append({
                "id": "#" + uniq(names, e.getAttribute("name")),
                "type": "string",
                "default": u
            })

            schema.append({
                "id": "#" + uniq(names, e.getAttribute("name")),
                "type": "File",
                "outputBinding": {
                    "glob": u
                }
            })

    return schema


def macros(basedir, elm, toks, expands):
    for imp in elm.getElementsByTagName("import"):
        macros(basedir, xml.dom.minidom.parse(os.path.join(basedir, imp.firstChild.data)).documentElement, toks, expands)
    for tok in elm.getElementsByTagName("token"):
        toks[tok.getAttribute("name")] = tok.firstChild.data
    for x in elm.getElementsByTagName("xml"):
        expands[x.getAttribute("name")] = x

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

    cwl["requirements"] = [{
        "class": "ExpressionEngineRequirement",
        "id": "#galaxy_command_line",
        "engineCommand": "./galaxy-command-line.py"
    },
    {
        "class": "ExpressionEngineRequirement",
        "id": "#galaxy_template",
        "engineCommand": "./galaxy-template.py"
    },
    {
        "class": "EnvVarRequirement",
        "envDef": [{
            "envName": "GALAXY_SLOTS",
            "envValue": ""
        }]
    }]

    interpreter = tool.getElementsByTagName("command")[0].getAttribute("interpreter")

    cwl["arguments"] = [{
        "valueFrom": {
            "engine": "#galaxy_command_line",
            "script": interpreter + tool.getElementsByTagName("command")[0].firstChild.data
            }
        }]

    toks = {}
    expands = {}
    names = set()
    macros(basedir, tool.getElementsByTagName("macros")[0], toks, expands)

    #pprint.pprint(toks)
    #pprint.pprint(expands)

    cwl["inputs"] = inpschema(tool.getElementsByTagName("inputs")[0], expands, names, top=True)
    cwl["outputs"] = outschema(cwl["inputs"], tool.getElementsByTagName("outputs")[0], expands, names, top=True)

    yaml.safe_dump([cwl], sys.stdout, encoding="utf-8")

main()
