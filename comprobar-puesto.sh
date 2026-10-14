#!/usr/bin/env bash
# Comprueba el puesto de los laboratorios. Sirve en Ubuntu del equipo, en WSL2 o en una máquina virtual.
# La aceptación es la línea PUESTO_OK. Cualquier fallo sale con código 1.
set -u
set -o pipefail

cd "$(dirname "$0")"

SOLO_EQUIPO=0
if [[ "${1:-}" == "--solo-equipo" ]]; then
  SOLO_EQUIPO=1
elif [[ -n "${1:-}" ]]; then
  echo "Uso: ./comprobar-puesto.sh [--solo-equipo]" >&2
  exit 2
fi

FALLOS=0
RAM_MIN_KB=$((14 * 1024 * 1024))
DOCKER_RAM_MIN=$((12 * 1024 * 1024 * 1024))
DISCO_MIN_GB=20
LLM_MAX_S=45
LAB_MAX_S=120
MODELO="modelos/qwen2.5-0.5b-instruct-q4_k_m.gguf"
URL_MODELO="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
URL_RUEDA="https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.19/llama_cpp_python-0.3.19-cp312-cp312-linux_x86_64.whl"
IMAGEN="puesto-modelo"
PUERTOS=(1883 4840 1502 8501 8000 8088)

ok() { printf 'OK  %s\n' "$1"; }
fallo() {
  printf 'FALLO  %s\n' "$1"
  FALLOS=$((FALLOS + 1))
}

