#!/usr/bin/env python

import xml.dom.minidom
import argparse
import pprint
import os
import yaml
import sys
import stat
import json
import hashlib

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
        if e.nodeType != xml.dom.Node.ELEMENT_NODE:
            continue

        if e.tagName == "conditional":
            sch = {}
            if top:
                sch["id"] = "#" + e.getAttribute("name")
            else:
                sch["name"] = e.getAttribute("name")

            sch["type"] = []

            param = e.getElementsByTagName("param")[0]
            default = None
            for opt in param.getElementsByTagName("option"):
                if opt.getAttribute("selected").lower() == "true":
                    sch["default"] = {
                        param.getAttribute("name"): opt.getAttribute("value")
                    }

            for when in e.getElementsByTagName("when"):
                f = {"type": "record", "name": uniq(names, when.getAttribute("value"))}
                f["fields"] = inpschema(when, expands, names)
                f["fields"].append({
                    "name": param.getAttribute("name"),
                    "type": {
                        "type": "enum",
                        "symbols": [when.getAttribute("value")],
                        "name": uniq(names, when.getAttribute("value"))
                    }
                })
                sch["type"].append(f)

            schema.append(sch)

        elif e.tagName == "repeat":
            sch = {}
            if top:
                sch["id"] = "#" + e.getAttribute("name")
            else:
                sch["name"] = e.getAttribute("name")

            sch["type"] = {
                "type": "array",
                "items": {
                    "type": "record",
                    "name": uniq(names, e.getAttribute("name")),
                    "fields": inpschema(e, expands, names)
                }
            }

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
                if e.getAttribute("optional").lower() != "true":
                    sch["default"] = ""
            elif e.getAttribute("type") == "integer":
                sch["type"] = "int"
                if e.getAttribute("optional").lower() != "true":
                    sch["default"] = 0
            elif e.getAttribute("type") == "float":
                sch["type"] = "float"
            elif e.getAttribute("type") == "boolean":
                if e.getAttribute("truevalue") or e.getAttribute("falsevalue"):
                    sch["type"] = {
                        "type": "enum",
                        "name": uniq(names, e.getAttribute("name")),
                        "symbols": [e.getAttribute("falsevalue"), e.getAttribute("truevalue")]
                    }
                    if e.getAttribute("checked").lower() == "true":
                        sch["default"] = e.getAttribute("truevalue")
                    else:
                        sch["default"] = e.getAttribute("falsevalue")
                else:
                    sch["type"] = "boolean"
                    if e.getAttribute("checked").lower() == "true":
                        sch["default"] = "true"
                    else:
                        sch["default"] = "false"
            else:
                sch["type"] = "Any"

            if sch:
                if e.getAttribute("optional").lower() == "true":
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
        if e.nodeType != xml.dom.Node.ELEMENT_NODE:
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
                "id": "#" + uniq(names, e.getAttribute("name")  + "_out"),
                "type": "File",
                "outputBinding": {
                    "glob": u
                }
            })

    return schema


def find_macros(basedir, elm, toks, expands):
    for imp in elm.getElementsByTagName("import"):
        find_macros(basedir, xml.dom.minidom.parse(os.path.join(basedir, imp.firstChild.data)).documentElement, toks, expands)
    for tok in elm.getElementsByTagName("token"):
        toks[tok.getAttribute("name")] = tok.firstChild.data
    for x in elm.getElementsByTagName("xml"):
        expands[x.getAttribute("name")] = x

def expand_macros(tool, toks, expands):
    for e in list(tool.childNodes):
        if e.nodeType == xml.dom.Node.ELEMENT_NODE:
            if e.tagName == "expand":
                point = e.nextSibling
                tool.removeChild(e)
                for mac in list(expands[e.getAttribute("macro")].childNodes):
                    tool.insertBefore(mac, point)
                continue
            else:
                expand_macros(e, toks, expands)
        if e.nodeType == xml.dom.Node.TEXT_NODE:
            for k,v in toks.items():
                e.data = e.data.replace(k, v)
        if e.attributes:
            for i in xrange(0, e.attributes.length):
                attr = e.attributes.item(i)
                for k,v in toks.items():
                    attr.value = attr.value.replace(k, v)


