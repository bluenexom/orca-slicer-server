import os
import glob
import argparse
import tempfile
import subprocess

ORCA_PATH = os.environ.get("ORCA_PATH", r"C:\Program Files\OrcaSlicer\orca-slicer.exe")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR,"orca-data")
PRESET_DIR = os.path.join(DATA_DIR,"user","default")
PROCESS_DIR = os.path.join(PRESET_DIR,"process")
PROCESS_PRESET = os.path.join(PROCESS_DIR, "fdm.json") 
MACHINE_DIR = os.path.join(PRESET_DIR,"machine")
MACHINE_PRESET = os.path.join(MACHINE_DIR, "k2-plus.json")
FILAMENT_DIR = os.path.join(PRESET_DIR,"filament")
FILAMENTS = ["ABS","PLA","TPU"]
LAYER_HEIGHT = ["0.1","0.2","0.3"]
INFILL = range(0,101)

def get_seconds(time):
    d = 0
    h = 0
    m = 0 
    s = 0 
    parts = time.split(" ")

    for part in parts:
        unit = part[-1]
        if unit == "d":
            d = int(part[:-1]) * 24 * 60 * 60
        elif unit == "h":
            h = int(part[:-1]) * 60 * 60
        elif unit == "m":
            m = int(part[:-1]) * 60
        elif unit == "s":
            s = int(part[:-1])
        else:
            raise ValueError(f"Unknown time unit: {part}")

    total_seconds = d + h + m + s 
    return total_seconds

def slice_model(model,filament,layer_height,infill):
    with tempfile.TemporaryDirectory() as out_dir:
        filament_used = 0
        print_time = 0 

        result = subprocess.run(
            [
                ORCA_PATH,
                "--debug",
                "0",
                "--datadir",
                DATA_DIR,
                "--slice",
                "0",
                "--load-settings",
                f"{MACHINE_PRESET};{PROCESS_PRESET}",
                "--load-filaments",
                os.path.join(FILAMENT_DIR,f"{filament.lower()}.json"),
                "--layer-height",
                layer_height,
                "--sparse-infill-density",
                f"{infill}%",
                "--arrange",
                "1",
                "--outputdir",
                out_dir,
                model,
            ],    
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            plates = glob.glob(os.path.join(out_dir, "plate_*.gcode"))
            if not plates:
                raise RuntimeError("Orca made no G-code")
            for plate in plates:
                grams = None
                seconds = None
                with open(plate, "rb") as gcode:
                    gcode.seek(0, 2)
                    size = gcode.tell()
                    gcode.seek(max(0, size - 20_000))
                    last_lines = gcode.read().decode(errors="ignore").splitlines()[-20:]

                    for line in last_lines:
                        if line.startswith("; total filament used [g]"):
                            grams = float(line.split("=")[1].strip())
                        elif line.startswith("; estimated printing time"):
                            seconds = get_seconds(line.split("=")[1].strip())
                    if grams is None or seconds is None:
                        raise RuntimeError("Couldn't read filament/time from G-code")
                    else:
                        filament_used+=grams
                        print_time+=seconds
            return (round(filament_used,2), print_time)

        else:
            raise RuntimeError(f"Orca failed ({result.returncode}): {result.stderr}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--filament", required=True, help="Filament for the print.",type=str.upper,choices=FILAMENTS)
    parser.add_argument("-l", "--layer-height", required=True, help="Layer height of the print.", type=str, choices=LAYER_HEIGHT)
    parser.add_argument("-i", "--infill", required=True, help="Infill percentage.",type=int, choices=INFILL,metavar="0-100")
    parser.add_argument("-m", "--model", required=True, help="Location of the model file.",type=str)
    args = parser.parse_args()
    filament = args.filament
    layer_height = args.layer_height
    infill = args.infill
    model = args.model
    print(slice_model(model,filament,layer_height,infill))
