import unittest
from agents.product_understanding.campaign_brief import ProductUnderstandingAgent
from scraper.radboards import ScrapedProduct
class Fake:
 def __init__(self,data): self.data=data; self.prompt=""
 def generate(self,prompt,schema): self.prompt=prompt; return self.data
class Tests(unittest.TestCase):
 def setUp(self):
  self.product=ScrapedProduct("Electric Unicycles","KingSong 14M","https://radboards.in/products/kingsong-14m","An 800W motor and carrying handle.",50000,True,())
  self.data={"features":["800W motor"],"benefits":["Convenient movement"],"target_audience":"Urban commuters","marketing_goal":"Explore the product page","brand_tone":"Energetic and practical","selling_points":["Compact"],"emotional_angle":"Freedom to move"}
 def test_creates_brief(self):
  model=Fake(self.data); brief=ProductUnderstandingAgent(model,"Brand context").create_campaign_brief(self.product,["output/images/kingsong/01.jpg"]); self.assertEqual(brief.product_name,"KingSong 14M"); self.assertIn("800W motor",model.prompt)
 def test_rejects_incomplete_response(self):
  data=dict(self.data); data.pop("benefits")
  with self.assertRaises(ValueError): ProductUnderstandingAgent(Fake(data),"Brand").create_campaign_brief(self.product)
 def test_rejects_empty_context(self):
  with self.assertRaises(ValueError): ProductUnderstandingAgent(Fake(self.data)," ")
if __name__=='__main__': unittest.main()