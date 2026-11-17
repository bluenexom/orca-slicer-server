import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--model", required=True, help="Location of the model file.")

args = parser.parse_args()

model = getattr(args,"model",None)

result = subprocess.run( #type: ignore
    [
        r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
        "--debug",
        "0",
        "--datadir",
        "orca-data",
        "--slice",
        "0",
        "--load-settings",
        "orca-data/user/default/machine/test-k2-plus.json;orca-data/user/default/process/test-process.json",
        "--load-filaments",
        "orca-data/user/default/filament/test-pla.json",
        "--outputdir",
        "out",
        model, #type: ignore
    ],    
    capture_output=True,
    text=True,
)

if result.returncode == 0:
    with open("./out/plate_1.gcode", "rb") as file:
        file.seek(0, 2)
        size = file.tell()
        file.seek(max(0, size - 20_000))
        last_lines = file.read().decode(errors="ignore").splitlines()[-20:]
        filament_used = 0
        print_time = 0

        for line in last_lines:
            if line.startswith("; total filament used [g]"):
                filament_used = line.split("=")[1].strip()
            elif line.startswith("; estimated printing time"):
                print_time = line.split("=")[1].strip()

        print(f"Total filament used = {filament_used}g")
        print(f"Total time = {print_time}")

else:
    print(result.returncode)
    print(result.stderr)
