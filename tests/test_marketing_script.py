import unittest
from agents.product_understanding.campaign_brief import CampaignBrief
from agents.script.marketing_script import ScriptAgent
class Fake:
 def __init__(self,data): self.data=data; self.prompt=""
 def generate(self,prompt,schema): self.prompt=prompt; return self.data
class Tests(unittest.TestCase):
 def setUp(self):
  self.brief=CampaignBrief("KingSong 14M","Electric Unicycles",("800W motor",),("Convenient movement",),"Urban commuters","Explore","Energetic",("Compact",),"Freedom","url",())
  self.data={"hook":"Ready to ride smarter?","voiceover":"Meet KingSong 14M with an 800W motor.","on_screen_text":["800W motor"],"call_to_action":"Explore it on Radboards.","estimated_duration_seconds":25}
 def test_generates_script(self):
  model=Fake(self.data); result=ScriptAgent(model).generate_script(self.brief); self.assertEqual(result.estimated_duration_seconds,25); self.assertIn("KingSong 14M",model.prompt)
 def test_rejects_invalid_duration(self):
  with self.assertRaises(ValueError): ScriptAgent(Fake(dict(self.data,estimated_duration_seconds=60))).generate_script(self.brief)
 def test_rejects_blank_cta(self):
  with self.assertRaises(ValueError): ScriptAgent(Fake(dict(self.data,call_to_action=" "))).generate_script(self.brief)
if __name__=='__main__': unittest.main()