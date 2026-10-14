"""Ocupa memoria dentro del techo de 2 GB, con el modelo ya en marcha."""
bloque = bytearray(1024 * 1024 * 1024)
for i in range(0, len(bloque), 4096):
    bloque[i] = 1
print("OK paso", flush=True)
