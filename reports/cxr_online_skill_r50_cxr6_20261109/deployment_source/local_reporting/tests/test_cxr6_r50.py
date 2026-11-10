"""New R50 retrieval boundaries; synthetic data, no API/model/reference access."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from skill_lifecycle_r50 import retrieve,initial,DEFAULTS
from run_online_skill_r50 import ARM


def repository(n):
    repo=initial()
    for i in range(n):
        repo['skills'][str(i)]={'c':{'branch':'task_level','task_category':'location','required_tools':[]},
          'status':'active','vector':[1.,0.],'u_by_category':{},'u':.5,'last_reinforced':0}
    return repo


class RetrievalBoundaries(unittest.TestCase):
    def test_nonempty_pools_can_all_be_rejected(self):
        for n in (1,5,6):
            with self.subTest(n=n):
                calls=[]
                def reject(pool):calls.append(pool);return []
                self.assertEqual(retrieve(repository(n),[1.,0.],'location',[],DEFAULTS,reject),[])
                self.assertEqual(len(calls),1)
                self.assertEqual(len(calls[0]),min(5,n))

    def test_no_candidates_means_no_prescreen(self):
        def unexpected(pool):self.fail('empty pool must not spend a META request')
        self.assertEqual(retrieve(repository(0),[1.,0.],'location',[],DEFAULTS,unexpected),[])
        self.assertEqual(retrieve(repository(1),[1.,0.],'presence',[],DEFAULTS,unexpected),[])

    def test_only_prescreened_ids_can_enter_context(self):
        selected=retrieve(repository(5),[1.,0.],'location',[],DEFAULTS,lambda pool:['3'])
        self.assertEqual([s['id'] for s in selected],['3'])
        with self.assertRaisesRegex(ValueError,'prescreen_unknown_id'):
            retrieve(repository(1),[1.,0.],'location',[],DEFAULTS,lambda pool:['absent'])

    def test_isolated_arm_identity(self):
        self.assertEqual(ARM,'M43-IM-GT-S50-CXR6')


if __name__=='__main__':unittest.main()