comprobar_equipo() {
  local mem_kb libres_gb mayor ver

  if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    fallo "hace falta Ubuntu x86_64, en el equipo, en WSL2 o en una máquina virtual ($(uname -s) $(uname -m))"
  elif grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null || [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
    ok "Ubuntu en WSL2"
  elif systemd-detect-virt --quiet 2>/dev/null; then
    ok "Ubuntu en máquina virtual ($(systemd-detect-virt))"
  else
    ok "Ubuntu en el equipo"
  fi

  case "$(pwd -P)" in
    /mnt/*)
      fallo "el repositorio está en /mnt (disco de Windows). Clónalo en el home de Ubuntu"
      ;;
    *)
      ok "repositorio en el disco de Ubuntu"
      ;;
  esac

  if [[ "$(nproc)" -ge 4 ]]; then
    ok "cpu $(nproc) núcleos"
  else
    fallo "cpu $(nproc) núcleos; hacen falta 4"
  fi

  mem_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
  if [[ "$mem_kb" -ge "$RAM_MIN_KB" ]]; then
    ok "ram $(awk -v kb="$mem_kb" 'BEGIN {printf "%.1f GB", kb/1024/1024}')"
  else
    fallo "ram $(awk -v kb="$mem_kb" 'BEGIN {printf "%.1f GB", kb/1024/1024}'); hacen falta 16 GB instalados"
  fi

  libres_gb="$(df -BG --output=avail . | awk 'NR==2 {gsub(/G/,"",$1); print $1}')"
  if [[ "$libres_gb" -ge "$DISCO_MIN_GB" ]]; then
    ok "disco libre ${libres_gb} GB"
  else
    fallo "disco libre ${libres_gb} GB; hacen falta ${DISCO_MIN_GB} GB"
  fi

  local cmd
  for cmd in git gh code; do
    if command -v "$cmd" >/dev/null 2>&1; then
      ok "$cmd"
    else
      fallo "falta $cmd en el PATH del usuario de clase"
    fi
  done
  if command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1; then
    ok "google-chrome"
  else
    fallo "falta Google Chrome en el PATH del usuario de clase"
  fi
  if ! command -v ss >/dev/null 2>&1; then
    fallo "falta ss (paquete iproute2)"
  fi

  if docker info >/dev/null 2>&1; then
    ver="$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)"
    mayor="${ver%%.*}"
    if [[ "$mayor" =~ ^[0-9]+$ && "$mayor" -ge 24 ]]; then
      ok "docker $ver sin sudo"
    else
      fallo "docker ${ver:-desconocido}; hace falta Engine 24 o superior"
    fi
  else
    fallo "docker info no responde sin sudo; el usuario tiene que estar en el grupo docker"
  fi

  if docker compose version >/dev/null 2>&1; then
    ok "docker compose v2"
  else
    fallo "falta docker compose v2 (el comando es docker compose, no docker-compose)"
  fi

  if docker info >/dev/null 2>&1; then
    local docker_ram
    docker_ram="$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)"
    if [[ "$docker_ram" -ge "$DOCKER_RAM_MIN" ]]; then
      ok "docker ve $((docker_ram / 1024 / 1024 / 1024)) GB"
    else
      fallo "docker solo ve $((docker_ram / 1024 / 1024 / 1024)) GB; la máquina virtual está recortada"
    fi
  fi

  local puerto
  for puerto in "${PUERTOS[@]}"; do
    if ss -ltn sport = ":$puerto" 2>/dev/null | grep -q ":$puerto"; then
      fallo "puerto $puerto ocupado"
    else
      ok "puerto $puerto libre"
    fi
  done

  local nombre url
  for nombre in "Docker Hub" "GitHub" "Hugging Face" "PyPI" "paquetes Python" "Debian"; do
    case "$nombre" in
      "Docker Hub") url="https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/hello-world:pull" ;;
      "GitHub") url="$URL_RUEDA" ;;
      "Hugging Face") url="$URL_MODELO" ;;
      "PyPI") url="https://pypi.org/simple/numpy/" ;;
      "paquetes Python") url="https://files.pythonhosted.org/packages/3f/27/4570e78fc0bf5ea0ca45eb1de3818a23787af9b390c0b0a0033a1b8236f9/diskcache-5.6.3-py3-none-any.whl" ;;
      "Debian") url="http://deb.debian.org/debian/dists/bookworm/Release" ;;
    esac
    if curl -fsSL -o /dev/null --max-time 30 -r 0-0 "$url"; then
      ok "salida $nombre"
    else
      fallo "sin salida a $nombre ($url)"
    fi
  done
}

asegurar_modelo() {
  local bytes
  if [[ -f "$MODELO" ]]; then
    bytes="$(stat -c '%s' "$MODELO")"
    if [[ "$bytes" -gt 10000000 ]]; then
      ok "modelo ya está ($((bytes / 1024 / 1024)) MB)"
      return 0
    fi
  fi
  mkdir -p modelos
  echo "+ descargando modelo"
  if curl -fL --retry 3 --max-time 600 -o "$MODELO" "$URL_MODELO"; then
    ok "modelo descargado"
    return 0
  fi
  fallo "no se pudo bajar el modelo desde Hugging Face"
  return 1
}

alguno_oom() {
  local id nombre
  while read -r id; do
    [[ -z "$id" ]] && continue
    nombre="$(docker inspect --format '{{.Name}} {{.State.OOMKilled}}' "$id")"
    if [[ "$nombre" == *true ]]; then
      echo "$nombre"
      return 0
    fi
  done < <(docker compose ps -q)
  return 1
}

comprobar_descargas() {
  echo "+ docker pull eclipse-mosquitto:2"
  if ! docker pull eclipse-mosquitto:2; then
    fallo "no se pudo bajar eclipse-mosquitto:2 desde Docker Hub"
    return 1
  fi
  ok "imagen mosquitto"

  echo "+ docker compose build"
  if ! docker compose build; then
    fallo "no se pudo construir la imagen (pip, la rueda de GitHub o apt)"
    return 1
  fi
  ok "imagen construida, paquetes instalados"

  local salida
  salida="$(docker run --rm "$IMAGEN" python /opt/importar.py)" || {
    fallo "un paquete no importa dentro del contenedor"
    printf '%s\n' "$salida"
    return 1
  }
  if ! grep -q 'OK imports' <<<"$salida"; then
    fallo "un paquete no importa dentro del contenedor"
    printf '%s\n' "$salida"
    return 1
  fi
  ok "paquetes importados"
}

comprobar_puertos_publicados() {
  local puerto cid bien i
  for puerto in "${PUERTOS[@]}"; do
    cid="$(docker run -d --rm -p "${puerto}:8080" "$IMAGEN" python /opt/escucha.py)" || {
      fallo "no se pudo publicar el puerto $puerto"
      continue
    }
    bien=0
    for i in 1 2 3 4 5 6 7 8 9 10; do
      if curl -fsS --max-time 2 "http://127.0.0.1:${puerto}/" 2>/dev/null | grep -q ok; then
        bien=1
        break
      fi
      sleep 0.5
    done
    docker rm -f "$cid" >/dev/null 2>&1 || true
    if [[ "$bien" -eq 1 ]]; then
      ok "localhost:$puerto llega al contenedor"
    else
      fallo "localhost:$puerto no llega al contenedor"
    fi
  done
}

comprobar_volumen() {
  local salida
  mkdir -p data
  echo ok > data/puesto-escritura
  salida="$(docker run --rm -v "$PWD/data:/data:ro" "$IMAGEN" python -c 'print(open("/data/puesto-escritura").read().strip())')" || {
    fallo "Docker no pudo leer un fichero del disco"
    printf '%s\n' "$salida"
    return 1
  }
  rm -f data/puesto-escritura
  if [[ "$salida" == "ok" ]]; then
    ok "volumen leído desde el disco"
  else
    fallo "Docker leyó mal el fichero del disco"
    printf '%s\n' "$salida"
    return 1
  fi
}

comprobar_desempeno() {
  local t_llm t_lab salida oom libres_gb

  comprobar_descargas || return
  comprobar_puertos_publicados
  if [[ "$FALLOS" -gt 0 ]]; then
    return
  fi
  comprobar_volumen || return

  asegurar_modelo || return

  libres_gb="$(df -BG --output=avail . | awk 'NR==2 {gsub(/G/,"",$1); print $1}')"
  if [[ "$libres_gb" -ge 5 ]]; then
    ok "tras las descargas quedan ${libres_gb} GB libres"
  else
    fallo "tras las descargas quedan ${libres_gb} GB; hacen falta 5 GB para la clase"
    return
  fi

  echo "+ arrancando el modelo"
  if ! docker compose up -d modelo; then
    fallo "docker compose up"
    return
  fi

  local i
  for i in $(seq 1 90); do
    if curl -fsS -o /dev/null --max-time 3 http://127.0.0.1:8088/salud 2>/dev/null; then
      ok "modelo en marcha"
      break
    fi
    if ! docker compose ps --status running --quiet modelo | grep -q .; then
      fallo "el contenedor del modelo se detuvo"
      docker compose logs --tail 40 modelo || true
      return
    fi
    if oom="$(alguno_oom)"; then
      fallo "contenedor muerto por memoria: $oom"
      docker compose logs --tail 40 modelo || true
      return
    fi
    if [[ "$i" -eq 90 ]]; then
      fallo "el modelo no respondió en /salud"
      docker compose logs --tail 40 modelo || true
      return
    fi
    sleep 2
  done

  t_llm="$(curl -sS --max-time "$LLM_MAX_S" -o /tmp/puesto-chat.json -w '%{time_total}' \
    -H 'content-type: application/json' \
    -d '{"messages":[{"role":"user","content":"di ok"}],"max_tokens":16}' \
    http://127.0.0.1:8088/v1/chat/completions || true)"
  if [[ -z "$t_llm" ]] || ! grep -q '"content"' /tmp/puesto-chat.json 2>/dev/null; then
    fallo "el modelo no contestó en ${LLM_MAX_S}s"
    docker compose logs --tail 40 modelo || true
    return
  fi
  ok "respuesta del modelo en ${t_llm}s"

  if oom="$(alguno_oom)"; then
    fallo "contenedor muerto por memoria: $oom"
    return
  fi

  local inicio
  inicio="$SECONDS"
  salida="$(docker compose --profile paso run --rm --no-deps paso)" || {
    fallo "el segundo contenedor no terminó"
    printf '%s\n' "$salida"
    return
  }
  t_lab="$((SECONDS - inicio))"
  if [[ "$t_lab" -gt "$LAB_MAX_S" ]] || ! grep -q 'OK paso' <<<"$salida"; then
    fallo "el segundo contenedor no dio OK en ${LAB_MAX_S}s"
    printf '%s\n' "$salida"
    return
  fi
  ok "segundo contenedor en ${t_lab}s"

  if oom="$(alguno_oom)"; then
    fallo "contenedor muerto por memoria: $oom"
    return
  fi

  docker compose stop >/dev/null 2>&1
  ok "contenedores parados"
  echo "PUESTO_OK cpu=$(nproc) ram_gb=$(($(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 / 1024)) llm_s=${t_llm} lab_s=${t_lab}"
}

comprobar_equipo
if [[ "$FALLOS" -gt 0 ]]; then
  echo "FALLOS=$FALLOS"
  exit 1
fi

if [[ "$SOLO_EQUIPO" -eq 1 ]]; then
  echo "EQUIPO_OK"
  exit 0
fi

comprobar_desempeno
if [[ "$FALLOS" -gt 0 ]]; then
  echo "FALLOS=$FALLOS"
  exit 1
fi
