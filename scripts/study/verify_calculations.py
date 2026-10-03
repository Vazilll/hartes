import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. Verification of decoded phrase: 145 170 174 224 174 255 170 160 173 168 170 227 171 235
bytes_list = [145, 170, 174, 224, 174, 255, 170, 160, 173, 168, 170, 227, 171, 235]
b = bytes(bytes_list)
print("Decoded phrase in CP866:")
try:
    print("CP866:", b.decode('cp866'))
except Exception as e:
    print("Error cp866:", e)

try:
    print("CP1251:", b.decode('cp1251'))
except Exception as e:
    print("Error cp1251:", e)

# 2. Words in CP866 / ASCII
hex_str1 = "88 AD E4 AE E0 AC A0 E2 A8 AA A0"
b1 = bytes.fromhex(hex_str1)
print("Word 1 (CP866):", b1.decode('cp866'))

hex_str2 = "50 72 6F 67 72 61 6D"
b2 = bytes.fromhex(hex_str2)
print("Word 2 (ASCII):", b2.decode('ascii'))

hex_str3 = "43 6F 6D 70 75 74 65 72 20 49 42 4D 20 50 43"
b3 = bytes.fromhex(hex_str3)
print("Word 3 (ASCII):", b3.decode('ascii'))

# 3. Zhukov Maksim Dmitrievich
fio = "Жуков Максим Дмитриевич"
print("\nFIO encodings:")
for enc in ['cp1251', 'koi8_r', 'cp866', 'utf-8']:
    raw = fio.encode(enc)
    print(f"{enc}: hex={raw.hex(' ')}, dec={[int(x) for x in raw]}")

# 4. Words for variant 6: "Протокол", "Сеть"
print("\nVariant 6 words:")
for word in ["Протокол", "Сеть"]:
    print(f"--- {word} ---")
    for enc in ['cp1251', 'koi8_r', 'cp866', 'utf-16be']:
        raw = word.encode(enc)
        print(f"{enc}: hex={raw.hex(' ').upper()}, dec={[int(x) for x in raw]}")

# 5. Logic PR-5 Var 6: F(A, B) = A and (B or not A)
print("\nPR-5 Var 6 Truth Table:")
print("A B | notA | B or notA | F(A,B)")
for A in [0, 1]:
    for B in [0, 1]:
        notA = 1 - A
        or_val = B or notA
        F = A and or_val
        print(f"{A} {B} |  {notA}   |     {or_val}     |   {F}")

# 6. Logic PR-6 Var 6: 4C3B_16
val_hex = "4C3B"
bin_str = bin(int(val_hex, 16))[2:].zfill(16)
print(f"\nPR-6 Var 6: {val_hex}_16 = {bin_str}_2")
minterms = []
maxterms = []
print("a b c d | F | type")
for i in range(16):
    a = (i >> 3) & 1
    b = (i >> 2) & 1
    c = (i >> 1) & 1
    d = i & 1
    f_val = int(bin_str[i])
    t = f"m{i}" if f_val == 1 else f"M{i}"
    if f_val == 1:
        minterms.append(i)
    else:
        maxterms.append(i)
    print(f"{a} {b} {c} {d} | {f_val} | {t}")

print(f"Minterms (F=1): {minterms}")
print(f"Maxterms (F=0): {maxterms}")
