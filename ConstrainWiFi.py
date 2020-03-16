from socket import gethostbyname, gaierror
from subprocess import check_call


HOST = 'odincova.ddns.net'


try:

    IP = gethostbyname(HOST)

    commands = (
        'route DELETE 0.0.0.0',
        f'route DELETE {IP}',
        'route ADD 0.0.0.0 MASK 0.0.0.0 192.168.116.115 IF 13',
        f'route ADD {IP} MASK 255.255.255.255 192.168.43.1 IF 15',
        'route PRINT'
    )

    for command in commands:
        check_call(command, shell=True)

    print("\nDONE")
    check_call('pause >nul', shell=True)
    exit(0)

except Exception as e:
    if type(e) is gaierror:
        print(f"Error: failed to resolve '{HOST}'")
    print(e)
    input("Script will now exit")
    exit(1)
