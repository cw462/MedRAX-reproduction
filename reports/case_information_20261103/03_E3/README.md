# 03_E3: generation milestone

Generation for this milestone has finished. Accuracy is deliberately deferred until every planned arm finishes.

[Complete questions, options, images and saved requests/responses](cases.json) · [Usage and status](summary.json) · [Configuration](configuration.json) · [Image provenance](assets.json).

|Arm|Planned questions|Saved request terminals|Status|
|---|---:|---:|---|
|E3_Classifier|402|402|generation_complete|
|E3_Report|402|402|generation_complete|
|E3_Evidence|402|402|generation_complete|

CNY amounts are inherited bookkeeping proxies, not provider prices or Credits conversion. Actual Credits are unknown. Case-batch requests are counted once; their child answers do not add cost.

## Tool evidence and recovery provenance

[Caption-derived image modality list](caption_modalities.json) · [Tool cache index](tool_cache/index.json) · [Preserved classifier serialization incident](recovery_history/01_classifier_serialization/incident.json). Each arm includes its actual evidence projections and saved model requests. Only confirmed chest X-rays triggered tools; classifier evidence uses the frozen strong-output threshold. Tool coverage is not accuracy.

The initial 116 classifier calls produced outputs that failed JSON persistence because of NumPy scalar serialization. Those failures remain public; 116 classifier calls were repeated after lossless transport conversion, while the 116 saved report calls were reused. Total tool invocations: 348 (232 classifier, including failed persistence, plus 116 report). This recovery is not a method gain or an additional model API probe. E3 scoring remains deferred until E0 finishes. [Already authorized E2/E1 interim scores](../interim_E2_E1/README.md) remain separate.
