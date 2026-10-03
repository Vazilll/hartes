import sys
import subprocess

args = []
for a in sys.argv[1:]:
    a = a.replace("x86_64-pc-windows-gnu", "x86_64-windows-gnu")
    if a in ("-O0", "-O1", "-O2"):
        a = "-O3"
    args.append(a)

if not any(a.startswith("-O") for a in args):
    args.append("-O3")

args.append("-fno-sanitize=undefined")
sys.exit(subprocess.run(["zig", "cc"] + args).returncode)
