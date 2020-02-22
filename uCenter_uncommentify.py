from sys import argv
from pathlib import Path

hashchar = '#'

if __name__ == '__main__':
    try:
        path = input("U-center config file path: ") or r"C:\GLEB\SRTK2Blite+RPi_Base\test.txt"
        path = Path(path.strip('"'))
        
        footer = input("New name footer: ") or '_clean'
        
        with path.open('r') as file:
            lines = list(file)

        parwidth = 0
        for line in lines:
            if not line.strip():
                continue
            if not (line.startswith(hashchar) or line.startswith('[')):
                parwidth = max(
                    parwidth,
                    len(line.split(' ', maxsplit=1)[1].split(' ', maxsplit=1)[0])
                )
        parwidth += 1

        for i, line in enumerate(lines):
            if line and hashchar in line and not line.startswith(hashchar):
                payload = line.split(hashchar)[0].strip()
                target, name, value = payload.split()
                output = target.rjust(5) + ' ' + name.ljust(parwidth) + value
                print(output)
                lines[i] = output + '\n'

        newname = path.stem + footer + path.suffix

        print(f"\nUncommented {i} lines")
        input(f"Enter - write to file '{newname}'")

        path.with_name(newname).write_text(''.join(lines))

    except Exception as e:
        print(f"{e} - line {e.__traceback__.tb_lineno}")
        input()
        exit(1)
