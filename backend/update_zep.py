new_key = "z_1dWlkIjoiOTJhOGU5YTctZTA4ZC00YWQxLTlkMWUtNzBiOTAxNDQyNzE4In0.A9J2zKRWx1kLrNO4hWkQgl77hoPUYVFvWlTZK0pQqfzdx0yby6gV5QeEnMrFpO9dxGsU0dJjojyr0UwBrYa1Gw"

with open(r"E:\MiroFish\.env", "r", encoding="utf-8") as f:
    lines = f.readlines()

result = []
for line in lines:
    if line.startswith("ZEP_API_KEY"):
        result.append("ZEP_API_KEY=" + new_key + "\n")
    else:
        result.append(line)

with open(r"E:\MiroFish\.env", "w", encoding="utf-8") as f:
    f.writelines(result)

print("Done!")
