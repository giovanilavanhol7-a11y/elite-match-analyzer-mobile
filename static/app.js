/* ======================================================
   CANDIDATOS DA SUGESTÃO PRINCIPAL

   NOVA REGRA:

   1. Todas as linhas são avaliadas individualmente.
   2. Precisam passar nos últimos 10.
   3. Precisam passar também nos últimos 5.
   4. Só depois escolhemos a maior linha
      segura de cada métrica.
====================================================== */

function primaryCandidates(data) {
  const homeName =
    data.home?.name ||
    currentFixture.home.name;


  const awayName =
    data.away?.name ||
    currentFixture.away.name;


  const homeCross =
    data.cross_samples
      ?.last_10
      ?.home ||
    data.cross?.home ||
    [];


  const awayCross =
    data.cross_samples
      ?.last_10
      ?.away ||
    data.cross?.away ||
    [];


  const homeItems =
    prepareTeamLines(
      homeName,
      homeCross,
      data
    );


  const awayItems =
    prepareTeamLines(
      awayName,
      awayCross,
      data
    );


  /*
    Primeiro:
    a linha precisa passar nos 10
    E também passar no filtro recente.
  */

  const homeStrong =
    homeItems.filter(
      item =>
        linePassesFilters(item) &&
        passesRecentPrimaryFilter(
          item,
          data
        )
    );


  const awayStrong =
    awayItems.filter(
      item =>
        linePassesFilters(item) &&
        passesRecentPrimaryFilter(
          item,
          data
        )
    );


  /*
    Agora, entre SOMENTE as linhas
    que passaram nos dois períodos,
    escolhemos a maior por métrica.
  */

  const homeBest =
    chooseHighestApprovedPerMetric(
      homeStrong
    );


  const awayBest =
    chooseHighestApprovedPerMetric(
      awayStrong
    );


  return sortOpportunities([
    ...homeBest,
    ...awayBest
  ]);
}


/* ======================================================
   ESCOLHER UMA ÚNICA SUGESTÃO PRINCIPAL
====================================================== */

function selectPrimarySuggestion(data) {
  const candidates =
    primaryCandidates(
      data
    );


  if (!candidates.length) {
    return null;
  }


  /*
    primaryCandidates já devolve
    apenas linhas que:

    - passaram nos últimos 10
    - passaram nos últimos 5
    - têm amostra recente suficiente
    - não estão enfraquecendo
    - são a maior linha segura
      da própria métrica

    Então basta pegar a melhor
    do ranking final.
  */

  return candidates[0];
}
