#!/usr/bin/env python3
import json
import re
import sys

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <ctchecker_txt> <output_json>")
    sys.exit(1)

txt_file = sys.argv[1]
json_file = sys.argv[2]

# Regular expression to parse lines like:
# library/bignum.c line  104 - if( X->p != NULL )
line_re = re.compile(r"^(?P<filename>.+?)\s+line\s+(?P<line>\d+)\s+-\s+(?P<code>.+)$")

branches = []

with open(txt_file, "r") as f:
    for l in f:
        l = l.strip()
        if not l:
            continue
        m = line_re.match(l)
        if m:
            branches.append({
                "filename": m.group("filename"),
                "line": int(m.group("line")),
                "column": 1,        # no column info in txt, so default to 1
                "code": m.group("code").strip()
            })

output = {"branches": branches}

with open(json_file, "w") as f:
    json.dump(output, f, indent=2)

print(f"Converted {len(branches)} branches to {json_file}")
