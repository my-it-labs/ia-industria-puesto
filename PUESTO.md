# Puesto de los laboratorios

El puesto es Ubuntu 24.04 LTS, 64 bits. Vale en el propio equipo, en WSL2 o en una máquina virtual. La prueba mide esa Ubuntu.

En clase, Docker reserva 2 GB para un modelo generativo y otros 2 GB para un paso de laboratorio, además del propio sistema. Dentro de la Ubuntu tienen que verse 16 GB. En WSL2 o en una VM eso se asigna a propósito: si el PC solo tiene 16 GB, Windows o el hipervisor se quedan con una parte y la prueba no llega.

Este repositorio no incluye los laboratorios. Comprueba el equipo y, con los mismos techos de memoria, un modelo pequeño y un segundo contenedor.

El equipo se prepara antes del primer día. Ese día no se instala nada.

## Equipo

Los mínimos y cómo repartirlos en cada sitio están en [README.md](README.md). Resumen: 4 núcleos, 16 GB de RAM y 20 GB libres dentro de la Ubuntu. En WSL2 el PC necesita 32 GB y un `.wslconfig` con `memory=16GB` y `processors=4`. En una máquina virtual se asignan 4 vCPU, 16 GB y 40 GB de disco, sobre un PC de unos 8 núcleos y 32 GB.

## Software

Instalado para el usuario de clase, que entra sin pedir privilegios cada día:

- Docker Engine 24 o superior y el plugin Compose v2 (`docker compose`, no el binario antiguo `docker-compose`). En Ubuntu: paquetes `docker.io` y `docker-compose-v2`.
- El usuario de clase en el grupo `docker`. Después de añadirlo hace falta cerrar la sesión y volver a entrar. En clase no se usa `sudo`.
- Git
- GitHub CLI (`gh`)
- Visual Studio Code
- Google Chrome

Python en el equipo no hace falta. No hace falta GPU ni webcam.

## Red

Salida a:

- `registry-1.docker.io` y `auth.docker.io` (imágenes, incluida Mosquitto)
- `github.com` (la rueda del modelo local)
- `huggingface.co` (el fichero del modelo, unos 470 MB)
- `pypi.org` y `files.pythonhosted.org` (los paquetes Python de los laboratorios)
- `deb.debian.org` (librerías del sistema dentro de la imagen)

La primera preparación baja todo eso. En clase no hay más descargas. No hace falta abrir puertos hacia internet: el navegador usa `localhost`.

En el equipo tienen que estar libres los puertos 1883, 4840, 1502, 8501, 8000 y 8088.

## Cómo se comprueba

Desde este repositorio, con el usuario de clase:

```bash
./comprobar-puesto.sh
```

La primera vez construye la imagen y baja el modelo. Tarda varios minutos. El equipo está listo solo si la última línea es:

```text
PUESTO_OK
```

Si algo no cumple, el script sale con código 1 y escribe `FALLO` y el motivo. No se da por bueno un puesto que no haya impreso `PUESTO_OK`.

La prueba hace tres cosas, en este orden:

1. Equipo. Ubuntu x86_64 en el equipo, en WSL2 o en una máquina virtual; el repositorio en el disco de esa Ubuntu, no en `/mnt`; 4 núcleos, 16 GB, 20 GB libres, Docker 24 sin `sudo`, Compose v2, los seis puertos libres y salida a Docker Hub, GitHub, Hugging Face, PyPI y Debian.
2. Memoria que ve Docker. Al menos 12 GB. Si WSL o la máquina virtual se crearon con menos, la prueba para.
3. Descargas. Baja Mosquitto, construye la imagen con los paquetes de los laboratorios e importa cada uno dentro del contenedor.
4. Red local. Publica los seis puertos y comprueba que `localhost` llega al contenedor. Lee un fichero del disco a través de Docker.
5. Desempeño. Arranca un contenedor con techo de 2 GB, carga el modelo y pide una respuesta corta. Con ese contenedor en marcha, arranca otro de 2 GB. Falla si uno muere por falta de memoria, si el modelo no responde en 45 segundos o si el segundo contenedor no termina en 120 segundos. Al final tienen que quedar al menos 5 GB libres.

Al terminar, para los contenedores. Para repetir solo el equipo, sin arrancar nada:

```bash
./comprobar-puesto.sh --solo-equipo
```

Eso imprime `EQUIPO_OK`. No sustituye a `PUESTO_OK`.
