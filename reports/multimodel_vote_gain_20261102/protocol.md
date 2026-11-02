# Multi-model independent-answer voting: protocol, 2026-11-02

Status: code and plan publication only, at the user's latest instruction. No new
inference was launched and no new experimental result is reported here.
The user authorized the attached *MedRAX performance-gain plan* using
`qwen3-vl-plus`, `qwen3.8-max-0902`, and `gpt-4o`.
The user replaced Kimi with GPT-4o on 2026-11-02 before any inference;
GPT-4o uses the user's APIYi endpoint and a separate private credential.
The user has approved a **CNY 200 incremental cap**, for the basic-answer and
voting stages first. Full-benchmark/heldout expansion is not automatically
launched under this first-stage authorization. No result is claimed in this protocol.
The user subsequently declined the always-nine GPT-4o expansion and its possible
2,412 additional calls. Preserve the existing three-or-nine rule, two-question
smokes, no added Qwen-Max text-only arm and the CNY 200 cap. This review revision
changes failure handling and image-metadata wording only; no inference is launched.

## Question and design

Does aggregating independent answers improve over one direct answer on the same
backbone, and does a three-model ensemble improve further? This is a fresh run;
previous experiments and predictions remain intact. There is no answer-revision
judge, memory injection, online feedback or new ReAct loop in the main arms.

1. Infrastructure regression: regenerate the old 60-question direct baseline once,
   as the plan explicitly requests. Its historical derived score is 42/60.
   This is a pipeline check, not a new heldout result or tuning set. Separately
   run two old questions per new model/high-resolution/thinking capability.
2. Tune on 402 questions (99 cases) grouped by explicit source case ID:
   historical direct prompt, text only, native images with explicit figure labels
   and provider high-resolution mode, concise evidence summary (at most 150
   words), and provider thinking mode. Retain the direct setting unless a
   visual candidate improves tune accuracy by at least 1.5 percentage points.
   Text only is the attachment's diagnostic control and is not a visual
   configuration eligible for advancement.
3. Draw nine independent samples at Qwen temperature 0.7. Evaluate the fixed
   first K samples for K=1,3,5,7,9. Two hundred random subsets describe variance;
   they are not 200 additional deployable systems or a source of selected votes.
   Every sample starts from the original question/options/images; previous
   answers and explanations never enter another sample's context.
4. Measure all three model single-call anchors and compare nine samples from the
   strongest tune model with three samples from each model. Remove the strongest
   model to form a six-sample diagnostic. Per the attachment's S4, each model
   first takes its own three-sample majority, then those three decisions are
   weighted by B0 tune accuracy. Pooling all nine sample votes is secondary.
   Freeze weights and
   strongest-model choice before any test labels are scored.
5. In a later authorized stage, score frozen arms once on the 1,002-question,
   241-case heldout set.
   A full 2,500-question result is separate: it includes seen and tuning cases
   and must not be called wholly heldout. Reuse a sample only when its complete
   frozen acquisition configuration and input match; never rerun for a better
   result. The full benchmark must finish before comparing its headline with
   the paper's full-benchmark result.

The two-question capability check confirms API acceptance and returned model
identity, not medical accuracy. An unsupported parameter/model is reported,
not silently substituted. Phase transitions freeze a new configuration and
code commit after the previous phase finishes and is scored offline.

## Attribution and documented deviations

The actual historical D prompt returns `Answer` plus one or two brief `Reason`
sentences. It does not forbid all reasoning as the attachment suggests. Its
literal prompt is preserved. A new derived parser accepts the last explicit
Answer line, including markdown and answer text; an ambiguous choice or refusal
remains missing. Previous prediction files and old parsers are not rewritten.

GPT-4o now has a B0 direct anchor and an independent sample arm. It receives
nine samples only if it is the strongest B0 model, otherwise three; no additional
paper-attribution A0/A1 arms are introduced. We request the `gpt-4o` alias and
archive its returned version. This does not establish the paper's exact snapshot
or reproduce its full dataset/prompt conditions, and cannot isolate a difference
from the paper as a voting-method effect.

Qwen direct anchors use T=0.2/top_p=0.95 with `enable_thinking=false` explicitly.
The dedicated Qwen thinking arm pins `enable_thinking=true`, uses streaming,
an 8,192 output ceiling and a 4,096 thinking budget. GPT-4o anchors use T=0.2
and independent samples T=0.7, both top_p=0.95 and max_tokens=2,048. Its ordinary
Chat Completions requests omit Qwen thinking/high-resolution parameters and
reasoning_effort. Only the exact `gpt-4o` alias or full `gpt-4o-YYYY-MM-DD`
returned identity is accepted; `gpt-4o-mini` and other suffixes are rejected.
Output truncation and absent final answers are retained, not repaired by a paid
format retry. Capabilities are tested before the large arms are frozen.

Nine sampled calls versus three times three sampled calls is a sample-count
comparison. Independent tie-break anchors add one versus three logical calls
unless their common acquisition cost is shared. Report both conventions and
actual tokens, reasoning usage, latency and monetary cost; different model
reasoning workloads are not equal compute merely because request counts match.

Plurality ties use the independent direct answer only if it is among the tied
leaders, then fixed alphabetical order. If all samples are invalid, the vote
stays missing. No confidence gate, label-conditioned subset, or hidden fallback
turns an invalid vote into a direct prediction.

## Data and image contract

Use the complete 2,500-row source `metadata.jsonl.new`; the older
`metadata.jsonl` download is truncated. Neither source file is rewritten.
Exclude actual historically exposed question/image/prediction/feedback/training
cases, including seed cases. A registry that only enumerates benchmark IDs and
split metadata does not by itself expose question/image content; this distinction
and all exclusion evidence are recorded in the split manifest. Never infer a
case ID from a question-ID prefix. The final manifest reports actual counts,
not the paper's nominal case count.

