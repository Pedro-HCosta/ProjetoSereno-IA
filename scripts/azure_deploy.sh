#!/usr/bin/env bash
# =====================================================================
#  Sereno - Serviço de IA no Azure App Service (Web App Linux, plano F1)
#  Baseado na Aula 13 (Criando um Web App), com az webapp create e
#  az webapp deploy.
#
#  Como usar (Cloud Shell do Portal, em Bash, ou Git Bash/Linux com az login):
#    git clone https://github.com/Pedro-HCosta/ProjetoSereno-IA.git
#    cd ProjetoSereno-IA
#    bash scripts/azure_deploy.sh
#
#  Credenciais: lê JWT_SECRET e AI_API_KEY do .env (se existir) ou pergunta
#  na hora, sem mostrar na tela. Elas vão só para as Configurações do Web App,
#  nunca para o código.
# =====================================================================
set -euo pipefail

# ---------- Altere aqui se precisar ----------
RG="rg-sereno"                 # Grupo de Recursos
LOCATION="brazilsouth"         # Região
PLAN="planSereno"              # Plano (o .NET pode usar o mesmo)
APP="sereno-ia-rm563009"       # Nome do Web App (RM do dono da assinatura)
SKU="F1"                       # F1 = Free
RUNTIME="PYTHON:3.12"
JAVA_API_URL="https://sereno-api-ayhx.onrender.com"
# --------------------------------------------

cd "$(dirname "$0")/.."        # raiz do projeto (onde está o requirements.txt)

# Lê uma variável do .env sem executar o arquivo
ler_env() {
  [ -f .env ] || return 0
  grep -E "^$1=" .env | tail -n1 | cut -d= -f2- | tr -d '\r"' || true
}

JWT_SECRET="${JWT_SECRET:-$(ler_env JWT_SECRET)}"
AI_API_KEY="${AI_API_KEY:-$(ler_env AI_API_KEY)}"
JWT_SECRET_BASE64="${JWT_SECRET_BASE64:-$(ler_env JWT_SECRET_BASE64)}"

if [ -z "$JWT_SECRET" ] || [[ "$JWT_SECRET" == troque-por* ]]; then
  read -rsp "JWT_SECRET (o mesmo do Java e do .NET): " JWT_SECRET; echo
fi
if [ -z "$AI_API_KEY" ]; then
  read -rsp "AI_API_KEY (chave do Groq): " AI_API_KEY; echo
