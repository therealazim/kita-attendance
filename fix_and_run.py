with open('main.py', 'rb') as f:
    raw = f.read()

raw = raw.replace(b'\xe2\x80\x98', b"'")
raw = raw.replace(b'\xe2\x80\x99', b"'")
raw = raw.replace(b'\xe2\x80\x9c', b'"')
raw = raw.replace(b'\xe2\x80\x9d', b'"')

with open('main.py', 'wb') as f:
    f.write(raw)

print("main.py tuzatildi!")
