# Resultados do modelo de previsão

Gerado por `python -m ml.treinar`. Alvo: nível de sobrecarga de 0 a 100 (média de ruído, luz e lotação).
Dados: 6000 avaliações de 24 lugares — fontes: {'sintetico': 6000}.

| Cenário | Modelo (MAE / R²) | Média geral (MAE / R²) | Média por categoria e hora (MAE / R²) |
| --- | --- | --- | --- |
| teste aleatório (20% das avaliações) | **8.21 / 0.749** | 17.23 / -0.0 | 8.82 / 0.711 |
| lugares novos (nunca vistos) | **8.33 / 0.728** | 17.14 / -0.021 | 8.42 / 0.724 |

MAE em pontos da escala 0–100 (menor é melhor). R² = quanto da variação o modelo explica (1 = tudo).

## Checagens de bom senso

| Caso | Previsto (cheio) | Previsto (vazio) | Resultado |
| --- | --- | --- | --- |
| UBS: segunda 8h deve ser mais cheia que segunda 16h | 72 | 23 | ok |
| Terminal: quarta 18h mais cheio que domingo 18h | 79 | 33 | ok |
| Parque: sábado 11h mais cheio que terça 11h | 76 | 31 | ok |
| Poupatempo: segunda 10h mais cheio que sexta 17h | 70 | 27 | ok |
| Biblioteca: terça 9h mais calma que terça 15h | 61 | 21 | ok |
