from pathlib import Path
p = Path('config.remote.py')
s = p.read_text()
needle = '"MAV_LOCAL_OUT_PORT_2": 14551,'
ins = '    "MAVPROXY_BINARY": "/home/dev/cenv/bin/mavproxy.py",\n'
if needle in s:
    s = s.replace(needle, needle + '\n' + ins)
    p.write_text(s)
    print('inserted')
else:
    print('needle not found')
