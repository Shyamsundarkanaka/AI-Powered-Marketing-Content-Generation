"""Create a structured campaign brief from one scraped Radboards product."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
from agents.gemini import StructuredGenerator
from scraper.radboards import ScrapedProduct
@dataclass(frozen=True)
class CampaignBrief:
    product_name:str; category:str; features:tuple[str,...]; benefits:tuple[str,...]; target_audience:str; marketing_goal:str; brand_tone:str; selling_points:tuple[str,...]; emotional_angle:str; source_url:str; local_image_paths:tuple[str,...]
SCHEMA={"type":"object","required":["features","benefits","target_audience","marketing_goal","brand_tone","selling_points","emotional_angle"],"properties":{"features":{"type":"array","items":{"type":"string"}},"benefits":{"type":"array","items":{"type":"string"}},"target_audience":{"type":"string"},"marketing_goal":{"type":"string"},"brand_tone":{"type":"string"},"selling_points":{"type":"array","items":{"type":"string"}},"emotional_angle":{"type":"string"}}}
def load_brand_context(path:str|Path)->str:
    content=Path(path).read_text(encoding="utf-8").strip()
    if not content: raise ValueError("Brand context cannot be empty.")
    return content
def _s(data:Mapping[str,object],key:str)->str:
    value=data.get(key)
    if not isinstance(value,str) or not value.strip(): raise ValueError(f"Campaign brief field '{key}' must be a non-empty string.")
    return value.strip()
def _ss(data:Mapping[str,object],key:str)->tuple[str,...]:
    value=data.get(key)
    if not isinstance(value,list) or not value or not all(isinstance(x,str) and x.strip() for x in value): raise ValueError(f"Campaign brief field '{key}' must be a non-empty list of strings.")
    return tuple(x.strip() for x in value)
class ProductUnderstandingAgent:
    def __init__(self,generator:StructuredGenerator,brand_context:str)->None:
        if not brand_context.strip(): raise ValueError("Brand context cannot be empty.")
        self.generator,self.brand_context=generator,brand_context.strip()
    def create_campaign_brief(self,product:ScrapedProduct,local_image_paths:Sequence[str|Path]=())->CampaignBrief:
        paths=tuple(str(Path(p)) for p in local_image_paths)
        facts={"title":product.title,"category":product.category,"description":product.description,"price_inr":product.price_inr,"available":product.available,"source_url":product.url,"local_image_paths":paths}
        prompt="Create a factual Radboards campaign brief. Use only product data and brand context. Do not invent specifications, safety, discounts, availability, or features.\n\nBRAND CONTEXT:\n"+self.brand_context+"\n\nPRODUCT DATA:\n"+json.dumps(facts)
        data=self.generator.generate(prompt,SCHEMA)
        return CampaignBrief(product.title,product.category,_ss(data,"features"),_ss(data,"benefits"),_s(data,"target_audience"),_s(data,"marketing_goal"),_s(data,"brand_tone"),_ss(data,"selling_points"),_s(data,"emotional_angle"),product.url,paths)