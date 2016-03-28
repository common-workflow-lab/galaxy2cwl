Attention: not currently compatible with the latest CWL draft. This is a work in progress.

TODO:  generate a two-step workflow (1st step runs cheetah to get the command line, 2nd step runs actual tool

Auto convert Galaxy tool XML to CWL Draft-2 CommandLineTool.

May be used as a command line tool:

```
$ ./galaxy2cwl.py bwa/bwa-mem.xml
Wrote bwa/bwa-mem.cwl
```

May also be imported as a module:


```
import galaxy2cwl
import xml.dom.minidom

galaxy2cwl.galaxy2cwl(xml.dom.minidom.parse("bwa/bwa-mem.xml").documentElement, "bwa")
```