Inference JSONL contains only question ID, case ID, question/options, images and
figure labels. Labels live in a separate scoring directory. The generation
process does not import or open labels. Native bytes means the saved benchmark
image bytes, not DICOM or a claim that the provider performs no resizing. Keep
all selected images; pair known figure labels with the corresponding image
immediately before that image. Do not invent a figure label when none is known.
New records use `native_bytes_sent`, replacing the misleading
`native_bytes_no_resizing` wording without changing historical artifacts.

## Budget, recovery and artifacts

Qwen uses the `dashscope` credential slot and GPT-4o uses `apiyi`. Mixed-provider
phases accept a credential map via stdin and pass only the relevant key to each
child. A single-key input is rejected for mixed slots; preparation needs no key.
No key is stored in the configuration, protocol, command arguments or repository.

One incremental budget applies to the entire experiment, including capability
checks and technical attempts. Serial arm ledgers inherit preceding committed
spend. The original account ledger is retained; no account ledger is published.
Runtime byte-drift shutdown stays disabled as the user previously instructed;
the original identity, locks and amount checks remain. A shared persistent
request counter spans restarts and models. SDK retries are zero. A sample-specific
definite 400/413/422 rejection becomes a missing terminal and execution continues.
Only an explicit non-quota 429 can receive at most one technical retry within
the existing limits. Timeout/connection/408/5xx outcomes are conservatively
treated as unknown, recorded missing and not resent; the next independent sample
may proceed. Five consecutive failed samples stop the arm, and the streak survives
restart. Authentication, quota, model/endpoint/configuration, identity, budget,
ledger and local persistence failures still stop immediately. A successful reply
resets the technical-failure streak even when its answer is unparsed; unparsed
answers remain missing in scoring. Saved terminals are never rewritten.
Resolved stops can be explicitly acknowledged once by exact arm and stop-event ID.
The acknowledgement is a separate immutable recovery record: it resets the failure
streak at that boundary and resumes the next unfinished sample. Ordinary restart
does not acknowledge a stop, and no acknowledgement bypasses budget/ledger checks
or repeats a failed request.

The unchanged ledger charges the full reservation when usage is unavailable or
cannot be settled. A GPT-4o reservation is CNY 2.56384 at the frozen bounds/rates;
this is conservative budget accounting, not an APIYi invoice. This revision does
not claim that a 4xx was billed, fabricate zero usage or relax the monetary guard.

The frozen tune inputs contain at most five images per question. Qwen's 131,072
input-token reservation/hard bound leaves room for five provider high-resolution
image allocations (up to 16,384 each) and text; it avoids treating the old
single-image token allowance as a valid multi-image ceiling. Settlement uses
returned actual usage, not the full pre-call reservation, when complete usage
is available. GPT-4o instead reserves at most 120,000 input tokens, within its
128,000 context together with the actual 2,048 requested output ceiling. Its
conservative usage guard allows at most 8,192 output tokens; this is a billing
protection bound, not the request's generation length.

The maximum planned request inventory is 56,268 normal plus 2,814 technical
attempts; this is an upper bound across all planned stages, not permission to
spend to that number. The monetary cap applies first. Optional tool-voter and
external-dataset stages are deferred until primary results and dataset access
are established. No external restricted patient data is assumed available.

Each finished phase publishes the exact frozen code/configuration, full
denominators, samples/votes, corrections/harms/missing recovery, case-aware
uncertainty, question/options/images, observable requests/replies, model
identities, usage, costs and failures. Historical case content is published per
the user's repository preference; credentials, account ledgers and weights are
excluded. Reports distinguish current experiment evidence from hypotheses.

## Provider sources checked 2026-11-02

- [Alibaba model pricing](https://help.aliyun.com/zh/model-studio/model-pricing):
  Beijing Qwen3.8-Max 12/36 CNY per million input/output tokens.
  Qwen3-VL-Plus retains the existing conservative 4/12 accounting rates.
  Cache discounts are not assumed; these are accounting estimates, not invoices.
- [APIYi public pricing](https://api.apiyi.com/api/pricing) and
  [public conversion metadata](https://api.apiyi.com/api/status): GPT-4o model
  ratio 1.25, output multiplier 4, quota_per_unit 500000 and default/svip group
  ratio 1 imply USD 2.5/10 per million input/output tokens. The guard retains
  conservative CNY 8/USD, yielding CNY 20/80, without cache discounts; the site's
  displayed conversion was 7.3. These are estimates, not the account invoice.
- [OpenAI GPT-4o model documentation](https://developers.openai.com/api/docs/models/gpt-4o):
  image input, 128,000 context and alias/snapshot distinction. APIYi's authenticated
  read-only model catalog listed `gpt-4o` and dated variants on 2026-11-02;
  catalog presence is not a successful vision inference. No paid smoke was made.
- [Alibaba vision API](https://docs.bailian.console.aliyun.com/en/model-studio/vision):
  Qwen thinking and `vl_high_resolution_images` behavior. Actual support must
  still be confirmed on this credential/endpoint with the two-question smoke.

## Entrypoints

- `data_tools/make_heldout.py`: case-isolated split and separate labels.
- `experiments/configure_vote_gain.py`: explicit-budget phase-0 configuration.
- `experiments/run_sampled_vlm.py`: independent immutable samples.
- `experiments/run_vote_phase.py`: serial frozen arms; no in-process scoring.
- `experiments/score_votes.py`: offline complete-phase scores and votes.

Later phases are materialized only after their upstream decisions are available;
no heldout label or intermediate test accuracy may change those decisions.
