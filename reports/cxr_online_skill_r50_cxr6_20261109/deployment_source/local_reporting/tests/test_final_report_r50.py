"""New formatter acceptance rules, synthetic summaries only."""
import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'local_assets'))
import finalize_r50_report as report


class FinalReportRules(unittest.TestCase):
    def metadata(self):
        return {'status':'completed','native_exit_code':0,'scope_complete':True,'audit_scope':sorted(report.REVIEW_SCOPE),
          'session_id':'new-result-review','fresh':True,'modelUsage':{'deepseek-v4-pro':{'fixture':True}},
          'duration_ms':1,'turns':1,'publication_blockers':[],'claim_supported':'no'}

    def test_negative_claim_verdict_does_not_prevent_honest_publication(self):
        value=self.metadata();self.assertEqual(report.validate_review(value,'initial-review')['claim_supported'],'no')

    def test_missing_actual_scope_or_reused_execution_review_is_rejected(self):
        for field,value in (('native_exit_code',1),('scope_complete',False),('session_id','initial-review'),
                            ('audit_scope',[]),('modelUsage',{}),('fresh',False)):
            with self.subTest(field=field):
                metadata=self.metadata();metadata[field]=value
                with self.assertRaisesRegex(ValueError,'actual_fresh_complete_scope'):
                    report.validate_review(metadata,'initial-review')

    def test_table_preserves_losses_and_zero_net_changes(self):
        loaded={}
        for i,(ds,(n,baseline,old,old49)) in enumerate(report.DATASETS.items()):
            delta=(-2,0,1)[i];current=old+delta
            paired={'corrected':max(delta,0),'harmed':max(-delta,0),'net':delta}
            loaded[ds]={'summary':{'arms':{report.ARM:{'correct':current,'n':n,'micro_pct':current/n*100,'macro_pct':1.},
              baseline:{'correct':old}},'comparisons':{baseline:paired,'R49_online_GT_Skill':copy.deepcopy(paired)}}}
        table=report.result_table(loaded)
        self.assertIn('0/2/-2',table);self.assertIn('0/0/+0',table);self.assertIn('1/0/+1',table)


if __name__=='__main__':unittest.main()
