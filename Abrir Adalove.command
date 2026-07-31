#!/bin/bash
# Double-click launcher (macOS): starts the local server and opens the
# dashboard in the browser — no typing required. Closing this Terminal
# window stops the server.
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Ambiente virtual não encontrado. Rode a instalação primeiro (veja o README)."
  read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
  exit 1
fi

source .venv/bin/activate
adalove serve
