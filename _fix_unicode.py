import re
p = r'c:\Users\burak\ptojects\secure-tunnel\generate_detailed_report.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()
replacements = {
    '\u250c': '+', '\u2510': '+', '\u2514': '+', '\u2518': '+',
    '\u251c': '+', '\u2524': '+', '\u252c': '+', '\u2534': '+', '\u253c': '+',
    '\u2500': '-', '\u2502': '|',
    '\u2605': '[*]',
    '\u2014': '--',
}
for old, new in replacements.items():
    count = content.count(old)
    if count > 0:
        print(f'  Replacing U+{ord(old):04X} ({count} occurrences) -> {repr(new)}')
        content = content.replace(old, new)
with open(p, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
