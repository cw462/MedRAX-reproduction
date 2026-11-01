import base64,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from official_gain.visual_inspection import roi,content,manual_box_allowed
from official_gain.evidence_agent import evidence_payload,ToolSession

class Tests(unittest.TestCase):
 def test_actual_new_pixels_and_coordinate_binding(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'raw.png';im=Image.new('RGB',(200,100),'black')
   for x in range(200):
    for y in range(100):im.putpixel((x,y),(x,y,0))
   im.save(p);source={'path':str(p),'image_id':'image:1','source_filename':'raw.png','size':[200,100]}
   views=roi(source,[.25,.2,.75,.8],d,'example');crop=Image.open(views[0]['path'])
   self.assertEqual(crop.size,(100,60));self.assertEqual(crop.tobytes(),im.crop((50,20,150,80)).tobytes())
   parts=content({'question':'inspect margin'},[source]+views);urls=[x['image_url']['url'] for x in parts if x['type']=='image_url']
   self.assertEqual(len(urls),3);self.assertEqual(base64.b64decode(urls[1].split(',')[1]),Path(views[0]['path']).read_bytes());self.assertNotEqual(urls[0],urls[1])
 def test_patient_side_never_uses_display_convention(self):
  action={'box':[.05,.1,.45,.9],'target_patient_side':'right'}
  self.assertFalse(manual_box_allowed(action,{'view':'frontal','marker':{'text':'unknown','box':None}}))
  self.assertTrue(manual_box_allowed(action,{'view':'frontal','marker':{'text':'R','box':[.01,.01,.1,.1]}}))
  self.assertFalse(manual_box_allowed(action,{'view':'frontal','marker':{'text':'L','box':[.01,.01,.1,.1]}}))
 def test_observer_no_initial_answer_or_reference(self):
  value=evidence_payload([{'image_ids':['image:1'],'question':'Which margin is visible?'}],[])
  self.assertEqual(set(value),{'neutral_attribute_questions','tool_observations'})
  self.assertFalse({'answer','reference','initial_answer','initial_reason','D0'}&set(value))
 def test_original_tuple_survives_cache_and_budget(self):
  class Schema:
   @staticmethod
   def model_validate(v):return v
  class Tool:
   args_schema=Schema
   def invoke(self,args):return ({'score':.2},{'analysis_status':'completed'})
  with tempfile.TemporaryDirectory() as d:
   im={'image_id':'image:1','path':str(Path(d)/'raw.png')};Image.new('RGB',(20,20)).save(im['path'])
   s=ToolSession({'test':Tool()},[im],d,Path(d)/'M','M');a=s.execute('test',{'image_path':im['path']})
   p=ToolSession({'test':Tool()},[im],d,Path(d)/'P','P');b=p.execute('test',{'image_path':im['path']})
   self.assertIsInstance(b,tuple);self.assertEqual(str(a),str(b));self.assertEqual(p.actual,0)
   for _ in range(3):p.execute('test',{'image_path':im['path']})
   self.assertIn('budget',p.execute('test',{'image_path':im['path']})['error'])

if __name__=='__main__':unittest.main()
