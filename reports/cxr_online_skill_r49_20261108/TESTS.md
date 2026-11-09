# Actual pre-execution checks

Raw supplied package:17 synthetic tests passed3.712s. Adapted integrated R49 suite:30 tests passed5.195s. Three scoring-boundary tests passed0.813s after final scorer-only closure changes. Six execution-boundary tests passed0.097s after final services-only terminal-raw/text-control cache change. Tests use synthetic temporary cases, not benchmark reference answers or medical-quality validation.

New server support created once; first dryrun harness failed import resolution before any API/reference access. Adding the script directory to harness sys.path resolved it. Three actual zero-API, zero-reference-content-read dryruns then passed: CheX618/488groups/130followups/21windows; SLAKE114/30groups/84followups/4windows; VQA116/58groups/58followups/4windows. The harness forbids network connects and opening files under the reference vault. No medical probes,environment install or weight changes.

One separately metered official DashScope embedding probe returned text-embedding-v4,1024finite dimensions,13tokens,in1.309259s. This establishes interface availability,not clinical or retrieval quality.

No originalfile/byte/pixel/hash verification gates. NewR49filesonly; current/futuretruth remains unavailable until currentprediction andpredictioneventsave. Full original toolcache and imagepublisher namingmechanics unchanged.
