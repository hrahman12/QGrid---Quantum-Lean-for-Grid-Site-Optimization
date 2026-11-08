# data/shared/social schema

Built 2026-11-08 for the QSiteProof Alviso / North San Jose case (NOVVA Colorado Springs partial). Complements `../socio/{alviso,novva}.json` (consent layer); nothing there is duplicated, only linked by URL. All stance/influence/weight values are ASSUMED judgments unless stated.

## Collection log (read first)
- Hacker News Algolia API: 11 queries (`search_by_date`, stories since 2025-01-01) cached in `raw/hn_q*.json`. `author` fields were removed. 110 data-center stories kept. No HN story named Alviso or Colorado Springs data centers, so HN is national discourse (`scope: national`).
- Reddit public JSON (`/r/{SanJose,bayarea,ColoradoSprings}/search.json`, also old.reddit.com): HTTP 403 from this host with UA `qsiteproof-hackathon/0.1`; not circumvented. Local Reddit data is limited to two threads and 13 captured comments read from the `reddit.sentinel-team.org` archive (already referenced by `socio/*.json`). Comment text is paraphrased, no usernames. r/bayarea was not collected. Retry from another network or with OAuth to extend.
- Post dates for the two Reddit threads are approximate (the mirror's "days before snapshot" conflicts with the thread ids).

## social_posts.json (array)
`id_hash` (sha256 prefix of platform id), `platform` (hackernews|reddit), `kind` (story|post|comment), `scope` (national|local_sj|local_cos), `date` (YYYY-MM-DD or YYYY-MM), `title` (<=200 chars; headline or paraphrase), `url`, `score`, `num_comments`, `stance`, `topics[]`, optional `source`, `subreddit`, `date_note`, `text_is_paraphrase`.

Stance rule (headline-level, not a model): `oppose` if title matches backlash|moratorium|ban|protest|furious|rebel|revolt|resist|NIMBY|oppos|freeze|pause|brakes|irks|reckoning|war on|refused|rage|limits|veto|blocks|flee...; `support` if invest|"you'd love"|win-win|prettier|beautiful; else `neutral`. Manual overrides in `build` were applied for headlines the regex misreads (e.g. "China is fueling America's data center rage" = support, as it frames opposition as manufactured; "Maine Said No..." = oppose). Stance means the story's framing toward siting/building new data centers, not the poster's identity. Reddit comments were labelled manually.

Topics are keyword tags: power, bills, water, noise, jobs, taxes, wildlife, heat_reuse, moratorium, politics, transparency.

## social_summary.json
`all`, `posts_only_excluding_reddit_comments`, and `by_scope.{national,local_sj,local_cos}` each give `n`, `by_stance`, `by_topic`, `monthly_stance{YYYY-MM:{stance:n}}`, `monthly_topic`. Sample is small and not representative.

## opposition_events.json
`events[]`: `site` (alviso|novva), `date`, `actor`, `event` (petition|council_comment|protest|lawsuit|op-ed|appeal; `appeal` added), `size` (free text, as reported), `url`, `evidence` (fetched|search_snippet|mirror_snapshot). Colorado Springs events are about Project Taurus (Raeden), not NOVVA; no NOVVA-specific opposition found. No op-ed and no Alviso data-center lawsuit were found (the Audubon 2017 Topgolf suit is a precedent). Mercury News and NBC Bay Area results were not retrieved.

## stakeholders.json
`nodes[]`: `id`, `name`, `type` (residents_group|elected|city_staff|utility|regulator|developer|labor|environmental|media|tribal), `site`, `stance` (-1 opposes siting .. +1 supports), `influence` (0..1), `rationale` (one line, ASSUMED), `evidence_urls[]` (empty = general-knowledge ASSUMED node), `stance_influence_status`.
`edges[]`: `from`, `to`, `kind` (pressures|funds|regulates|endorses|opposes|reports_on), `weight` (0..1), `rationale`. Edge kinds are approximated where the relation is contractual (e.g. PG&E to Prologis).

## engagement_levers.json
`levers[]`: `id`, `name`, `description`, `addresses_stakeholders[]` (node ids), `topics_addressed[]`, `evidence[]{claim,url}` (mostly analogies from other places; several developer-announced), `evidence_strength` (low|medium, judgment), `caveat`.
