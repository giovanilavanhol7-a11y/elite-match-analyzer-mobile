ELITE MATCH ANALYZER MOBILE V2
================================

Esta versão é um projeto NOVO e separado do Elite Analyzer antigo.

O que já existe:
- Site feito para celular.
- Tela "Jogos de hoje".
- Servidor Flask.
- Endpoint de saúde.
- Endpoint de partidas do dia.
- Tela de análise.
- Últimos 5 ou 10 jogos.
- Gols.
- Escanteios.
- Finalizações.
- Chutes no gol.
- Cartões.
- Faltas.
- Modo DEMO claramente identificado.
- Estrutura pronta para Render.

IMPORTANTE
----------
Enquanto DEMO_MODE=true, os jogos e estatísticas mostrados são exemplos.
Isso foi feito de propósito para NUNCA mostrar dado falso como se fosse real.

COMO TESTAR NO COMPUTADOR
-------------------------
1. Instale Python.
2. Abra a pasta.
3. Execute INICIAR_SITE.bat.
4. Abra http://127.0.0.1:5000 no navegador.

COMO ATIVAR A API REAL
----------------------
O projeto foi preparado para API-FOOTBALL / API-SPORTS.

Crie estas variáveis de ambiente:
API_FOOTBALL_KEY = sua chave
DEMO_MODE = false
APP_TIMEZONE = America/Sao_Paulo

A chave NÃO deve ser escrita no JavaScript e NÃO deve ficar exposta no site.

NO RENDER
---------
1. Crie um novo Web Service.
2. Envie esta pasta para um repositório GitHub.
3. O render.yaml já contém build/start.
4. Adicione API_FOOTBALL_KEY nas Environment Variables.
5. Troque DEMO_MODE para false somente quando a chave estiver configurada.

OBSERVAÇÃO SOBRE ESTATÍSTICAS
-----------------------------
Nesta V2, a integração real calcula médias usando partidas recentes finalizadas
e o endpoint de estatísticas de cada fixture.

Antes de liberar recomendações de aposta, precisamos validar em partidas reais:
- se Corner Kicks corresponde a escanteios;
- se Total Shots corresponde a finalizações;
- se Shots on Goal corresponde a chutes no gol;
- se Fouls corresponde a faltas;
- se Yellow Cards + Red Cards será a regra desejada para cartões;
- se o recorte casa/fora deve ser separado do geral.

Por segurança, a V2 NÃO gera "melhores apostas" com dados reais ainda.
Primeiro validamos os números.
