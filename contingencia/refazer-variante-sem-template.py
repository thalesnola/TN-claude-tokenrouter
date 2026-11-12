#!/usr/bin/env python3
"""Recria a variante :NOTPL do Qwen3-Coder-Next sem a camada de template.

POR QUE ISTO EXISTE (medido em 31/08/2026, Ollama 0.33.2 no Windows):

1. `ollama create` esta inutil nesta versao (0.33.2; voltou a funcionar no 0.34.2, testado em 30/09/2026 — este script deixou de ser obrigatorio). Ele grava o manifesto em
   `manifests/registry.ollama.ai/library/<nome>/<tag>` e NENHUM modelo dali
   carrega -- responde 404 "model not found", mesmo derivando de um modelo
   da propria biblioteca. Diz `success` e aparece no `ollama list`; so falha
   na hora de usar. Reinstalar o Ollama NAO corrige.

2. A resolucao so funciona no namespace de ONDE o modelo foi puxado. Por isso
   este script grava dentro de `manifests/hf.co/unsloth/...`, ao lado do
   original, e nao em `library/`.

Rode depois de qualquer novo `ollama pull` do modelo base, ou se o manifesto
:NOTPL sumir. Idempotente.
"""
import json, os, hashlib, sys

HOME = os.path.expanduser('~/.ollama/models')
BLOBS = os.path.join(HOME, 'blobs')
DIR = os.path.join(HOME, 'manifests', 'hf.co', 'unsloth', 'Qwen3-Coder-Next-GGUF')
BASE, ALVO = 'UD-Q3_K_XL', 'NOTPL'
NUM_CTX = 65536

def put(obj):
    b = json.dumps(obj, separators=(',', ':')).encode()
    d = hashlib.sha256(b).hexdigest()
    with open(os.path.join(BLOBS, 'sha256-' + d), 'wb') as f:
        f.write(b)
    return 'sha256:' + d, len(b)

def main():
    src = os.path.join(DIR, BASE)
    if not os.path.exists(src):
        sys.exit(f'base ausente: {src}\nrode antes:\n'
                 '  ollama pull hf.co/unsloth/Qwen3-Coder-Next-GGUF:UD-Q3_K_XL')
    m = json.load(open(src))
    modelo = [l for l in m['layers'] if l['mediaType'].endswith('image.model')][0]
    pd, ps = put({"num_ctx": NUM_CTX, "temperature": 0.2, "top_p": 0.8, "repeat_penalty": 1.05})
    # A camada de template do GGUF fica DE FORA de proposito.
    camadas = [modelo, {"mediaType": "application/vnd.ollama.image.params",
                        "digest": pd, "size": ps}]
    cd, cs = put({"model_format": "gguf", "model_family": "qwen3next",
                  "model_families": ["qwen3next"], "model_type": "79.7B",
                  "file_type": "Q3_K_XL", "architecture": "amd64", "os": "linux",
                  "rootfs": {"type": "layers",
                             "diff_ids": [l['digest'] for l in camadas]}})
    man = {"schemaVersion": 2,
           "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
           "config": {"mediaType": "application/vnd.docker.container.image.v1+json",
                      "digest": cd, "size": cs},
           "layers": camadas}
    with open(os.path.join(DIR, ALVO), 'w') as f:
        json.dump(man, f)
    print(f'ok: hf.co/unsloth/Qwen3-Coder-Next-GGUF:{ALVO} (num_ctx={NUM_CTX})')
    print('confira: ollama list | grep NOTPL')

if __name__ == '__main__':
    main()
