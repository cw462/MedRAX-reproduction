# Tool preparation stopped on inconsistent file reads

No new paid API calls were made after the user's instruction to prioritize the complete tool set. Current conservative ledger occupancy remains **CNY 21.02928**, with **78.97072 remaining**. Formal baseline and memory experiments have not started.

The remaining three tools' environments now pass official class/schema import checks. This includes the required Transformers versions and LangChain Core/Pydantic dependencies. A CheXagent source check was corrected to compare the pinned upstream LF-normalized source across Windows CRLF and Linux LF checkouts, while still recording actual raw-byte hashes. These checks explicitly report `model_loaded=false`; they are not real large-model inference results.

## Observed integrity failure

A downloaded CheXagent shard had the correct 4,982,355,512-byte length but failed its official SHA256. Download preparation therefore changed to bounded 16 MiB transfers with remote read-back validation, followed by a mandatory whole-file official digest. The server can fetch official Hugging Face CDN URLs directly after authorized origin resolution; this does not require sending the Hugging Face token to the CDN or server.

All 297 chunks of the first shard were transferred, but later validation found two chunks inconsistent with their recorded hashes. Repeated read-only checks then reproduced a stronger issue:

- Six retained reads of one 16 MiB chunk produced different bytes on two reads: one and two differing bytes, respectively.
- The device/inode, file size, modification time and change time remained unchanged.
- Re-reading through the **same open file descriptor** reproduced differing hashes under both the environment Python and the system Python, with `-I -S` excluding site initialization. The environment run differed on one of six reads; the system-Python run differed on two of six reads.
- Repeated OpenSSL SHA256 and Python's separate builtin SHA256 agreed when given the **same already-read bytes**. Thus the observations do not point to a simple hash-implementation disagreement.
- No task downloader process was found in the checked server process listing at the time of these read-only follow-ups. A small 80 MiB constant-pattern memory check passed; that is not an exhaustive memory or storage test. Available filtered kernel logs did not establish a specific hardware failure.

These observations establish inconsistent read results in this environment. They do **not** identify a failed DIMM, disk, CPU, kernel or filesystem as the cause. The downloader review also identified an independent software risk: SSH-timeout retries did not prove the previous remote attempt had exited and reused temporary names. That path needs unique temporary files, locking and remote lifetime control, but has not been established as the cause of the same-descriptor read observations.

## Preserved state and resumption gate

Download retries and the automatic continuation to local GPU tests have stopped. Partial chunks, manifests, failed assembled files and private diagnostic evidence are preserved outside Git. No unverified large model was loaded. The complete required runtime asset manifest has **60 files / 59,548,387,625 bytes**; that number is required size, not completed or verified download size.

Before continuing, establish stable repeated reads and writes in the server environment, then repair the downloader's timeout/temporary-file handling, revalidate retained chunks and require the official digest for every full asset. A single lucky matching read is insufficient. Only after verified assets, real standalone inference and real process-bridge checks may the complete Agent protocol be frozen and paid comparisons resumed.

Earlier small-tool functional records remain unchanged. This later integrity observation is documented as a limitation; it does not prove that any specific earlier answer was affected. Those records must not be promoted to a formal full-tool reproduction result.
