# Preparación del puesto

Este repositorio no contiene el curso. Sirve para dejar el equipo listo y comprobar que aguanta la carga de los laboratorios.

Vale igual **Ubuntu en el propio equipo**, **Ubuntu en WSL2** o **Ubuntu en una máquina virtual**. La prueba no mira el Windows ni el hipervisor: mira la Ubuntu donde se va a trabajar.

```bash
git clone https://github.com/my-it-labs/ia-industria-puesto.git
cd ia-industria-puesto
./comprobar-puesto.sh
```

La primera vez baja Mosquitto, los paquetes Python de los laboratorios, la rueda del modelo y el fichero de unos 470 MB. Publica los puertos de la clase, lee un fichero a través de Docker y carga el modelo junto con un segundo contenedor. No ejecuta los ejercicios. Tarda varios minutos. El equipo está listo solo si la última línea es:

```text
PUESTO_OK
```

Esa línea es la que hay que devolver. Si algo no cumple, el script sale con código 1 y escribe `FALLO` y el motivo.

El detalle de instalación está en [PUESTO.md](PUESTO.md).

## Requisitos mínimos

Dentro de la Ubuntu, en los tres casos:

| | Mínimo |
|--|--|
| Sistema | Ubuntu 24.04 LTS, 64 bits |
| CPU | 4 núcleos. El modelo arranca con 4 hilos |
| RAM | 16 GB en el equipo. La prueba pide al menos 11 GB visibles en la Ubuntu y 11 GB vistos por Docker |
| Disco libre | 20 GB, después de instalar el sistema |
| Docker | Engine 24 o superior y Compose v2, usables sin `sudo` |

En clase Docker reserva 2 GB para un modelo y otros 2 GB para un paso, además del sistema. Con todo arrancado, los contenedores no pasan de unos 6 GB; 12 GB dentro de la Ubuntu dejan margen.

### Ubuntu en el equipo

El PC es la Ubuntu. Con 4 núcleos, 16 GB de RAM y un disco de 40 GB se cumple la tabla.

### WSL2

Ubuntu 24.04 instalada en WSL2. Docker va dentro de esa Ubuntu. No hace falta Docker Desktop.

Vale un PC de **16 GB**. Por defecto WSL solo ve la mitad, así que hay que darle 12 GB. Windows sigue funcionando porque WSL solo ocupa lo que usa y lo devuelve. En `%UserProfile%\.wslconfig`:

```
[wsl2]
memory=12GB
swap=8GB
processors=4

[experimental]
autoMemoryReclaim=gradual
```

Con 32 GB en el PC se puede poner `memory=16GB`.

Después, `wsl --shutdown` y volver a abrir Ubuntu. En el disco de esa Ubuntu tienen que quedar 20 GB libres.

### Máquina virtual

A la VM se le asignan 4 vCPU, 16 GB de RAM y 40 GB de disco. El PC que la hospeda tiene que poder prestar eso y seguir funcionando: **8 núcleos y 32 GB de RAM** es la estimación cómoda.
