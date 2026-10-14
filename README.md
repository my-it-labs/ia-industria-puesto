# Prueba del puesto

Comprueba que un equipo puede correr los laboratorios de **Inteligencia Artificial Aplicada a Entornos Industriales**.

Lo que hay que instalar está en [PUESTO.md](PUESTO.md). El equipo es Ubuntu 24.04 en la propia máquina, con el usuario de clase en el grupo `docker`. En clase no se usa `sudo`.

```bash
git clone https://github.com/my-it-labs/ia-industria-puesto.git
cd ia-industria-puesto
./comprobar-puesto.sh
```

La primera vez construye la imagen, baja el modelo y arranca la estación. Tarda varios minutos. El equipo está listo solo si la última línea es:

```text
PUESTO_OK
```

Esa línea es la que hay que devolver. Si algo no cumple, el script sale con código 1 y escribe `FALLO` y el motivo.
