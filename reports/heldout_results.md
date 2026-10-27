# Heldout evaluation status

**Not run.** No heldout accuracy, memory gain or generalization claim is available.

The original frozen heldout contains **510 questions from 123 case IDs**. A predeclared additional input excludes the one case involved in confirmed cross-split exact-image overlap, leaving **505 questions from 122 cases**. Both denominators must be reported separately; the latter removes known exact overlap only and does not prove patient or pretraining independence. See [data audit](data-audit-v3-2026-10-27.md).

Before inference, freeze the complete available tool set, protocol, memory pools, hyperparameters, final method, scoring rules and schedule. At minimum run R0, R1 and the final method on the same full predeclared heldout questions, with failures and unrun questions retained in reporting. No heldout feedback may update the pool or choose the method. The 2,500-question paper benchmark contains these cases and must be isolated from development selection.

Current prerequisites are incomplete: full tool deployment, successful train trajectories, validation controls and budget forecast. No test result has been substituted with development accuracy.
