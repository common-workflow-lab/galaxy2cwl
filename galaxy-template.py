#!/usr/bin/env python

import json
import sys
from Cheetah.Template import Template

j = json.load(sys.stdin)

def resolve_paths(p):
    if isinstance(p, dict):
        for k,v in p.items():
            if isinstance(v, dict) and v.get("class") == "File":
                p[k] = v.get("path")
            else:
                resolve_paths(v)

resolve_paths(j)

command_line = str( Template( source=j["script"], searchList=[j["job"]] ) )

print json.dumps(command_line)
