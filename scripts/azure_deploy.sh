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
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

echo "==> 6) Comando de inicialização (FastAPI com gunicorn)"
az webapp config set \
  --resource-group "$RG" \
  --name "$APP" \
  --output none \
  --startup-file "gunicorn -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 120 app.main:app"

echo "==> 7) Empacotando o código (só o necessário para rodar)"
PACOTE="$(mktemp -d)/sereno-ia.zip"
ARQUIVOS="requirements.txt app ml/modelo ml/dados/locais.json rag/indice"
if command -v zip >/dev/null 2>&1; then
  zip -qr "$PACOTE" $ARQUIVOS -x '*__pycache__*' '*.pyc'
else
  python3 - "$PACOTE" $ARQUIVOS <<'EOF'
import sys, zipfile
from pathlib import Path
destino, itens = sys.argv[1], sys.argv[2:]
with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
    for item in itens:
        p = Path(item)
        for arq in ([p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())):
            if "__pycache__" not in arq.parts and arq.suffix != ".pyc":
                z.write(arq, arq.as_posix())
EOF
fi

echo "==> 8) Deploy do pacote (a Azure instala o requirements.txt; a 1ª vez leva alguns minutos)"
az webapp deploy \
  --resource-group "$RG" \
  --name "$APP" \
  --src-path "$PACOTE" \
  --type zip

URL="https://$APP.azurewebsites.net"
echo "==> 9) Testando $URL/ia/health (o 1º acesso demora: carrega o modelo)"
for i in $(seq 1 20); do
  RESPOSTA="$(curl -s --max-time 60 "$URL/ia/health" || true)"
  if [[ "$RESPOSTA" == *'"status":"UP"'* ]]; then
    echo "$RESPOSTA"
    echo
    echo "URL da aplicação: $URL"
    echo "Swagger:          $URL/ia/docs"
    exit 0
  fi
  echo "   aguardando... ($i/20)"
  sleep 20
done
echo "Não respondeu ainda. Veja os logs: az webapp log tail --resource-group $RG --name $APP"
exit 1

# LIMPAR O LABORATÓRIO (apaga tudo; não rode antes da correção!)
# az group delete --name rg-sereno --yes --no-wait