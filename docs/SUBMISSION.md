# QSiteProof (QGrid): find quantumly, check physically, prove formally

About $3 trillion is going into data centers by 2030, yet $130 billion of US projects stalled in a single quarter this year. The money is there. Power, permits and people are not.

QSiteProof gives developers, investors and cities a clear answer to "can I build here, how much, and how soon?" in four steps:
1. **Define** the site.
2. **Find** connection plans with a fast search that checks many options at once (Grover quantum search) on a quantum simulator (PsiQDK).
3. **Check** them on a power-grid simulation (pandapower) of the real local grid, including what happens if one transformer fails (N-1).
4. **Prove** them against rules in a math proof checker (Lean 4): grid, climate risk, nature, community, economics and timeline.

Each run ends in a single RED, AMBER or GREEN answer, plus the "what if" conditions that would make the project viable. Every "no" becomes a constraint for the next round, so the agent learns as it goes.

Real data: utility grid capacity (PG&E), substations and live electricity prices; FEMA climate hazards, satellite land data, protected areas and wetlands; Census, energy and environmental-justice data; public social media, local news and a map of key decision-makers; colocation data-center data from existing and in-development campuses.

**Example, 150 MW in North San Jose: RED, "Grid too small".** About 40 MW is guaranteed now, 47.6 MW if use is paused in a few peak hours, about 2% (curtailment), and it turns GREEN by phasing in edge sites, adding storage and signing a community agreement. The same analysis runs in Colorado, Utah and Arizona, and works for any country.

A screening tool, not a utility approval. The quantum search runs on a simulator; no speed-up is claimed.

Tracks: 1 (Identify suitable sites), 2 (Assess grid capacity at the edge). Team: Alejandro Delmar, Hannah Rahman, Manvender Singh.
Live demo: https://q-grid-quantum-lean-for-grid-site-o.vercel.app/
