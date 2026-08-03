with open("pinterest_poster.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_main_block = False
for i, line in enumerate(lines):
    if "page = await context.new_page()" in line and "if not logged_in:" in lines[i-4]:
        in_main_block = True
    
    if in_main_block and i >= 139 and i <= 288:
        if line.strip() == "":
            new_lines.append(line)
        else:
            new_lines.append("    " + line)
    else:
        new_lines.append(line)

with open("pinterest_poster.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
