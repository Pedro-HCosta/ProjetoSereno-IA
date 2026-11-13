#!/usr/bin/env bash
# =====================================================================
#  Sereno - Serviço de IA no Azure App Service (Web App Linux, plano F1)
#  Baseado na Aula 13 (Criando um Web App): az provider register,
#  az webapp up e az webapp config.
#
#  Como usar (Cloud Shell do Portal, igual à aula, ou Git Bash/Linux):
#    git clone <link do repositório sereno-ia>
#    cd sereno-ia
#    bash scripts/azure_deploy.sh
#
#  Credenciais: o script lê JWT_SECRET e AI_API_KEY do .env (se existir)
#  ou pergunta na hora. Elas vão só para as Configurações do Web App,
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
for f in ml/modelo/modelo_previsao.joblib rag/indice/leis.faiss ml/dados/locais.json; do
  [ -f "$f" ] || { echo "ERRO: falta $f (rode: python iniciar.py treinar)"; exit 1; }
done

echo "==> 1) Registrando o serviço de Web App na assinatura"
az provider register --namespace Microsoft.Web --wait

echo "==> 2) Criando Grupo de Recursos, Plano e Web App e fazendo o deploy (az webapp up)"
# Copia o diretório atual para o Azure (ignora .env e pastas de ambiente virtual)
# e instala o requirements.txt na nuvem
az webapp up \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --plan "$PLAN" \
  --name "$APP" \
  --runtime "$RUNTIME" \
  --os-type Linux \
  --sku "$SKU" \
  --logs

echo "==> 3) Configurações do aplicativo (variáveis de ambiente)"
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

echo "==> 4) Comando de inicialização (FastAPI com gunicorn) e só HTTPS"
az webapp config set \
  --resource-group "$RG" \
  --name "$APP" \
  --output none \
  --startup-file "gunicorn -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 120 app.main:app"
az webapp update --resource-group "$RG" --name "$APP" --https-only true --output none

echo "==> 5) Reiniciando o Web App"
az webapp restart --resource-group "$RG" --name "$APP"

URL="https://$APP.azurewebsites.net"
echo "==> 6) Testando $URL/ia/health (o 1º acesso demora: carrega o modelo)"
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
