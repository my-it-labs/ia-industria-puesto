FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/opt

WORKDIR /opt

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt \
    && pip install --no-deps \
        https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.19/llama_cpp_python-0.3.19-cp312-cp312-linux_x86_64.whl \
    && rm -rf /root/.cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends musl libgomp1 \
    && ln -sf /lib/x86_64-linux-musl/libc.so /lib/libc.musl-x86_64.so.1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir diskcache==5.6.3

COPY linea /opt/linea

ENTRYPOINT ["python", "-m"]
