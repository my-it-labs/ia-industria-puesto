FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install --upgrade pip \
    && pip install fastapi==0.115.4 uvicorn==0.32.0 numpy==2.1.3 jinja2==3.1.6 diskcache==5.6.3 \
    && pip install --no-deps \
        https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.19/llama_cpp_python-0.3.19-cp312-cp312-linux_x86_64.whl \
    && rm -rf /root/.cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends musl libgomp1 \
    && ln -sf /lib/x86_64-linux-musl/libc.so /lib/libc.musl-x86_64.so.1 \
    && rm -rf /var/lib/apt/lists/*

COPY prueba.py paso.py /opt/
WORKDIR /opt
