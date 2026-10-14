# Puesto de los laboratorios

El puesto es **Linux en el propio equipo**: Ubuntu 24.04 LTS, 64 bits. No es Windows, ni WSL2, ni una máquina virtual por encima de otro sistema.

Los laboratorios corren en Docker. El modelo generativo reserva 2 GB y un paso de laboratorio otros 2 GB, además de la estación (alrededor de 1 GB) y del propio sistema. Esos límites salen de los 16 GB del equipo. En WSL2 hay que partir esa memoria con Windows, y Docker Desktop añade una máquina virtual y una licencia. La prueba de abajo rechaza ese puesto.

El equipo se prepara antes del primer día. Ese día no se instala nada.

## Equipo

| | |
|--|--|
| Sistema | Ubuntu 24.04 LTS, x86_64, instalado en el equipo |
| CPU | 4 núcleos. El modelo arranca con 4 hilos |
| RAM | 16 GB |
| Disco | 40 GB, con 20 GB libres después de instalar el sistema |

## Software

Instalado para el usuario de clase, que entra sin pedir privilegios cada día:

- Docker Engine 24 o superior y el plugin Compose v2 (`docker compose`, no el binario antiguo `docker-compose`). En Ubuntu: paquetes `docker.io` y `docker-compose-v2`.
- El usuario de clase en el grupo `docker`. Después de añadirlo hace falta cerrar la sesión y volver a entrar. Los laboratorios no usan `sudo`.
- Git
- GitHub CLI (`gh`)
- Visual Studio Code
- Google Chrome

Python en el equipo no hace falta. Lo que usa el curso corre dentro de los contenedores.

No hace falta GPU ni webcam.

## Red

Salida HTTPS a:

- `registry-1.docker.io` y `auth.docker.io`
- `github.com`
- `huggingface.co`

La primera preparación baja las imágenes y un fichero de unos 470 MB. En clase no hay más descargas. No hace falta abrir puertos hacia internet: el navegador usa `localhost`.

En el equipo tienen que estar libres los puertos 1883, 4840, 1502, 8501, 8000 y 8088.

## Cómo se comprueba

Desde la carpeta `infra/` del repositorio, con el usuario de clase:

```bash
./comprobar-puesto.sh
```

La primera vez construye la imagen, baja el modelo y arranca la estación. Tarda varios minutos. El equipo está listo solo si la última línea es:

```text
PUESTO_OK
```

Si algo no cumple, el script sale con código 1 y escribe `FALLO` y el motivo. No se da por bueno un puesto que no haya impreso `PUESTO_OK`.

La prueba hace tres cosas, en este orden:

1. Equipo. Sistema Linux de verdad (no WSL), 4 núcleos, 16 GB, 20 GB libres, Docker 24 accesible sin `sudo`, Compose v2, los seis puertos libres y salida HTTPS a los tres sitios.
2. Memoria que ve Docker. Tiene que ser la del equipo, no la de una máquina virtual recortada. Por debajo de 12 GB la prueba para.
3. Desempeño. Arranca la estación y el modelo, pide una respuesta corta y ejecuta un paso de laboratorio con todo eso en marcha. Falla si un contenedor muere por falta de memoria, si el modelo no responde en 45 segundos o si el paso de laboratorio no responde en 120 segundos.

Al terminar, para los contenedores. Para repetir solo el equipo, sin arrancar nada:

```bash
./comprobar-puesto.sh --solo-equipo
```

Eso imprime `EQUIPO_OK`. No sustituye a `PUESTO_OK`.