fi
if [ ${#JWT_SECRET} -lt 32 ]; then
  echo "ERRO: o JWT_SECRET precisa ter pelo menos 32 caracteres."; exit 1
fi

# O modelo treinado e o índice das leis vão prontos no repositório
for f in requirements.txt ml/modelo/modelo_previsao.joblib rag/indice/leis.faiss ml/dados/locais.json; do
  [ -f "$f" ] || { echo "ERRO: falta $f (rode: python iniciar.py treinar)"; exit 1; }
done

echo "==> 1) Registrando o serviço de Web App na assinatura"
az provider register --namespace Microsoft.Web --wait

echo "==> 2) Criando o Grupo de Recursos"
az group create \
  --name "$RG" \
  --location "$LOCATION" \
  --output none

echo "==> 3) Criando o Plano de Serviço (Linux, $SKU)"
if az appservice plan show --resource-group "$RG" --name "$PLAN" --output none 2>/dev/null; then
  echo "   plano já existe, reaproveitando"
else
  az appservice plan create \
    --resource-group "$RG" \
    --name "$PLAN" \
    --location "$LOCATION" \
    --sku "$SKU" \
    --is-linux \
    --output none
fi

echo "==> 4) Criando o Web App ($RUNTIME)"
if az webapp show --resource-group "$RG" --name "$APP" --output none 2>/dev/null; then
  echo "   Web App já existe, reaproveitando"
else
  az webapp create \
    --resource-group "$RG" \
    --plan "$PLAN" \
    --name "$APP" \
    --runtime "$RUNTIME" \
    --https-only true \
    --output none
fi

echo "==> 5) Configurações do aplicativo (variáveis de ambiente)"
az webapp config appsettings set \
  --resource-group "$RG" \
  --name "$APP" \
  --output none \
  --settings \
    JWT_SECRET="$JWT_SECRET" \
    JWT_ISSUER="sereno-auth" \
    JWT_AUDIENCE="sereno-app" \
    JWT_SECRET_BASE64="${JWT_SECRET_BASE64:-false}" \
    AI_API_KEY="$AI_API_KEY" \
    AI_BASE_URL="https://api.groq.com/openai/v1" \
    AI_MODEL="openai/gpt-oss-120b" \
    AI_REASONING_EFFORT="low" \
    AI_TIMEOUT="10" \
    AI_MAX_TOKENS="2048" \
    CACHE_TTL="3600" \
    JAVA_API_URL="$JAVA_API_URL" \
    JAVA_TIMEOUT="8" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="false" \
    ENABLE_ORYX_BUILD="false" \
    PYTHONPATH="/home/site/wwwroot/__oryx_packages__"
# As dependências vão prontas no pacote (passo 7): o instalador da Azure (Oryx) trava no plano F1.
# Mudar as configurações também reinicia o Kudu, o que cancela algum deploy antigo que tenha travado.

echo "==> 6) Comando de inicialização (FastAPI com gunicorn)"
az webapp config set \
  --resource-group "$RG" \
  --name "$APP" \
  --output none \
  --startup-file "python -m gunicorn -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 120 app.main:app"

echo "==> 7) Montando o pacote com as dependências já instaladas (Linux, Python 3.12)"
PY="$(command -v python3 || command -v python)"
BUILD="$(mktemp -d)"
PACOTE="$(mktemp -d)/sereno-ia.zip"
cp -r requirements.txt app ml rag "$BUILD"/
rm -rf "$BUILD"/ml/dados/avaliacoes_sinteticas.csv "$BUILD"/rag/leis "$BUILD"/rag/avaliacao
# Baixa as versões prontas para o servidor da Azure (manylinux, CPython 3.12), seja qual for o PC
"$PY" -m pip install --quiet --disable-pip-version-check \
  --requirement requirements.txt --no-warn-conflicts --no-warn-script-location \
  --target "$BUILD/__oryx_packages__" \
  --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 \
  --python-version 3.12 --implementation cp --only-binary=:all:
if command -v zip >/dev/null 2>&1; then
  (cd "$BUILD" && zip -qr "$PACOTE" . -x '*__pycache__*' '*.pyc')
else
  (cd "$BUILD" && "$PY" - "$PACOTE" <<'EOF'
import os, sys, zipfile
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED) as z:
    for raiz, pastas, arquivos in os.walk("."):
        pastas[:] = [p for p in pastas if p != "__pycache__"]
        for a in arquivos:
            if not a.endswith(".pyc"):
                z.write(os.path.join(raiz, a))
EOF
  )
fi
echo "   pacote: $(du -h "$PACOTE" | cut -f1)"

echo "==> 8) Deploy do pacote (sem instalação na Azure: só copia os arquivos)"
# --clean true apaga o que sobrou de deploys anteriores; --async true evita o HTTP 502 por tempo no F1
az webapp deploy \
  --resource-group "$RG" \
  --name "$APP" \
  --src-path "$PACOTE" \
  --type zip \
  --clean true \
  --async true

URL="https://$APP.azurewebsites.net"
echo "==> 9) Esperando $URL/ia/health responder (cópia dos arquivos + 1º acesso; alguns minutos)"
echo "   Para ver os logs, em outra aba: az webapp log tail --resource-group $RG --name $APP"
for i in $(seq 1 45); do
  RESPOSTA="$(curl -s --max-time 60 "$URL/ia/health" || true)"
  if [[ "$RESPOSTA" == *'"status":"UP"'* ]]; then
    echo "$RESPOSTA"
    echo
    echo "URL da aplicação: $URL"
    echo "Swagger:          $URL/ia/docs"
    exit 0
  fi
  echo "   aguardando... ($i/45)"
  sleep 20
done
echo "Não respondeu ainda. Veja: az webapp log deployment show --resource-group $RG --name $APP"
echo "e:      az webapp log tail --resource-group $RG --name $APP"
exit 1

# LIMPAR O LABORATÓRIO (apaga tudo; não rode antes da correção!)
# az group delete --name rg-sereno --yes --no-wait