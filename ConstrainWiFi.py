from socket import gethostbyname, gaierror
from subprocess import check_call
from sys import argv
from pathlib import Path

print(repr(argv))
HOSTS_FILE = Path('Constrained hosts.txt')

if argv[1:]:
    HOSTS = argv[1:]
elif HOSTS_FILE.exists():
    lines = HOSTS_FILE.read_text().split('\n')
    HOSTS = [item.strip() for item in lines if item and not item.startswith('#')]
else:
    raise RuntimeError("Hosts are not provided neither in args nor in 'Constrained hosts' file")


try:

    IPs = [gethostbyname(host) for host in HOSTS]

    print("Constraining targets:")
    for host, ip in zip(HOSTS, IPs):
        print(f"    Route {host}({ip}) via 192.168.43.1")
    print()

    commands = (
        'route DELETE 0.0.0.0',
        *(f'route DELETE {ip}' for ip in IPs),
        'route ADD 0.0.0.0 MASK 0.0.0.0 192.168.116.115 IF 13',
        *(f'route ADD {ip} MASK 255.255.255.255 192.168.43.1 IF 15' for ip in IPs),
        'route PRINT'
    )

    for command in commands:
        print(f"Command: {command}")
        check_call(command, shell=True)
        print()

    print("\nDONE")
    check_call('pause >nul', shell=True)

except Exception as e:
    if type(e) is gaierror:
        print(f"Error: failed to resolve '{HOST}'")
    print(e)
    input("Script will now exit")
    exit(1)
