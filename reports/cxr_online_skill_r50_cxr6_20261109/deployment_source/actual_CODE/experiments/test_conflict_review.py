"""Unit tests for conflict_review (R6). Fabricated inputs only, no GPU/API."""

import unittest

import conflict_review as cr


class ReportClaimsTest(unittest.TestCase):
    def test_plain_negation(self):
        self.assertEqual(cr.report_claims("No pleural effusion.")["effusion"], "absent")

    def test_no_evidence_of(self):
        self.assertEqual(cr.report_claims("No evidence of pneumonia.")["pneumonia"], "absent")

    def test_plain_presence(self):
        self.assertEqual(cr.report_claims("Moderate pleural effusion is present.")["effusion"], "present")

    def test_uncertain(self):
        self.assertEqual(cr.report_claims("Cannot exclude pneumonia.")["pneumonia"], "uncertain")

    def test_two_findings_in_one_sentence(self):
        claims = cr.report_claims("Small effusion, no pneumothorax.")
        self.assertEqual(claims["effusion"], "present")
        self.assertEqual(claims["pneumothorax"], "absent")

    def test_unmentioned_pathology_is_absent_from_the_map(self):
        self.assertNotIn("fracture", cr.report_claims("No pleural effusion."))

    def test_present_outranks_uncertain_across_sentences(self):
        claims = cr.report_claims("Possible pneumonia. Pneumonia is present on the right.")
        self.assertEqual(claims["pneumonia"], "present")

    def test_uncertain_is_not_downgraded_to_absent(self):
        claims = cr.report_claims("Possible pneumonia. No effusion.")
        self.assertEqual(claims["pneumonia"], "uncertain")

    def test_empty_text_yields_no_claims(self):
        self.assertEqual(cr.report_claims(""), {})


class ClassifierClaimsTest(unittest.TestCase):
    def test_confident_scores_become_claims(self):
        claims = cr.classifier_claims({"Pneumothorax": 0.93, "Effusion": 0.04})
        self.assertEqual(claims, {"pneumothorax": "present", "effusion": "absent"})

    def test_ambiguous_band_yields_no_claim(self):
        claims = cr.classifier_claims({"Pneumothorax": 0.55, "Effusion": 0.45}, threshold=0.6)
        self.assertEqual(claims, {})

    def test_unknown_label_ignored(self):
        self.assertEqual(cr.classifier_claims({"Atelectasis ": 0.9, "nonsense": 0.9}),
                         {"atelectasis": "present"})

    def test_bad_threshold_rejected(self):
        with self.assertRaises(ValueError):
            cr.classifier_claims({"Effusion": 0.9}, threshold=0.5)

    def test_non_numeric_score_skipped(self):
        self.assertEqual(cr.classifier_claims({"Effusion": "high"}), {})


class ConflictTest(unittest.TestCase):
    def test_contradiction_detected(self):
        a = cr.classifier_claims({"Pneumothorax": 0.95})
        b = cr.report_claims("No pneumothorax.")
        conflicts = cr.find_conflicts(a, b)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["pathology"], "pneumothorax")
        self.assertEqual(conflicts[0]["present_in"], "chest_xray_classifier")
        self.assertEqual(conflicts[0]["absent_in"], "chest_xray_report_generator")

    def test_agreement_is_not_a_conflict(self):
        a = cr.classifier_claims({"Effusion": 0.95})
        b = cr.report_claims("Moderate pleural effusion.")
        self.assertEqual(cr.find_conflicts(a, b), [])

    def test_uncertain_never_counts_as_conflict(self):
        a = cr.classifier_claims({"Pneumonia": 0.95})
        b = cr.report_claims("Cannot exclude pneumonia.")
        self.assertEqual(cr.find_conflicts(a, b), [])

    def test_absent_claims_only_do_not_conflict(self):
        a = cr.classifier_claims({"Effusion": 0.02})
        b = cr.report_claims("No effusion.")
        self.assertEqual(cr.find_conflicts(a, b), [])


class RenderTest(unittest.TestCase):
    def test_empty_when_no_conflicts(self):
        self.assertEqual(cr.render_review([], 0.6), "")

    def test_block_names_both_tools_and_the_operating_point(self):
        conflicts = cr.find_conflicts(cr.classifier_claims({"Pneumothorax": 0.95}),
                                      cr.report_claims("No pneumothorax."))
        block = cr.render_review(conflicts, 0.6)
        self.assertIn("TOOL CONFLICT", block)
        self.assertIn("pneumothorax", block)
        self.assertIn("chest_xray_classifier", block)
        self.assertIn("chest_xray_report_generator", block)
        self.assertIn("0.60", block)
        self.assertIn("not calibrated", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