def galaxy2cwl(tool, basedir):

    toks = {}
    expands = {}
    names = set()
    find_macros(basedir, tool.getElementsByTagName("macros")[0], toks, expands)

    expand_macros(tool, toks, expands)


    cwl = {"class":"CommandLineTool"}

    #cwl["id"] = "#" + tool.getAttribute("id")
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

    cwl["inputs"] = inpschema(tool.getElementsByTagName("inputs")[0], expands, names, top=True)
    cwl["outputs"] = outschema(cwl["inputs"], tool.getElementsByTagName("outputs")[0], expands, names, top=True)

    return cwl

class Invalid(Exception):
    pass

def bindtestparam(name, sch, params, datadir):
    if not isinstance(sch, dict):
        if name in params:
            return params[name]
        else:
            return None

    if name in params:
        if sch["type"] == "File":
            return {
                "class": "File",
                "path": os.path.join(datadir, params[name])
                }
        elif isinstance(sch["type"], dict):
            if sch["type"]["type"] == "enum":
                if params[name] in sch["type"]["symbols"]:
                    return params[name]
                else:
                    raise Invalid()
        else:
            return params[name]

    if isinstance(sch["type"], list):
        for t in sch["type"]:
            try:
                b = bindtestparam(name, t, params, datadir)
            except Invalid:
                b = None
            if b:
                return b

    if sch["type"] == "record":
        r = {}

        for f in sch["fields"]:
            b = bindtestparam(f["name"], f, params, datadir)
            if b is not None:
                r[f["name"]] = b
        return r

def maketests(source, datadir, tool, cwl):
    tests = []

    n = 0
    for test in tool.getElementsByTagName("tests")[0].getElementsByTagName("test"):
        job = {}
        params = {}
        for p in test.getElementsByTagName("param"):
            params[p.getAttribute("name")] = p.getAttribute("value")

        for i in cwl["inputs"]:
            b = bindtestparam(i["id"][1:], i, params, datadir)
            if b is not None:
                job[i["id"][1:]] = b

        fn = os.path.splitext(source)[0] + "_testjob" + str(n) + ".json"

        with open(fn, "w") as f:
            f.write(json.dumps(job, indent=4))
        print >>sys.stderr, "Wrote " + fn

        outobj = {}

        for out in test.getElementsByTagName("output"):
            with open(os.path.join(datadir, out.getAttribute("file"))) as outfile:
                checksum = hashlib.sha1()
                filesize = 0
                contents = outfile.read(1024*1024)
                while contents != "":
                    checksum.update(contents)
                    filesize += len(contents)
                    contents = outfile.read(1024*1024)

            outobj[out.getAttribute("name")] = {
                "class": "File",
                "path": out.getAttribute("name"),
                "size": filesize,
                "checksum": "sha1$%s" % checksum.hexdigest()
            }

        tests.append({
            "job": fn,
            "tool": source,
            "output": outobj
        })
        n += 1

    fn = os.path.splitext(source)[0] + "_test.yaml"
    with open(fn, "w") as f:
        yaml.safe_dump(tests, f)
    print >>sys.stderr, "Wrote " + fn


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('tool', type=str, nargs=1)
    parser.add_argument('out', type=str, nargs="?")
    args = parser.parse_args(argv)

    basedir = os.path.dirname(args.tool[0])

    dom = xml.dom.minidom.parse(args.tool[0])

    cwl = galaxy2cwl(dom.documentElement, basedir)

    toolstem = os.path.split(args.tool[0])[1]
    datadir = os.path.join(os.path.split(args.tool[0])[0], "test-data")

    if args.out == "-":
        fn = "stdout"
        out = sys.stderr
    else:
        if args.out:
            fn = args.out
        else:
            fn = os.path.splitext(toolstem)[0] + ".cwl"
        out = open(fn, "w")
        maketests(fn, datadir, dom.documentElement, cwl)

    out.write("#!/usr/bin/env cwl-runner\n")
    yaml.safe_dump(cwl, out, encoding="utf-8")

    out.close()

    os.chmod(fn, os.stat(fn).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print >>sys.stderr, "Wrote " + fn

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
